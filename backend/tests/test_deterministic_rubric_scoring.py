"""Tests for Deterministic Rubric Scoring (Requirement D).

Verifies application-code arithmetic, criterion and question caps,
and rejection of fabricated evidence from earning points.
"""

from backend.app.schemas.evaluator_contracts import CriterionClaim, EvaluatorOutput
from backend.app.services.rubric_scoring_service import (
    parse_rubric_criteria,
    score_rubric_deterministically,
)


def test_parse_rubric_criteria_preserves_total_max():
    rubric = {
        "criteria": [
            {"name": "Concept", "max_score": 4},
            {"name": "Accuracy", "max_score": 3},
            {"name": "Terminology", "max_score": 3},
        ]
    }
    specs = parse_rubric_criteria(rubric, authoritative_max=10.0)
    assert len(specs) == 3
    assert sum(s.max_score for s in specs) == 10.0


def test_scoring_enforces_criterion_caps_even_if_evaluator_exceeds():
    """An evaluator returning factor > 1.0 cannot award more than criterion max."""
    ev_output = EvaluatorOutput(
        evaluator_name="concept_text",
        status="success",
        confidence=1.0,
        claims=[
            CriterionClaim.model_construct(
                criterion_name="Concept",
                assessment="fulfilled",
                score_factor=1.5,  # Rogue factor bypassing pydantic validation
                reasoning="Superb",
                evidence_quotes=["Photosynthesis makes glucose"],
            )
        ],

    )

    rubric = {"criteria": [{"name": "Concept", "max_score": 5.0}]}
    student_ans = "Photosynthesis makes glucose from sunlight."

    results, total, flags = score_rubric_deterministically(
        rubric=rubric,
        student_answer=student_ans,
        evaluator_outputs={"concept_text": ev_output},
        explicit_max_score=5.0,
    )

    assert len(results) == 1
    assert results[0].awarded_score == 5.0  # Clamped to 5.0 max
    assert total == 5.0


def test_scoring_rejects_fabricated_evidence_quotes():
    """If an evaluator outputs evidence quotes not in the student's answer,

    the evidence is flagged as unverified and attainment factor is penalized.
    """
    ev_output = EvaluatorOutput(
        evaluator_name="concept_text",
        status="success",
        confidence=1.0,
        claims=[
            CriterionClaim(
                criterion_name="Concept",
                assessment="fulfilled",
                score_factor=1.0,
                reasoning="Claimed fulfillment",
                evidence_quotes=["A completely hallucinated quote that student never wrote"],
            )
        ],
    )

    rubric = {"criteria": [{"name": "Concept", "max_score": 10.0}]}
    student_ans = "I don't know the exact answer to this."

    results, total, flags = score_rubric_deterministically(
        rubric=rubric,
        student_answer=student_ans,
        evaluator_outputs={"concept_text": ev_output},
        explicit_max_score=10.0,
    )

    assert "unverified_evidence_detected" in flags
    assert results[0].verified_evidence is False
    assert results[0].awarded_score < 10.0


def test_empty_answer_scores_zero_deterministically():
    rubric = {
        "criteria": [
            {"name": "Concept", "max_score": 4},
            {"name": "Accuracy", "max_score": 6},
        ]
    }
    results, total, flags = score_rubric_deterministically(
        rubric=rubric,
        student_answer="",
        evaluator_outputs={},
        explicit_max_score=10.0,
    )

    assert total == 0.0
    assert all(r.awarded_score == 0.0 for r in results)
    assert all(r.attainment_factor == 0.0 for r in results)
