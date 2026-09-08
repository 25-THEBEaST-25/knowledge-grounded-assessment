"""Handwritten answer-sheet pipeline:

image -> OCR -> question-wise segmentation -> per-question evaluation
      -> marks + feedback + strengths + missing concepts + confidence

Evaluation reuses ``evaluation_service.evaluate_answer`` unchanged; this module
only orchestrates and aggregates.
"""

from __future__ import annotations

import inspect
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from backend.app.schemas.handwritten import (
    HandwrittenEvaluationResponse,
    QuestionResult,
    QuestionSpec,
    SegmentOut,
)
from backend.app.services import evaluation_service
from backend.app.services.ocr_service import OCRLine, OCRResult, crop_region, extract_text, union_bbox
from backend.app.services.segmentation_service import (
    Segment,
    normalize_question_id,
    segment_answers,
)

logger = logging.getLogger(__name__)

Evaluator = Callable[..., dict]


def _default_evaluator(**kwargs) -> dict:
    return evaluation_service.evaluate_answer(**kwargs)


def review_threshold() -> float:
    return float(os.getenv("REVIEW_CONFIDENCE_THRESHOLD", "0.6"))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


# ---------------------------------------------------------------------------
# Per-question OCR evidence (A2/A3) and uncertainty detection (A4)
# ---------------------------------------------------------------------------


@dataclass
class AnswerEvidence:
    """OCR evidence for one question, fusing a text-level Segment with the
    OCRLine-level confidence/bbox data underneath it. Internal to the
    pipeline -- not returned to the frontend/student as-is; only the derived
    ``mapping_confidence``/``ocr_uncertain`` flags on QuestionResult are."""

    question_id: str
    ocr_confidence: float  # mean confidence of THIS segment's own lines, not the whole page
    line_count: int
    bbox: Optional[List[int]]  # union bbox of this segment's lines (OCR image coordinate space)
    mapping_confidence: float
    marker_detected: bool


def _segment_lines(segment: Segment, ocr_lines: Sequence[OCRLine]) -> List[OCRLine]:
    """``OCRResult.text`` is built by joining ``ocr_lines`` (already in
    reading order) with ``"\\n"``, so ``Segment.start_line``/``end_line`` --
    computed against that same joined text -- index directly into
    ``ocr_lines``. No separate alignment step is needed."""
    if segment.start_line < 0 or not ocr_lines:
        return []
    start = max(0, segment.start_line)
    end = min(len(ocr_lines) - 1, segment.end_line)
    if end < start:
        return []
    return list(ocr_lines[start : end + 1])


def build_answer_evidence(segments: Sequence[Segment], ocr: OCRResult) -> Dict[str, AnswerEvidence]:
    """One AnswerEvidence per segment, keyed by normalized question id (lowercase)."""
    evidence: Dict[str, AnswerEvidence] = {}
    for seg in segments:
        lines = _segment_lines(seg, ocr.lines)
        conf = round(sum(l.confidence for l in lines) / len(lines), 4) if lines else ocr.mean_confidence
        bbox = union_bbox([l.bbox for l in lines]) if lines else None
        evidence[normalize_question_id(seg.question_id).lower()] = AnswerEvidence(
            question_id=seg.question_id,
            ocr_confidence=conf,
            line_count=len(lines),
            bbox=bbox,
            mapping_confidence=seg.mapping_confidence,
            marker_detected=seg.marker_line is not None,
        )
    return evidence


def _uncertainty_min_answer_chars() -> int:
    try:
        return int(os.getenv("OCR_UNCERTAINTY_MIN_ANSWER_CHARS", "15"))
    except ValueError:
        return 15


def _uncertainty_confidence_threshold() -> float:
    try:
        return float(os.getenv("OCR_UNCERTAINTY_CONFIDENCE_THRESHOLD", "0.55"))
    except ValueError:
        return 0.55


def is_uncertain_evidence(evidence: AnswerEvidence, answer_text: str) -> bool:
    """A4: flag (never penalize) evidence with a suspicious signal --
    low OCR confidence, an uncertain question-to-answer mapping, or an
    answer that's suspiciously short for a detected marker."""
    if evidence.ocr_confidence < _uncertainty_confidence_threshold():
        return True
    if evidence.mapping_confidence < 1.0:
        return True
    stripped = answer_text.strip()
    if 0 < len(stripped) < _uncertainty_min_answer_chars():
        return True
    return False


def _visual_fallback_enabled() -> bool:
    return _env_bool("VISUAL_FALLBACK_ENABLED", True)


def _max_evaluation_concurrency() -> int:
    """A8: bounded concurrency for per-question Gemini calls. 1 = fully
    sequential (the original behavior). Never unbounded -- this is a hard
    cap on simultaneous in-flight provider requests per assessment, not a
    thread-pool-size suggestion.

    Measured, not assumed: threading itself is correct (proven both by
    test_pipeline_evidence.py's concurrency tests and by a real 3-question
    /handwritten/evaluate call, whose 3 results came back correct and
    correctly attributed). But a real, isolated 3-call concurrent-vs-
    sequential benchmark directly against the Gemini SDK (no test project
    code involved) showed the provider does not process concurrent requests
    from one API key in true parallel -- individual call latency inflated
    from ~1-5s sequential to 3-21s when fired concurrently, netting only a
    modest ~7% end-to-end improvement on a real 3-question evaluation
    (27.4s at concurrency=3 vs 29.5s at concurrency=1), not the ~3x a naive
    reading of "3 parallel workers" would suggest. This may differ on other
    API tiers/keys. Default kept at a middle value reflecting a real, small,
    measured benefit -- not a promise of proportional speedup."""
    try:
        return max(1, int(os.getenv("MAX_EVALUATION_CONCURRENCY", "3")))
    except ValueError:
        return 3


