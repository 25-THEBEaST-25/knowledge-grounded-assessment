"""Tests for duplicate question handling and unmarked OCR answer fallback."""

from backend.app.schemas.handwritten import QuestionSpec
from backend.app.services import pipeline_service
from backend.app.services.ocr_service import OCRResult
from backend.app.services.segmentation_service import segment_answers


def fake_evaluator(question, student_answer, model_answer, rubric):
    return {
        "score": 8.0,
        "max_score": 10.0,
        "concept_score": 3.0,
        "accuracy_score": 3.0,
        "precision_score": 1.0,
        "technical_terminology_score": 1.0,
        "strengths": ["Good definition"],
        "missing_concepts": [],
        "feedback": "Well done",
        "confidence": 0.9,
    }


def test_duplicate_question_ids_deduplicated():
    """Duplicate question IDs in QuestionSpec are deduplicated and cannot double score."""
    questions = [
        QuestionSpec(question_id="Q1", question="Define osmosis", model_answer="...", rubric={"max_score": 10}),
        QuestionSpec(question_id="q1", question="Define osmosis", model_answer="...", rubric={"max_score": 10}),
        QuestionSpec(question_id="Q1", question="Define osmosis duplicate", model_answer="...", rubric={"max_score": 10}),
    ]

    deduped = pipeline_service.deduplicate_questions(questions)
    assert len(deduped) == 1
    assert deduped[0].question_id == "Q1"

    text = "Q1. Osmosis is the movement of water molecules."
    segmentation = segment_answers(text, expected_question_ids=[q.question_id for q in deduped])
    results = pipeline_service.evaluate_segments(segmentation.segments, questions, ocr_confidence=0.9, evaluator=fake_evaluator)

    # Should evaluate only once
    assert len(results) == 1
    assert results[0].score == 8.0

    resp = pipeline_service.build_response(
        OCRResult(text=text, mean_confidence=0.9, engine="fake"),
        segmentation.segments,
        results,
    )
    assert resp.total_score == 8.0
    assert resp.total_max_score == 10.0


def test_unmarked_ocr_answer_fallback_evaluated():
    """If student writes the answer directly without 'Q1.' marker, it is detected and evaluated."""
    text = "Photosynthesis is the biological process by which plants convert solar energy into chemical energy."
    # No explicit markers in text
    seg = segment_answers(text, expected_question_ids=["Q1"])
    assert len(seg.segments) == 1
    assert seg.segments[0].question_id == "Q1"
    assert seg.segments[0].detected is True
    assert "convert solar energy" in seg.segments[0].text

    spec = QuestionSpec(
        question_id="Q1",
        question="Describe photosynthesis",
        model_answer="Plants convert sunlight to chemical energy",
        rubric={"max_score": 10},
    )

    results = pipeline_service.evaluate_segments(seg.segments, [spec], ocr_confidence=0.95, evaluator=fake_evaluator)
    assert len(results) == 1
    assert results[0].answer_detected is True
    assert results[0].score == 8.0
    assert results[0].student_answer.startswith("Photosynthesis is")
