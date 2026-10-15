"""Assessment Orchestrator and Audit Engine (Requirements A and E).

Coordinates normalized student responses, dynamic evaluator routing based on
question classification, failure isolation, and evaluation trace generation.
Keeps orchestration strictly separate from deterministic rubric grading.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, List, Optional

from backend.app.schemas.evaluator_contracts import (
    CriterionScoreResult,
    EvaluationTrace,
    EvaluatorOutput,
    OrchestrationResult,
    SourceReference,
)
from backend.app.services.evaluation_service import extract_authoritative_max_score
from backend.app.services.evaluators.accuracy_math_evaluator import AccuracyMathEvaluator
from backend.app.services.evaluators.base import BaseEvaluator
from backend.app.services.evaluators.code_evaluator import CodeEvaluator
from backend.app.services.evaluators.concept_evaluator import ConceptEvaluator
from backend.app.services.evaluators.diagram_visual_evaluator import DiagramVisualEvaluator, is_diagram_question
from backend.app.services.retrieval_service import retrieve_grounding_sources
from backend.app.services.rubric_scoring_service import score_rubric_deterministically
from backend.app.services.segmentation_service import normalize_question_id

logger = logging.getLogger(__name__)


class AssessmentOrchestrator:
    """Orchestrates evaluator selection, execution, and trace capture."""

    def __init__(self) -> None:
        self.evaluators: Dict[str, BaseEvaluator] = {
            "concept_text": ConceptEvaluator(),
            "accuracy_math": AccuracyMathEvaluator(),
            "code": CodeEvaluator(),
            "diagram_visual": DiagramVisualEvaluator(),
        }

    def select_evaluators(
        self,
        question: str,
        model_answer: str,
        rubric: dict,
        image_bytes: Optional[bytes] = None,
        force_evaluators: Optional[List[str]] = None,
    ) -> Tuple[List[str], Dict[str, str]]:
        """Dynamically select only evaluators relevant to this question."""
        if force_evaluators:
            reasons = {e: "Explicitly requested by assessment configuration." for e in force_evaluators}
            return force_evaluators, reasons

        selected: List[str] = ["concept_text"]
        reasons: Dict[str, str] = {
            "concept_text": "Core conceptual understanding and technical terminology assessment."
        }

        combined_text = (question + " " + model_answer + " " + str(rubric)).lower()

        # Math / calculation detection
        math_keywords = ["calculate", "compute", "solve", "formula", "value", "sum", "probability", "derivative", "integral", "ratio", "percentage"]
        has_math_kw = any(kw in combined_text for kw in math_keywords)
        has_digits_operators = any(c in combined_text for c in "=+-*/^") and any(c.isdigit() for c in combined_text)
        if has_math_kw or has_digits_operators:
            selected.append("accuracy_math")
            reasons["accuracy_math"] = "Mathematical expressions, formulas, or numerical calculations detected."

        # Code detection
        code_keywords = ["code", "function", "program", "algorithm", "implement", "class", "syntax", "pseudo-code", "def ", "loop"]
        if any(kw in combined_text for kw in code_keywords):
            selected.append("code")
            reasons["code"] = "Programming code constructs or algorithmic logic requested."

        # Diagram / visual detection
        if is_diagram_question(question, rubric):
            selected.append("diagram_visual")
            if image_bytes and len(image_bytes) > 0:
                reasons["diagram_visual"] = "Visual diagram/schematic question with provided image input."
            else:
                reasons["diagram_visual"] = "Visual diagram requested (image input verification needed)."

        return selected, reasons

    def orchestrate_question(
        self,
        assessment_id: str,
        question_id: str,
        question: str,
        student_answer: str,
        model_answer: str,
        rubric: dict,
        image_bytes: Optional[bytes] = None,
        selected_evaluators: Optional[List[str]] = None,
        routing_reasons: Optional[Dict[str, str]] = None,
    ) -> OrchestrationResult:
        """Run relevant evaluators, retrieve grounding context, and record execution trace."""
        norm_qid = normalize_question_id(question_id)

        # 1. Routing decision
        if selected_evaluators is None or routing_reasons is None:
            selected_evaluators, routing_reasons = self.select_evaluators(
                question, model_answer, rubric, image_bytes=image_bytes
            )

        # 2. Genuine knowledge retrieval scoped to assessment & question
        retrieved_sources: List[SourceReference] = []
        try:
            retrieved_sources = retrieve_grounding_sources(
                assessment_id=assessment_id,
                question_id=norm_qid,
                student_answer=student_answer,
            )
        except Exception as exc:
            logger.warning("Retrieval failed for %s: %s", norm_qid, exc)

        # 3. Execute selected evaluators with isolation and timing
        evaluator_outputs: Dict[str, EvaluatorOutput] = {}
        execution_times: Dict[str, float] = {}
        failures: List[str] = []

        for eval_name in selected_evaluators:
            evaluator = self.evaluators.get(eval_name)
            if not evaluator:
                continue

            t_start = time.perf_counter()
            try:
                out = evaluator.evaluate(
                    question=question,
                    student_answer=student_answer,
                    model_answer=model_answer,
                    rubric=rubric,
                    retrieved_sources=retrieved_sources,
                    image_bytes=image_bytes,
                )
                evaluator_outputs[eval_name] = out
                if out.status == "failed":
                    failures.append(eval_name)
            except Exception as exc:
                logger.exception("Evaluator '%s' threw an unhandled exception", eval_name)
                evaluator_outputs[eval_name] = EvaluatorOutput(
                    evaluator_name=eval_name,
                    status="failed",
                    confidence=0.0,
                    error=str(exc),
                    observations=[f"Evaluator execution crashed: {exc}"],
                )
                failures.append(eval_name)
            finally:
                t_elapsed = (time.perf_counter() - t_start) * 1000.0
                execution_times[eval_name] = round(t_elapsed, 2)

        return OrchestrationResult(
            question_id=norm_qid,
            selected_evaluators=selected_evaluators,
            routing_reasons=routing_reasons,
            evaluator_outputs=evaluator_outputs,
            retrieved_sources=retrieved_sources,
            execution_times_ms=execution_times,
            failures=failures,
        )


_default_orchestrator = AssessmentOrchestrator()


def detect_contradictions(evaluator_outputs: Dict[str, EvaluatorOutput]) -> List[str]:
    """Detect significant disagreements or contradictions between specialized evaluators."""
    contradictions = []
    concept = evaluator_outputs.get("concept_text")
    accuracy = evaluator_outputs.get("accuracy_math")

    if concept and accuracy and concept.status == "success" and accuracy.status == "success":
        c_claims = concept.claims
        a_claims = accuracy.claims
        if c_claims and a_claims:
            c_factor = c_claims[0].score_factor
            a_factor = a_claims[0].score_factor
            # High concept understanding but severe calculation failure
            if c_factor >= 0.70 and a_factor <= 0.30:
                contradictions.append(
                    "High conceptual understanding reported, but numerical/factual accuracy failed."
                )
            elif c_factor <= 0.30 and a_factor >= 0.70:
                contradictions.append(
                    "Calculation matches target, but core conceptual explanation is missing."
                )


    return contradictions


# In-memory evaluation trace store for audit trail
_trace_store: Dict[str, EvaluationTrace] = {}


def store_trace(trace: EvaluationTrace) -> None:
    _trace_store[trace.trace_id] = trace


def get_trace(trace_id: str) -> Optional[EvaluationTrace]:
    return _trace_store.get(trace_id)


def evaluate_with_orchestrator(
    assessment_id: str,
    question_id: str,
    question: str,
    student_answer: str,
    model_answer: str,
    rubric: dict,
    image_bytes: Optional[bytes] = None,
    ocr_confidence: float = 1.0,
    mapping_confidence: float = 1.0,
    max_score: Optional[float] = None,
    orchestrator: Optional[AssessmentOrchestrator] = None,
) -> dict:
    """Full orchestrated assessment vertical slice:

    routing -> retrieval -> evaluators -> deterministic scoring -> audit trace.
    """
    orch = orchestrator or _default_orchestrator
    norm_qid = normalize_question_id(question_id)
    authoritative_max = max_score or extract_authoritative_max_score(rubric)

    t0 = time.perf_counter()

    # Step 1 & 2: Orchestration & Evaluation (Separated from Grading)
    orch_result = orch.orchestrate_question(
        assessment_id=assessment_id,
        question_id=norm_qid,
        question=question,
        student_answer=student_answer,
        model_answer=model_answer,
        rubric=rubric,
        image_bytes=image_bytes,
    )

    # Step 3: Deterministic Rubric Scoring in application code
    criteria_results, final_score, scoring_warnings = score_rubric_deterministically(
        rubric=rubric,
        student_answer=student_answer,
        evaluator_outputs=orch_result.evaluator_outputs,
        explicit_max_score=authoritative_max,
    )

    total_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    # Step 4: Faculty Review Flags & Contradiction Detection
    review_flags = list(scoring_warnings)
    if orch_result.failures:
        review_flags.append(f"evaluator_failures: {', '.join(orch_result.failures)}")

    contradictions = detect_contradictions(orch_result.evaluator_outputs)
    if contradictions:
        review_flags.append("evaluator_contradiction_detected")

    if not student_answer.strip():
        review_flags.append("no_answer_detected")
    elif len(student_answer.strip()) < 15:
        review_flags.append("short_answer")

    if ocr_confidence < 0.55:
        review_flags.append("low_ocr_confidence")
    if mapping_confidence < 1.0:
        review_flags.append("uncertain_question_mapping")

    # Compute overall confidence
    confidences = [
        out.confidence for out in orch_result.evaluator_outputs.values()
        if out.status == "success"
    ]
    mean_eval_conf = sum(confidences) / len(confidences) if confidences else 0.5
    combined_conf = round(mean_eval_conf * (0.5 + 0.5 * min(1.0, ocr_confidence)), 4)

    needs_review = bool(
        combined_conf < 0.60
        or review_flags
        or orch_result.failures
        or not student_answer.strip()
    )

    # Step 5: Construct Auditable Trace
    trace_id = f"tr-{uuid.uuid4().hex[:12]}"
    trace = EvaluationTrace(
        trace_id=trace_id,
        question_id=norm_qid,
        routing_reasons=orch_result.routing_reasons,
        evaluators_run=list(orch_result.evaluator_outputs.keys()),
        evaluators_failed=orch_result.failures,
        retrieval_sources=orch_result.retrieved_sources,
        criteria_breakdown=criteria_results,
        review_flags=review_flags,
        execution_time_ms=total_time_ms,
    )
    store_trace(trace)

    # Concept output details for strengths / missing concepts
    concept_out = orch_result.evaluator_outputs.get("concept_text")
    strengths = []
    missing_concepts = []
    if concept_out:
        if concept_out.key_terms_present:
            strengths.append(f"Correctly applied concepts: {', '.join(concept_out.key_terms_present[:4])}")
        if concept_out.evidence:
            strengths.append(f"Evidence: \"{concept_out.evidence[0]}\"")
        if concept_out.key_terms_missing:
            missing_concepts = concept_out.key_terms_missing[:4]

    feedback = f"Evaluated across {len(criteria_results)} rubric criteria. "
    if review_flags:
        feedback += f"Flags for faculty review: {', '.join(review_flags)}. "
    if missing_concepts:
        feedback += f"Missing key concepts: {', '.join(missing_concepts)}."

    # Subscores breakdown
    concept_score = 0.0
    accuracy_score = 0.0
    precision_score = 0.0
    technical_score = 0.0

    for c in criteria_results:
        c_low = c.criterion_name.lower()
        if "accuracy" in c_low or "math" in c_low:
            accuracy_score += c.awarded_score
        elif "precision" in c_low:
            precision_score += c.awarded_score
        elif "term" in c_low:
            technical_score += c.awarded_score
        else:
            concept_score += c.awarded_score

    return {
        "score": final_score,
        "max_score": authoritative_max,
        "concept_score": round(concept_score, 2),
        "accuracy_score": round(accuracy_score, 2),
        "precision_score": round(precision_score, 2),
        "technical_terminology_score": round(technical_score, 2),
        "strengths": strengths,
        "missing_concepts": missing_concepts,
        "feedback": feedback.strip(),
        "confidence": round(mean_eval_conf, 4),
        "combined_confidence": combined_conf,
        "ocr_confidence": round(ocr_confidence, 4),
        "needs_review": needs_review,
        "mapping_confidence": round(mapping_confidence, 4),
        "ocr_uncertain": "low_ocr_confidence" in review_flags or "uncertain_question_mapping" in review_flags,
        "visual_fallback_used": image_bytes is not None and len(image_bytes) > 0,
        "criteria_breakdown": [c.model_dump() for c in criteria_results],
        "evaluation_trace": trace.model_dump(),
    }
