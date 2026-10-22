import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.evaluator_contracts import CriterionScoreResult, EvaluationTrace
from backend.app.services.orchestrator_service import store_trace


client = TestClient(app)


def test_evaluation_api_serializes_real_orchestrator_response_shape(monkeypatch):
    """Regression test for HTTP 500 ResponseValidationError on POST /evaluation/evaluate.

    Proves that criteria_breakdown formatted as a List[CriterionScoreResult] (or dicts)
    and evaluation_trace serialize without error.
    """
    import backend.app.api.evaluation as eval_api

    criterion_1 = CriterionScoreResult(
        criterion_name="Photosynthesis Concept",
        max_score=6.0,
        awarded_score=5.0,
        attainment_factor=0.8333,
        reasoning="Correctly identified solar to chemical energy conversion.",
        evaluator_name="concept_text",
        evidence_used=["convert sunlight to chemical energy"],
        verified_evidence=True,
    )
    criterion_2 = CriterionScoreResult(
        criterion_name="Chemical Formula & Details",
        max_score=4.0,
        awarded_score=3.0,
        attainment_factor=0.75,
        reasoning="Key terms present but light-dependent reactions not fully detailed.",
        evaluator_name="concept_text",
        evidence_used=["plants convert sunlight"],
        verified_evidence=True,
    )

    trace = EvaluationTrace(
        trace_id="tr-regression-test-001",
        question_id="demo-question",
        routing_reasons={"concept_text": "Core conceptual understanding."},
        evaluators_run=["concept_text"],
        evaluators_failed=[],
        retrieval_sources=[],
        criteria_breakdown=[criterion_1, criterion_2],
        review_flags=[],
        execution_time_ms=12.5,
    )
    store_trace(trace)

    real_orchestrator_shape = {
        "score": 8.0,
        "max_score": 10.0,
        "concept_score": 8.0,
        "accuracy_score": 0.0,
        "precision_score": 0.0,
        "technical_terminology_score": 0.0,
        "strengths": ["Identified sunlight conversion"],
        "missing_concepts": ["chlorophyll", "ATP"],
        "feedback": "Evaluated across 2 rubric criteria.",
        "confidence": 0.88,
        "combined_confidence": 0.88,
        "ocr_confidence": 1.0,
        "needs_review": False,
        "mapping_confidence": 1.0,
        "ocr_uncertain": False,
        "visual_fallback_used": False,
        "criteria_breakdown": [criterion_1.model_dump(), criterion_2.model_dump()],
        "evaluation_trace": trace.model_dump(),
    }

    monkeypatch.setattr(
        eval_api,
        "evaluate_with_orchestrator",
        lambda **kwargs: real_orchestrator_shape,
    )

    payload = {
        "question": "Explain photosynthesis.",
        "student_answer": "Plants convert sunlight to chemical energy.",
        "model_answer": "Plants convert solar energy into sugars using chlorophyll.",
        "rubric": {
            "criteria": [
                {"name": "Photosynthesis Concept", "max_score": 6.0},
                {"name": "Chemical Formula & Details", "max_score": 4.0},
            ]
        },
        "assessment_id": "test-assess",
        "question_id": "Q1",
    }

    response = client.post("/evaluation/evaluate", json=payload)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["score"] == 8.0
    assert data["max_score"] == 10.0
    assert isinstance(data["criteria_breakdown"], list)
    assert len(data["criteria_breakdown"]) == 2
    assert data["criteria_breakdown"][0]["criterion_name"] == "Photosynthesis Concept"
    assert data["criteria_breakdown"][0]["awarded_score"] == 5.0
    assert data["criteria_breakdown"][1]["criterion_name"] == "Chemical Formula & Details"
    assert data["evaluation_trace"]["trace_id"] == "tr-regression-test-001"


def test_get_evaluation_trace_endpoint():
    """Verify GET /evaluation/trace/{trace_id} works and does not raise NameError for get_trace."""
    trace_id = "tr-trace-endpoint-test"
    trace = EvaluationTrace(
        trace_id=trace_id,
        question_id="Q2",
        routing_reasons={"concept_text": "text evaluation"},
        evaluators_run=["concept_text"],
        evaluators_failed=[],
        retrieval_sources=[],
        criteria_breakdown=[],
        review_flags=[],
        execution_time_ms=5.0,
    )
    store_trace(trace)

    res = client.get(f"/evaluation/trace/{trace_id}")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["trace_id"] == trace_id
    assert data["question_id"] == "Q2"

    res_404 = client.get("/evaluation/trace/non-existent-trace-id")
    assert res_404.status_code == 404
