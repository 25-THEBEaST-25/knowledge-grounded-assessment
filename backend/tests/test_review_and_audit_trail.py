"""Tests for Review and Audit Trail (Requirement E).

Verifies contradiction detection, audit flags, evaluation trace structure,
and persistence of audit logs.
"""

from backend.app.schemas.evaluator_contracts import CriterionClaim, EvaluatorOutput
from backend.app.services.orchestrator_service import (
    detect_contradictions,
    evaluate_with_orchestrator,
    get_trace,
)


def test_contradiction_detection_between_concept_and_accuracy():
    # Concept evaluator claims high attainment, but accuracy evaluator finds critical calculation failure
    outputs = {
        "concept_text": EvaluatorOutput(
            evaluator_name="concept_text",
            status="success",
            confidence=0.9,
            claims=[
                CriterionClaim(
                    criterion_name="Conceptual Understanding",
                    assessment="fulfilled",
                    score_factor=0.9,
                    reasoning="Understands physics concepts well",
                    evidence_quotes=[],
                )
            ],
        ),
        "accuracy_math": EvaluatorOutput(
            evaluator_name="accuracy_math",
            status="success",
            confidence=0.9,
            claims=[
                CriterionClaim(
                    criterion_name="Mathematical Accuracy",
                    assessment="incorrect",
                    score_factor=0.1,
                    reasoning="Calculation is off by a factor of 100",
                    evidence_quotes=[],
                )
            ],
        ),
    }

    contradictions = detect_contradictions(outputs)
    assert len(contradictions) >= 1
    assert "accuracy" in contradictions[0].lower() or "calculation" in contradictions[0].lower()


def test_audit_flags_triggered_on_contradiction():
    # Construct an assessment that exhibits contradiction
    result = evaluate_with_orchestrator(
        assessment_id="as_physics",
        question_id="Q1",
        question="Calculate kinetic energy where m=10kg and v=2m/s. Formula is KE = 0.5 * m * v^2.",
        student_answer="Kinetic energy is the energy of motion given by half mass times velocity squared. KE = 99999 Joules.",
        model_answer="KE = 0.5 * 10 * 4 = 20 Joules.",
        rubric={
            "criteria": [
                {"name": "Concept", "max_score": 5},
                {"name": "Calculation Accuracy", "max_score": 5},
            ]
        },
    )

    assert result["needs_review"] is True
    trace = result["evaluation_trace"]
    assert "evaluator_contradiction_detected" in trace["review_flags"]


def test_evaluation_trace_is_persisted_and_retrievable():
    result = evaluate_with_orchestrator(
        assessment_id="as_audit_test",
        question_id="Q2",
        question="Define recursion.",
        student_answer="Recursion is a process where a function calls itself directly or indirectly until a base case.",
        model_answer="Recursion is when a function calls itself until reaching a base condition.",
        rubric={"max_score": 5},
    )

    trace_id = result["evaluation_trace"]["trace_id"]
    retrieved_trace = get_trace(trace_id)

    assert retrieved_trace is not None
    assert retrieved_trace.trace_id == trace_id
    assert retrieved_trace.question_id.upper() == "Q2"
    assert len(retrieved_trace.criteria_breakdown) >= 1
    assert retrieved_trace.execution_time_ms >= 0
