"""Tests for deterministic Question ID normalization and marker handling."""

from backend.app.services.segmentation_service import (
    match_marker,
    normalize_question_id,
    segment_answers,
)


def test_normalize_question_id_variants():
    """Verify various question formats normalize deterministically."""
    # Standard and case variants
    assert normalize_question_id("Q1") == "Q1"
    assert normalize_question_id("q1") == "Q1"
    assert normalize_question_id("Q 1") == "Q1"
    assert normalize_question_id("Question 1") == "Q1"
    assert normalize_question_id("Que 1") == "Q1"
    assert normalize_question_id("Ques 1") == "Q1"
    assert normalize_question_id("Qn 1") == "Q1"

    # OCR noise variants (l / I -> 1, O / o -> 0)
    assert normalize_question_id("Ql") == "Q1"
    assert normalize_question_id("QI") == "Q1"
    assert normalize_question_id("Q1O") == "Q10"
    assert normalize_question_id("0.1") == "Q1"
    assert normalize_question_id("0 2") == "Q2"

    # Numbered / separator forms
    assert normalize_question_id("1.") == "Q1"
    assert normalize_question_id("1)") == "Q1"
    assert normalize_question_id("(1)") == "Q1"
    assert normalize_question_id("1:") == "Q1"
    assert normalize_question_id("Ans 1") == "Q1"
    assert normalize_question_id("Answer 1") == "Q1"

    # Subquestion variants
    assert normalize_question_id("Q1(a)") == "Q1a"
    assert normalize_question_id("Q1(A)") == "Q1a"
    assert normalize_question_id("Q1a") == "Q1a"
    assert normalize_question_id("q1a") == "Q1a"
    assert normalize_question_id("1(a)") == "Q1a"
    assert normalize_question_id("1(A)") == "Q1a"
    assert normalize_question_id("1a.") == "Q1a"
    assert normalize_question_id("Q1(i)") == "Q1i"
    assert normalize_question_id("1(iv)") == "Q1iv"


def test_match_marker_handles_noisy_separators():
    assert match_marker("1.Photosynthesis is process") == ("Q1", "Photosynthesis is process")
    assert match_marker("1) Photosynthesis") == ("Q1", "Photosynthesis")
    assert match_marker("Q1(a) Mitochondria") == ("Q1a", "Mitochondria")
    assert match_marker("Q1(A) Mitochondria") == ("Q1a", "Mitochondria")
    assert match_marker("Question 2: Osmosis") == ("Q2", "Osmosis")
    assert match_marker("Ans 3 - Diffusion") == ("Q3", "Diffusion")


def test_segmentation_with_mixed_subquestion_formats():
    text = """Q1(A) First part of answer
1(b) Second part of answer
Q2. Complete answer two"""
    res = segment_answers(text, expected_question_ids=["Q1a", "Q1(b)", "Question 2"])
    assert res.question_ids == ["Q1a", "Q1b", "Q2"]
    assert "First part" in res.segments[0].text
    assert "Second part" in res.segments[1].text
    assert "Complete answer" in res.segments[2].text
