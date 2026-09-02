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
from backend.app.services.segmentation_service import Segment, segment_answers

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


def _missing_answer_result(spec: QuestionSpec, ocr_conf: float) -> QuestionResult:
    max_score = spec.max_score or float(spec.rubric.get("max_score", 10) or 10)
    return QuestionResult(
        question_id=spec.question_id,
        student_answer="",
        answer_detected=False,
        score=0,
        max_score=max_score,
        concept_score=0,
        accuracy_score=0,
        precision_score=0,
        technical_terminology_score=0,
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
    by_id: Dict[str, Segment] = {s.question_id.lower(): s for s in segments}
    threshold = review_threshold()
    results: List[QuestionResult] = []

    for spec in questions:
        seg = by_id.get(spec.question_id.lower())
        if seg is None or not seg.text.strip():
            results.append(_missing_answer_result(spec, ocr_confidence))
            continue

        raw = evaluator(
            question=spec.question,
            student_answer=seg.text,
            model_answer=spec.model_answer,
            rubric=spec.rubric,
        )
        combined = combine_confidence(raw.get("confidence", 0.0), ocr_confidence)
        results.append(
            QuestionResult(
                question_id=spec.question_id,
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
    total = sum(r.score for r in results)
    total_max = sum(r.max_score for r in results)
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
    ocr = extract_text(image_bytes)
    expected = [q.question_id for q in questions]
    segmentation = segment_answers(ocr.text, expected_question_ids=expected)
    results = evaluate_segments(
        segmentation.segments, questions, ocr.mean_confidence, evaluator=evaluator
    )
    return build_response(ocr, segmentation.segments, results)
