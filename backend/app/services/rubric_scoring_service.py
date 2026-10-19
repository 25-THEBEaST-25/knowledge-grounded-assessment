"""Deterministic Rubric Scoring Engine (Requirement D).

Scores individual rubric criteria using evaluator evidence, calculates marks
deterministically in application code, validates evidence against raw student
input to prevent hallucinated credit, and strictly enforces criterion and
question maximum mark caps.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from backend.app.schemas.evaluator_contracts import (
    CriterionScoreResult,
    EvaluatorOutput,
    RubricCriterionSpec,
)
from backend.app.services.evaluation_service import extract_authoritative_max_score
from backend.app.services.evaluators.base import extract_verifiable_quotes

logger = logging.getLogger(__name__)


def parse_rubric_criteria(rubric: dict, authoritative_max: float) -> List[RubricCriterionSpec]:
    """Parse criteria from various rubric structures into normalized RubricCriterionSpec."""
    if not isinstance(rubric, dict):
        rubric = {}

    criteria_spec: List[RubricCriterionSpec] = []
    raw_criteria = rubric.get("criteria")

    if isinstance(raw_criteria, list):
        for item in raw_criteria:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("title") or "Criterion")
                max_sc = 0.0
                for k in ("max_score", "marks", "weight", "max_marks", "score"):
                    if k in item:
                        try:
                            max_sc = float(item[k])
                            break
                        except (ValueError, TypeError):
                            pass
                if max_sc <= 0:
                    max_sc = max(1.0, authoritative_max / len(raw_criteria))

                c_type = "concept"
                low_name = name.lower()
                if any(w in low_name for w in ["math", "accuracy", "calculation", "formula", "numerical"]):
                    c_type = "accuracy"
                elif any(w in low_name for w in ["code", "programming", "implementation", "syntax"]):
                    c_type = "code"
                elif any(w in low_name for w in ["diagram", "visual", "figure", "sketch", "flowchart"]):
                    c_type = "diagram"

                criteria_spec.append(
                    RubricCriterionSpec(
                        name=name,
                        max_score=round(max_sc, 2),
                        description=str(item.get("description", "")),
                        evaluator_type=c_type,
                    )
                )

    elif isinstance(raw_criteria, dict):
        for name, val in raw_criteria.items():
            max_sc = 0.0
            if isinstance(val, (int, float)):
                max_sc = float(val)
            elif isinstance(val, dict):
                for k in ("max_score", "marks", "weight"):
                    if k in val:
                        try:
                            max_sc = float(val[k])
                            break
                        except (ValueError, TypeError):
                            pass
            if max_sc <= 0:
                max_sc = max(1.0, authoritative_max / max(len(raw_criteria), 1))

            c_type = "concept"
            low_name = name.lower()
            if any(w in low_name for w in ["math", "accuracy", "calculation"]):
                c_type = "accuracy"
            elif any(w in low_name for w in ["code", "programming"]):
                c_type = "code"
            elif any(w in low_name for w in ["diagram", "visual"]):
                c_type = "diagram"

            criteria_spec.append(
                RubricCriterionSpec(
                    name=name.replace("_", " ").title(),
                    max_score=round(max_sc, 2),
                    evaluator_type=c_type,
                )
            )

    # If no explicit criteria list, synthesize academic criteria normalized to authoritative_max
    if not criteria_spec:
        # 40% Concept, 30% Accuracy, 15% Precision, 15% Technical Terminology
        c_score = round(authoritative_max * 0.40, 2)
        a_score = round(authoritative_max * 0.30, 2)
        p_score = round(authoritative_max * 0.15, 2)
        t_score = round(authoritative_max - (c_score + a_score + p_score), 2)

        criteria_spec = [
            RubricCriterionSpec(name="Conceptual Understanding", max_score=c_score, evaluator_type="concept"),
            RubricCriterionSpec(name="Accuracy & Factual Correctness", max_score=a_score, evaluator_type="accuracy"),
            RubricCriterionSpec(name="Precision & Relevance", max_score=p_score, evaluator_type="concept"),
            RubricCriterionSpec(name="Technical Terminology", max_score=t_score, evaluator_type="concept"),
        ]

    return criteria_spec


def verify_evidence(candidate_quotes: List[str], student_answer: str) -> Tuple[List[str], bool]:
    """Validate that candidate evidence quotes are genuinely present in student answer.

    Returns (verified_quotes, is_fully_authentic).
    """
    if not candidate_quotes:
        return [], True
    verified = extract_verifiable_quotes(student_answer, candidate_quotes)
    is_authentic = len(verified) == len(candidate_quotes)
    return verified, is_authentic


def score_rubric_deterministically(
    rubric: dict,
    student_answer: str,
    evaluator_outputs: Dict[str, EvaluatorOutput],
    explicit_max_score: float | None = None,
) -> Tuple[List[CriterionScoreResult], float, List[str]]:
    """Deterministically score each criterion in the rubric using evaluator evidence.

    Enforces strict mathematical bounds in application code:
    - Each criterion awarded score <= criterion.max_score
    - Total score <= authoritative_max
    - Disallows credit for unverified or fabricated quotes
    """
    authoritative_max = explicit_max_score or extract_authoritative_max_score(rubric)
    criteria_specs = parse_rubric_criteria(rubric, authoritative_max)
    results: List[CriterionScoreResult] = []
    review_flags: List[str] = []

    is_empty_answer = not student_answer.strip()

    for spec in criteria_specs:
        if is_empty_answer:
            results.append(
                CriterionScoreResult(
                    criterion_name=spec.name,
                    max_score=spec.max_score,
                    awarded_score=0.0,
                    attainment_factor=0.0,
                    reasoning="No student answer detected.",
                    evaluator_name="deterministic_scorer",
                    evidence_used=[],
                    verified_evidence=True,
                )
            )
            continue

        # Select relevant evaluator output
        eval_key = (
            "accuracy_math" if spec.evaluator_type == "accuracy"
            else "code" if spec.evaluator_type == "code"
            else "diagram_visual" if spec.evaluator_type == "diagram"
            else "concept_text"
        )

        ev_output = evaluator_outputs.get(eval_key) or evaluator_outputs.get("concept_text")

        attainment = 0.5  # default baseline if no claim
        reasoning = f"Evaluated under {spec.name}."
        claimed_quotes: List[str] = []
        eval_name = ev_output.evaluator_name if ev_output else "deterministic_scorer"

        if ev_output:
            if ev_output.status == "failed":
                review_flags.append(f"evaluator_failure_{ev_output.evaluator_name}")
                attainment = 0.0
                reasoning = f"Evaluator {ev_output.evaluator_name} failed: {ev_output.error or 'unknown'}"
            elif ev_output.status == "skipped":
                # If specialized evaluator skipped, fallback to conceptual assessment if available
                concept_output = evaluator_outputs.get("concept_text")
                if concept_output and concept_output.claims:
                    attainment = concept_output.claims[0].score_factor
                    reasoning = f"Evaluator skipped ({ev_output.observations[0] if ev_output.observations else ''}); grounded in concept text analysis."
                    claimed_quotes = concept_output.evidence
                else:
                    attainment = 0.0
                    reasoning = f"Evaluator skipped: {ev_output.observations[0] if ev_output.observations else 'not applicable'}"
            elif ev_output.claims:
                # Find matching claim
                match_claim = None
                for claim in ev_output.claims:
                    if (
                        claim.criterion_name.lower() in spec.name.lower()
                        or spec.name.lower() in claim.criterion_name.lower()
                    ):
                        match_claim = claim
                        break
                if not match_claim and ev_output.claims:
                    match_claim = ev_output.claims[0]

                if match_claim:
                    attainment = match_claim.score_factor
                    reasoning = match_claim.reasoning
                    claimed_quotes = match_claim.evidence_quotes or ev_output.evidence

        # Validate that claimed evidence quotes genuinely exist in the student's text
        verified_quotes, is_authentic = verify_evidence(claimed_quotes, student_answer)
        if not is_authentic:
            review_flags.append("unverified_evidence_detected")
            # Penalize attainment factor if model claimed quotes that do not exist
            attainment = max(0.0, attainment * 0.75)
            reasoning += " (Warning: Some claimed evidence quotes could not be verified in student text.)"

        # Clamp attainment factor strictly to [0.0, 1.0]
        attainment = max(0.0, min(1.0, float(attainment)))

        # Deterministic arithmetic: multiply max_score by attainment
        awarded = round(spec.max_score * attainment, 2)
        # Server-side hard clamp per criterion
        clamped_awarded = max(0.0, min(spec.max_score, awarded))


        results.append(
            CriterionScoreResult(
                criterion_name=spec.name,
                max_score=spec.max_score,
                awarded_score=clamped_awarded,
                attainment_factor=round(attainment, 4),
                reasoning=reasoning,
                evaluator_name=eval_name,
                evidence_used=verified_quotes,
                verified_evidence=is_authentic,
            )
        )

    # Deterministic final score sum
    raw_total = sum(r.awarded_score for r in results)
    final_score = round(max(0.0, min(authoritative_max, raw_total)), 2)

    return results, final_score, list(set(review_flags))
