"""Handwritten answer-sheet pipeline:

image -> OCR -> question-wise segmentation -> per-question evaluation
      -> marks + feedback + strengths + missing concepts + confidence

Evaluation reuses ``evaluation_service.evaluate_answer`` unchanged; this module
only orchestrates and aggregates.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Sequence

from backend.app.schemas.handwritten import (
    HandwrittenEvaluationResponse,
    QuestionResult,
    QuestionSpec,
    SegmentOut,
)
from backend.app.services import evaluation_service
from backend.app.services.ocr_service import OCRResult, extract_text
from backend.app.services.segmentation_service import (
    Segment,
    normalize_question_id,
    segment_answers,
)

Evaluator = Callable[..., dict]


def _default_evaluator(**kwargs) -> dict:
    return evaluation_service.evaluate_answer(**kwargs)


def review_threshold() -> float:
    return float(os.getenv("REVIEW_CONFIDENCE_THRESHOLD", "0.6"))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def combine_confidence(evaluator_confidence: float, ocr_confidence: float) -> float:
    """Blend evaluator and OCR confidence.

    OCR errors propagate into grading, so the evaluator's confidence is scaled
    by the OCR confidence (weighted so a good OCR read does not over-penalise).
    """
    ocr = _clamp01(ocr_confidence)
    ev = _clamp01(evaluator_confidence)
    return round(ev * (0.5 + 0.5 * ocr), 4)


def deduplicate_questions(questions: Sequence[QuestionSpec]) -> List[QuestionSpec]:
    """Deduplicate questions by normalized question ID to avoid score inflation."""
    seen = set()
    deduped: List[QuestionSpec] = []
    for q in questions:
        norm_id = normalize_question_id(q.question_id)
        if norm_id.lower() not in seen:
            seen.add(norm_id.lower())
            # Ensure rubric has matching max_score if spec.max_score is provided
            rubric = dict(q.rubric) if isinstance(q.rubric, dict) else {}
            if q.max_score is not None and "max_score" not in rubric:
                rubric["max_score"] = q.max_score
            deduped.append(
                QuestionSpec(
                    question_id=norm_id,
                    question=q.question,
                    model_answer=q.model_answer,
                    rubric=rubric,
                    max_score=q.max_score,
                )
            )
    return deduped


def _missing_answer_result(spec: QuestionSpec, ocr_conf: float) -> QuestionResult:
    max_score = spec.max_score or evaluation_service.extract_authoritative_max_score(spec.rubric)
    return QuestionResult(
        question_id=spec.question_id,
        student_answer="",
        answer_detected=False,
        score=0.0,
        max_score=round(float(max_score), 2),
        concept_score=0.0,
        accuracy_score=0.0,
        precision_score=0.0,
        technical_terminology_score=0.0,
        strengths=[],
        missing_concepts=["No answer was detected for this question in the scanned script."],
        feedback="No answer text was found for this question. Please verify the scan or mark manually.",
        confidence=1.0,
        ocr_confidence=ocr_conf,
        combined_confidence=0.0,
        needs_review=True,
    )


def evaluate_segments(
    segments: Sequence[Segment],
    questions: Sequence[QuestionSpec],
    ocr_confidence: float,
    evaluator: Evaluator = _default_evaluator,
) -> List[QuestionResult]:
    # Deduplicate questions by normalized id
    deduped_questions = deduplicate_questions(questions)
    by_id: Dict[str, Segment] = {
        normalize_question_id(s.question_id).lower(): s for s in segments
    }
    threshold = review_threshold()
    results: List[QuestionResult] = []

    for spec in deduped_questions:
        norm_qid = normalize_question_id(spec.question_id)
        seg = by_id.get(norm_qid.lower())
        if seg is None or not seg.text.strip():
            results.append(_missing_answer_result(spec, ocr_confidence))
            continue

        authoritative_max = spec.max_score or evaluation_service.extract_authoritative_max_score(spec.rubric)
        rubric = dict(spec.rubric)
        rubric["max_score"] = authoritative_max

        raw = evaluator(
            question=spec.question,
            student_answer=seg.text,
            model_answer=spec.model_answer,
            rubric=rubric,
        )

        # Enforce score clamping against authoritative rubric max
        score = min(float(authoritative_max), max(0.0, float(raw.get("score", 0.0))))
        raw["score"] = round(score, 2)
        raw["max_score"] = round(float(authoritative_max), 2)
        for subfield in ("concept_score", "accuracy_score", "precision_score", "technical_terminology_score"):
            raw[subfield] = round(min(float(authoritative_max), max(0.0, float(raw.get(subfield, 0.0)))), 2)

        ev_conf = _clamp01(raw.get("confidence", 0.0))
        combined = combine_confidence(ev_conf, ocr_confidence)

        results.append(
            QuestionResult(
                question_id=norm_qid,
                student_answer=seg.text,
                answer_detected=seg.detected,
                ocr_confidence=ocr_confidence,
                combined_confidence=combined,
                needs_review=combined < threshold,
                **raw,
            )
        )
    return results


def build_response(
    ocr: OCRResult,
    segments: Sequence[Segment],
    results: Sequence[QuestionResult],
) -> HandwrittenEvaluationResponse:
    total = round(sum(r.score for r in results), 2)
    total_max = round(sum(r.max_score for r in results), 2)
    graded = [r for r in results if r.answer_detected or r.student_answer]
    overall = (
        round(sum(r.combined_confidence for r in graded) / len(graded), 4) if graded else 0.0
    )
    return HandwrittenEvaluationResponse(
        extracted_text=ocr.text,
        ocr_confidence=_clamp01(ocr.mean_confidence),
        ocr_engine=ocr.engine,
        segments=[SegmentOut(**s.__dict__) for s in segments],
        results=list(results),
        total_score=total,
        total_max_score=total_max,
        overall_confidence=overall,
        needs_review=any(r.needs_review for r in results),
    )


def evaluate_handwritten_image(
    image_bytes: bytes,
    questions: Sequence[QuestionSpec],
    evaluator: Evaluator = _default_evaluator,
) -> HandwrittenEvaluationResponse:
    deduped = deduplicate_questions(questions)
    ocr = extract_text(image_bytes)
    expected = [q.question_id for q in deduped]
    segmentation = segment_answers(ocr.text, expected_question_ids=expected)
    results = evaluate_segments(
        segmentation.segments, deduped, ocr.mean_confidence, evaluator=evaluator
    )
    return build_response(ocr, segmentation.segments, results)