def _evaluator_accepts_evidence(evaluator: Evaluator) -> bool:
    """Whether ``evaluator`` will accept the new ``ocr_confidence``/
    ``image_bytes`` kwargs. True for the real evaluator (``**kwargs``) and
    for any future evaluator that declares them explicitly; False for the
    plain 4-arg fakes used throughout the existing test suite, so those
    keep working completely unchanged."""
    try:
        params = inspect.signature(evaluator).parameters
    except (TypeError, ValueError):
        return False
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return True
    return "ocr_confidence" in params and "image_bytes" in params


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
        mapping_confidence=0.0,
        ocr_uncertain=True,
        visual_fallback_used=False,
    )


def evaluate_segments(
    segments: Sequence[Segment],
    questions: Sequence[QuestionSpec],
    ocr_confidence: float,
    evaluator: Evaluator = _default_evaluator,
    ocr: Optional[OCRResult] = None,
) -> List[QuestionResult]:
    """Evaluate every question, with bounded concurrency (A8).

    ``ocr`` is optional and new: when provided (the real pipeline always
    provides it), per-question OCR evidence (A2/A3), uncertainty detection
    (A4), and the visual fallback (A5) are used. When omitted -- every
    existing caller in the test suite calls this with a plain
    ``ocr_confidence`` float and no ``ocr`` -- behavior is byte-for-byte the
    same as before this feature existed: every question gets the same
    page-level ``ocr_confidence`` and no image is ever attached.
    """
    deduped_questions = deduplicate_questions(questions)
    by_id: Dict[str, Segment] = {
        normalize_question_id(s.question_id).lower(): s for s in segments
    }
    evidence_by_id = build_answer_evidence(segments, ocr) if ocr is not None else {}
    threshold = review_threshold()
    evaluator_supports_evidence = _evaluator_accepts_evidence(evaluator)
    visual_fallback_enabled = _visual_fallback_enabled()

    def _evaluate_one(spec: QuestionSpec) -> QuestionResult:
        norm_qid = normalize_question_id(spec.question_id)
        seg = by_id.get(norm_qid.lower())
        if seg is None or not seg.text.strip():
            return _missing_answer_result(spec, ocr_confidence)

        authoritative_max = spec.max_score or evaluation_service.extract_authoritative_max_score(spec.rubric)
        rubric = dict(spec.rubric)
        rubric["max_score"] = authoritative_max

        evidence = evidence_by_id.get(norm_qid.lower())
        seg_ocr_confidence = evidence.ocr_confidence if evidence else ocr_confidence
        mapping_confidence = evidence.mapping_confidence if evidence else seg.mapping_confidence
        uncertain = is_uncertain_evidence(evidence, seg.text) if evidence else False

        image_bytes = None
        visual_fallback_used = False
        if (
            uncertain
            and visual_fallback_enabled
            and evidence is not None
            and evidence.bbox is not None
            and ocr is not None
            and ocr.image is not None
        ):
            try:
                image_bytes = crop_region(ocr.image, evidence.bbox)
                visual_fallback_used = True
            except Exception:
                logger.exception(
                    "Failed to crop answer region for %s; continuing OCR-text-only", norm_qid
                )
                image_bytes = None

        eval_kwargs = dict(
            question=spec.question,
            student_answer=seg.text,
            model_answer=spec.model_answer,
            rubric=rubric,
        )
        if evaluator_supports_evidence:
            eval_kwargs["ocr_confidence"] = seg_ocr_confidence
            eval_kwargs["image_bytes"] = image_bytes
        raw = evaluator(**eval_kwargs)

        # Enforce score clamping against authoritative rubric max
        score = min(float(authoritative_max), max(0.0, float(raw.get("score", 0.0))))
        raw["score"] = round(score, 2)
        raw["max_score"] = round(float(authoritative_max), 2)
        for subfield in ("concept_score", "accuracy_score", "precision_score", "technical_terminology_score"):
            raw[subfield] = round(min(float(authoritative_max), max(0.0, float(raw.get(subfield, 0.0)))), 2)

        ev_conf = _clamp01(raw.get("confidence", 0.0))
        combined = combine_confidence(ev_conf, seg_ocr_confidence)

        return QuestionResult(
            question_id=norm_qid,
            student_answer=seg.text,
            answer_detected=seg.detected,
            ocr_confidence=seg_ocr_confidence,
            combined_confidence=combined,
            needs_review=(combined < threshold) or uncertain,
            mapping_confidence=mapping_confidence,
            ocr_uncertain=uncertain,
            visual_fallback_used=visual_fallback_used,
            **raw,
        )

    max_workers = _max_evaluation_concurrency()
    if max_workers <= 1 or len(deduped_questions) <= 1:
        return [_evaluate_one(spec) for spec in deduped_questions]

    # Bounded concurrency: never more than max_workers in-flight Gemini
    # calls at once, regardless of how many questions the assessment has.
    # pool.map preserves input order in its output, so results stay aligned
    # with deduped_questions even though they may complete out of order.
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(_evaluate_one, deduped_questions))


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
        segmentation.segments, deduped, ocr.mean_confidence, evaluator=evaluator, ocr=ocr
    )
    return build_response(ocr, segmentation.segments, results)
