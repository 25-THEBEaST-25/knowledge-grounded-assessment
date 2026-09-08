"""Tests for per-question OCR evidence (A2/A3), uncertainty detection (A4),
the visual-fallback gate (A5), and bounded evaluation concurrency (A8) in
pipeline_service. None of these hit the real PaddleOCR/Gemini APIs.
"""

import threading
import time

from backend.app.schemas.handwritten import QuestionSpec
from backend.app.services import pipeline_service
from backend.app.services.ocr_service import OCRLine, OCRResult
from backend.app.services.segmentation_service import Segment, segment_answers


def _make_ocr(lines_text_conf_bbox, image=None) -> OCRResult:
    lines = [OCRLine(text=t, confidence=c, bbox=b) for t, c, b in lines_text_conf_bbox]
    text = "\n".join(l.text for l in lines)
    mean_conf = sum(l.confidence for l in lines) / len(lines) if lines else 0.0
    return OCRResult(text=text, lines=lines, mean_confidence=round(mean_conf, 4), engine="fake", image=image)


# ---------------------------------------------------------------------------
# A2/A3: per-question evidence
# ---------------------------------------------------------------------------


def test_build_answer_evidence_slices_lines_and_averages_confidence():
    ocr = _make_ocr(
        [
            ("Q1. answer line one", 0.9, [0, 0, 100, 10]),
            ("continued line two", 0.7, [0, 12, 90, 22]),
            ("Q2. next answer", 0.95, [0, 24, 80, 34]),
        ]
    )
    segmentation = segment_answers(ocr.text)
    evidence = pipeline_service.build_answer_evidence(segmentation.segments, ocr)

    q1 = evidence["q1"]
    assert q1.line_count == 2
    assert q1.ocr_confidence == round((0.9 + 0.7) / 2, 4)
    assert q1.bbox == [0, 0, 100, 22]  # union of the two Q1 lines' boxes

    q2 = evidence["q2"]
    assert q2.line_count == 1
    assert q2.ocr_confidence == 0.95


def test_build_answer_evidence_handles_undetected_segment_with_no_lines():
    ocr = _make_ocr([("Q1. only question present", 0.9, [0, 0, 50, 10])])
    segmentation = segment_answers(ocr.text, expected_question_ids=["Q1", "Q2"])
    evidence = pipeline_service.build_answer_evidence(segmentation.segments, ocr)

    q2 = evidence["q2"]
    assert q2.line_count == 0
    assert q2.bbox is None
    assert q2.mapping_confidence == 0.0


# ---------------------------------------------------------------------------
# A4: uncertainty detection
# ---------------------------------------------------------------------------


def test_uncertain_when_ocr_confidence_low():
    ev = pipeline_service.AnswerEvidence("Q1", ocr_confidence=0.3, line_count=2, bbox=[0, 0, 1, 1], mapping_confidence=1.0, marker_detected=True)
    assert pipeline_service.is_uncertain_evidence(ev, "a reasonably long answer here") is True


def test_uncertain_when_mapping_confidence_low():
    ev = pipeline_service.AnswerEvidence("Q1", ocr_confidence=0.95, line_count=2, bbox=[0, 0, 1, 1], mapping_confidence=0.5, marker_detected=False)
    assert pipeline_service.is_uncertain_evidence(ev, "a reasonably long answer here") is True


def test_uncertain_when_answer_suspiciously_short():
    ev = pipeline_service.AnswerEvidence("Q1", ocr_confidence=0.95, line_count=1, bbox=[0, 0, 1, 1], mapping_confidence=1.0, marker_detected=True)
    assert pipeline_service.is_uncertain_evidence(ev, "ok") is True


def test_not_uncertain_when_everything_looks_clean():
    ev = pipeline_service.AnswerEvidence("Q1", ocr_confidence=0.95, line_count=3, bbox=[0, 0, 1, 1], mapping_confidence=1.0, marker_detected=True)
    assert pipeline_service.is_uncertain_evidence(ev, "a clear, complete, well-detected answer") is False


