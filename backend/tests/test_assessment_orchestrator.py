"""Tests for the Assessment Orchestrator (Requirement A).

Verifies dynamic evaluator selection, evaluator failure isolation,
routing reason tracking, and separation of orchestration from grading.
"""

import pytest

from backend.app.schemas.evaluator_contracts import EvaluatorOutput
from backend.app.services.orchestrator_service import AssessmentOrchestrator, evaluate_with_orchestrator


def test_select_evaluators_routes_text_question_to_concept():
    orch = AssessmentOrchestrator()
    selected, reasons = orch.select_evaluators(
        question="Explain the greenhouse effect and solar radiation absorption.",
        model_answer="Atmospheric gases trap infrared radiation, warming the surface.",
        rubric={"max_score": 5},
    )
    assert "concept_text" in selected
    assert "accuracy_math" not in selected
    assert "code" not in selected
    assert "diagram_visual" not in selected
    assert "concept_text" in reasons


def test_select_evaluators_routes_math_question_to_accuracy_math():
    orch = AssessmentOrchestrator()
    selected, reasons = orch.select_evaluators(
        question="Calculate the kinetic energy of a 10 kg mass moving at 5 m/s. Formula: KE = 0.5 * m * v^2",
        model_answer="KE = 0.5 * 10 * 25 = 125 Joules.",
        rubric={"max_score": 10},
    )
    assert "concept_text" in selected
    assert "accuracy_math" in selected
    assert "code" not in selected
    assert "accuracy_math" in reasons
    assert "formula" in reasons["accuracy_math"].lower() or "calculation" in reasons["accuracy_math"].lower()


def test_select_evaluators_routes_code_question_to_code():
    orch = AssessmentOrchestrator()
    selected, reasons = orch.select_evaluators(
        question="Implement a Python function to compute the factorial of n using a loop.",
        model_answer="def factorial(n):\n    res = 1\n    for i in range(1, n+1):\n        res *= i\n    return res",
        rubric={"max_score": 10},
    )
    assert "concept_text" in selected
    assert "code" in selected
    assert "code" in reasons


def test_select_evaluators_routes_diagram_question():
    orch = AssessmentOrchestrator()
    selected, reasons = orch.select_evaluators(
        question="Draw the block diagram of the OSI 7-layer architecture.",
        model_answer="Physical, Data Link, Network, Transport, Session, Presentation, Application.",
        rubric={"max_score": 10},
        image_bytes=b"fake_image_bytes",
    )
    assert "diagram_visual" in selected
    assert "diagram_visual" in reasons


def test_orchestrator_isolates_evaluator_failure():
    """If one evaluator crashes, other evaluators still succeed and failure is recorded."""
    orch = AssessmentOrchestrator()

    class CrashingEvaluator:
        name = "accuracy_math"

        def evaluate(self, *args, **kwargs):
            raise RuntimeError("Database connection timed out in math engine")

    orch.evaluators["accuracy_math"] = CrashingEvaluator()

    res = orch.orchestrate_question(
        assessment_id="test_assessment",
        question_id="Q1",
        question="Calculate 2 + 2",
        student_answer="The answer is 4",
        model_answer="4",
        rubric={"max_score": 5},
        selected_evaluators=["concept_text", "accuracy_math"],
        routing_reasons={"concept_text": "concept", "accuracy_math": "math"},
    )

    assert "accuracy_math" in res.failures
    assert res.evaluator_outputs["accuracy_math"].status == "failed"
    assert "Database connection timed out" in str(res.evaluator_outputs["accuracy_math"].error)
    # concept_text should still succeed
    assert res.evaluator_outputs["concept_text"].status == "success"


def test_evaluate_with_orchestrator_returns_complete_trace_and_criteria():
    res = evaluate_with_orchestrator(
        assessment_id="as_unit_1",
        question_id="Q1",
        question="Explain Newton's second law of motion and state the formula.",
        student_answer="Force equals mass times acceleration: F = m * a.",
        model_answer="Newton's second law states that Force = mass * acceleration (F = ma).",
        rubric={
            "criteria": [
                {"name": "Concept of Second Law", "max_score": 5},
                {"name": "Formula Accuracy", "max_score": 5},
            ]
        },
    )

    assert "score" in res
    assert "criteria_breakdown" in res
    assert "evaluation_trace" in res
    assert len(res["criteria_breakdown"]) == 2
    assert res["evaluation_trace"]["trace_id"].startswith("tr-")
    assert "concept_text" in res["evaluation_trace"]["evaluators_run"]
    assert res["score"] <= 10.0
