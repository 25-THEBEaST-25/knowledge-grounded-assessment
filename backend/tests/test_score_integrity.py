"""Tests for score integrity and rubric max score clamping."""

from backend.app.schemas.handwritten import QuestionSpec
from backend.app.services import evaluation_service, pipeline_service
from backend.app.services.segmentation_service import Segment


def test_score_never_exceeds_rubric_max():
    """Even if the model returns a score higher than rubric max, it is clamped."""
    def rogue_evaluator(question, student_answer, model_answer, rubric):
        # Rogue model attempts to award 15 out of 10
        return {
            "score": 15.0,
            "max_score": 100.0,
            "concept_score": 20.0,
            "accuracy_score": 20.0,
            "precision_score": 20.0,
            "technical_terminology_score": 20.0,
            "strengths": ["Everything"],
            "missing_concepts": [],
            "feedback": "Flawless",
            "confidence": 0.95,
        }

    spec = QuestionSpec(
        question_id="Q1",
        question="What is photosynthesis?",
        model_answer="Process converting light to energy",
        rubric={"max_score": 10},
    )

    seg = Segment(question_id="Q1", text="Converts light", start_line=0, end_line=1)
    results = pipeline_service.evaluate_segments([seg], [spec], ocr_confidence=0.9, evaluator=rogue_evaluator)

    assert len(results) == 1
    assert results[0].score == 10.0
    assert results[0].max_score == 10.0


def test_negative_score_clamped_to_zero():
    """Model returning negative score is clamped to 0.0."""
    def negative_evaluator(question, student_answer, model_answer, rubric):
        return {
            "score": -5.0,
            "max_score": 10.0,
            "concept_score": -1.0,
            "accuracy_score": 0.0,
            "precision_score": 0.0,
            "technical_terminology_score": 0.0,
            "strengths": [],
            "missing_concepts": ["All"],
            "feedback": "Terrible",
            "confidence": 0.5,
        }

    spec = QuestionSpec(
        question_id="Q1",
        question="Explain mitosis",
        model_answer="Cell division",
        rubric={"max_score": 5},
    )

    seg = Segment(question_id="Q1", text="Wrong answer", start_line=0, end_line=1)
    results = pipeline_service.evaluate_segments([seg], [spec], ocr_confidence=0.9, evaluator=negative_evaluator)

    assert len(results) == 1
    assert results[0].score == 0.0
    assert results[0].max_score == 5.0


def test_rubric_max_score_extraction():
    """Verify various rubric formats are extracted correctly."""
    assert evaluation_service.extract_authoritative_max_score({"max_score": 15}) == 15.0
    assert evaluation_service.extract_authoritative_max_score({"total_marks": 20}) == 20.0
    assert evaluation_service.extract_authoritative_max_score({"max_marks": "8"}) == 8.0
    assert evaluation_service.extract_authoritative_max_score({
        "criteria": [
            {"name": "Concept", "max_score": 4},
            {"name": "Accuracy", "max_score": 6},
        ]
    }) == 10.0
    assert evaluation_service.extract_authoritative_max_score({}) == 10.0