# ---------------------------------------------------------------------------
# needs_review reflects uncertainty even when confidence alone would pass
# ---------------------------------------------------------------------------


def _confident_evaluator(**kwargs):
    return {
        "score": 9, "max_score": 10, "concept_score": 4, "accuracy_score": 3,
        "precision_score": 1, "technical_terminology_score": 1,
        "strengths": ["good"], "missing_concepts": [], "feedback": "great",
        "confidence": 0.95,
    }


def test_needs_review_true_for_uncertain_evidence_even_with_high_confidence():
    # Two lines, but low OCR confidence -> uncertain, despite a confident evaluator.
    ocr = _make_ocr([("Q1. short", 0.2, [0, 0, 50, 10])])
    spec = QuestionSpec(question_id="Q1", question="Q", model_answer="M", rubric={"max_score": 10})
    segmentation = segment_answers(ocr.text)

    results = pipeline_service.evaluate_segments(
        segmentation.segments, [spec], ocr.mean_confidence, evaluator=_confident_evaluator, ocr=ocr
    )
    assert results[0].ocr_uncertain is True
    assert results[0].needs_review is True  # flagged, not penalized
    assert results[0].score == 9  # the evaluator's real score is untouched


def test_needs_review_false_for_clean_confident_evidence():
    ocr = _make_ocr(
        [
            ("Q1. a full, clearly written, confidently OCR'd answer here", 0.97, [0, 0, 300, 10]),
        ]
    )
    spec = QuestionSpec(question_id="Q1", question="Q", model_answer="M", rubric={"max_score": 10})
    segmentation = segment_answers(ocr.text)

    results = pipeline_service.evaluate_segments(
        segmentation.segments, [spec], ocr.mean_confidence, evaluator=_confident_evaluator, ocr=ocr
    )
    assert results[0].ocr_uncertain is False
    assert results[0].needs_review is False


# ---------------------------------------------------------------------------
# A5: visual fallback gate
# ---------------------------------------------------------------------------


def test_visual_fallback_triggers_image_bytes_when_uncertain(monkeypatch):
    monkeypatch.setenv("VISUAL_FALLBACK_ENABLED", "true")
    import numpy as np

    fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
    ocr = _make_ocr([("Q1. faint", 0.2, [5, 5, 40, 15])], image=fake_image)
    spec = QuestionSpec(question_id="Q1", question="Q", model_answer="M", rubric={"max_score": 10})
    segmentation = segment_answers(ocr.text)

    captured = {}

    def evaluator(question, student_answer, model_answer, rubric, ocr_confidence, image_bytes):
        captured["image_bytes"] = image_bytes
        return _confident_evaluator()

    pipeline_service.evaluate_segments(segmentation.segments, [spec], ocr.mean_confidence, evaluator=evaluator, ocr=ocr)
    assert captured["image_bytes"] is not None


def test_visual_fallback_not_used_when_confidence_is_fine(monkeypatch):
    monkeypatch.setenv("VISUAL_FALLBACK_ENABLED", "true")
    import numpy as np

    fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
    ocr = _make_ocr(
        [("Q1. a full, clearly written, confidently OCR'd answer here", 0.97, [5, 5, 300, 15])], image=fake_image
    )
    spec = QuestionSpec(question_id="Q1", question="Q", model_answer="M", rubric={"max_score": 10})
    segmentation = segment_answers(ocr.text)

    captured = {}

    def evaluator(question, student_answer, model_answer, rubric, ocr_confidence, image_bytes):
        captured["image_bytes"] = image_bytes
        return _confident_evaluator()

    pipeline_service.evaluate_segments(segmentation.segments, [spec], ocr.mean_confidence, evaluator=evaluator, ocr=ocr)
    assert captured["image_bytes"] is None  # no visual fallback needed -- OCR was fine


def test_visual_fallback_disabled_via_env_even_when_uncertain(monkeypatch):
    monkeypatch.setenv("VISUAL_FALLBACK_ENABLED", "false")
    import numpy as np

    fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
    ocr = _make_ocr([("Q1. faint", 0.2, [5, 5, 40, 15])], image=fake_image)
    spec = QuestionSpec(question_id="Q1", question="Q", model_answer="M", rubric={"max_score": 10})
    segmentation = segment_answers(ocr.text)

    captured = {}

    def evaluator(question, student_answer, model_answer, rubric, ocr_confidence, image_bytes):
        captured["image_bytes"] = image_bytes
        return _confident_evaluator()

    pipeline_service.evaluate_segments(segmentation.segments, [spec], ocr.mean_confidence, evaluator=evaluator, ocr=ocr)
    assert captured["image_bytes"] is None


# ---------------------------------------------------------------------------
# A8: bounded concurrency
# ---------------------------------------------------------------------------


def test_concurrent_evaluation_never_exceeds_configured_bound(monkeypatch):
    monkeypatch.setenv("MAX_EVALUATION_CONCURRENCY", "2")
    in_flight = {"current": 0, "max_seen": 0}
    lock = threading.Lock()

    def slow_evaluator(**kwargs):
        with lock:
            in_flight["current"] += 1
            in_flight["max_seen"] = max(in_flight["max_seen"], in_flight["current"])
        time.sleep(0.05)
        with lock:
            in_flight["current"] -= 1
        return _confident_evaluator()

    specs = [QuestionSpec(question_id=f"Q{i}", question="Q", model_answer="M", rubric={"max_score": 10}) for i in range(1, 6)]
    segments = [Segment(question_id=f"Q{i}", text=f"answer {i}", start_line=0, end_line=0) for i in range(1, 6)]

    pipeline_service.evaluate_segments(segments, specs, ocr_confidence=0.9, evaluator=slow_evaluator)
    assert in_flight["max_seen"] <= 2
    assert in_flight["max_seen"] > 1  # actually ran concurrently, not accidentally serial


def test_concurrent_results_preserve_question_order(monkeypatch):
    monkeypatch.setenv("MAX_EVALUATION_CONCURRENCY", "3")

    def variable_delay_evaluator(**kwargs):
        # Later questions finish first, to prove ordering isn't just luck.
        qnum = int(kwargs["question"].split()[-1])
        time.sleep(0.02 * (5 - qnum))
        return {**_confident_evaluator(), "feedback": f"done {qnum}"}

    specs = [QuestionSpec(question_id=f"Q{i}", question=f"question {i}", model_answer="M", rubric={"max_score": 10}) for i in range(1, 5)]
    segments = [Segment(question_id=f"Q{i}", text=f"answer {i}", start_line=0, end_line=0) for i in range(1, 5)]

    results = pipeline_service.evaluate_segments(segments, specs, ocr_confidence=0.9, evaluator=variable_delay_evaluator)
    assert [r.question_id for r in results] == ["Q1", "Q2", "Q3", "Q4"]


def test_concurrency_of_one_runs_fully_sequential(monkeypatch):
    monkeypatch.setenv("MAX_EVALUATION_CONCURRENCY", "1")
    in_flight = {"current": 0, "max_seen": 0}
    lock = threading.Lock()

    def slow_evaluator(**kwargs):
        with lock:
            in_flight["current"] += 1
            in_flight["max_seen"] = max(in_flight["max_seen"], in_flight["current"])
        time.sleep(0.02)
        with lock:
            in_flight["current"] -= 1
        return _confident_evaluator()

    specs = [QuestionSpec(question_id=f"Q{i}", question="Q", model_answer="M", rubric={"max_score": 10}) for i in range(1, 4)]
    segments = [Segment(question_id=f"Q{i}", text=f"answer {i}", start_line=0, end_line=0) for i in range(1, 4)]

    pipeline_service.evaluate_segments(segments, specs, ocr_confidence=0.9, evaluator=slow_evaluator)
    assert in_flight["max_seen"] == 1
