"""Tests for Specialized Evaluators (Requirement B).

Tests Concept, Accuracy/Math, Code, and Diagram/Visual evaluators.
Verifies structured outputs, verified quote extraction, and modality gating.
"""

from backend.app.services.evaluators import (
    AccuracyMathEvaluator,
    CodeEvaluator,
    ConceptEvaluator,
    DiagramVisualEvaluator,
    extract_verifiable_quotes,
)


def test_verifiable_quotes_extraction():
    student_text = "The quick brown fox jumps over the lazy dog."
    candidates = [
        "quick brown fox",
        "totally fabricated sentence that is not there",
        "jumps over the lazy dog",
    ]
    verified = extract_verifiable_quotes(student_text, candidates)
    assert "quick brown fox" in verified
    assert "jumps over the lazy dog" in verified
    assert "totally fabricated sentence that is not there" not in verified


def test_concept_evaluator_identifies_terms_and_evidence():
    evaluator = ConceptEvaluator()
    out = evaluator.evaluate(
        question="What is photosynthesis?",
        student_answer="Photosynthesis is the process where plants convert sunlight and carbon dioxide into glucose.",
        model_answer="Photosynthesis converts sunlight, water, and carbon dioxide into glucose and oxygen.",
        rubric={"max_score": 10},
    )

    assert out.status == "success"
    assert out.confidence >= 0.7
    assert "photosynthesis" in [t.lower() for t in out.key_terms_present]
    assert "glucose" in [t.lower() for t in out.key_terms_present]
    assert len(out.evidence) > 0
    assert len(out.claims) >= 1
    assert out.claims[0].score_factor >= 0.7


def test_accuracy_math_evaluator_validates_calculations():
    evaluator = AccuracyMathEvaluator()
    out = evaluator.evaluate(
        question="Find the area of a circle with radius 5 cm. (pi = 3.14)",
        student_answer="Area = 3.14 * 5 * 5 = 78.5 square cm.",
        model_answer="Area is 78.5 cm^2.",
        rubric={"max_score": 5},
    )

    assert out.status == "success"
    assert len(out.claims) >= 1
    assert out.claims[0].score_factor >= 0.8
    assert "78.5" in str(out.metadata.get("expected_numbers"))


def test_accuracy_math_evaluator_penalizes_wrong_numbers():
    evaluator = AccuracyMathEvaluator()
    out = evaluator.evaluate(
        question="Calculate 25 * 4",
        student_answer="25 * 4 is 999",
        model_answer="100",
        rubric={"max_score": 5},
    )

    assert out.status == "success"
    assert out.claims[0].score_factor < 0.4
    assert out.claims[0].assessment == "incorrect"


def test_code_evaluator_validates_python_syntax():
    evaluator = CodeEvaluator()
    out = evaluator.evaluate(
        question="Write a function to return the square of a number.",
        student_answer="def square(x):\n    return x * x",
        model_answer="def square(n):\n    return n ** 2",
        rubric={"max_score": 5},
    )

    assert out.status == "success"
    assert out.metadata.get("syntax_valid") is True
    assert out.claims[0].score_factor >= 0.8


def test_code_evaluator_detects_syntax_errors():
    evaluator = CodeEvaluator()
    out = evaluator.evaluate(
        question="Write a function to return x plus 1.",
        student_answer="def broken_func(x:\n  return x + 1",
        model_answer="def broken_func(x):\n  return x + 1",
        rubric={"max_score": 5},
    )

    assert out.status == "success"
    assert out.metadata.get("syntax_valid") is False
    assert out.claims[0].score_factor <= 0.75


def test_code_evaluator_skips_non_coding_questions():
    evaluator = CodeEvaluator()
    out = evaluator.evaluate(
        question="Explain the causes of the French Revolution.",
        student_answer="Economic crisis and social inequality.",
        model_answer="Feudal system oppression and financial crisis.",
        rubric={"max_score": 5},
    )
    assert out.status == "skipped"


def test_diagram_evaluator_strictly_skips_when_image_absent():
    evaluator = DiagramVisualEvaluator()
    out = evaluator.evaluate(
        question="Draw the flowchart of binary search algorithm.",
        student_answer="Binary search divides the array in half.",
        model_answer="Flowchart showing start, mid calculation, comparison, branch.",
        rubric={"max_score": 10},
        image_bytes=None,  # No image
    )

    assert out.status == "skipped"
    assert "no image" in out.observations[0].lower()
    assert out.claims[0].score_factor == 0.0


def test_diagram_evaluator_evaluates_when_image_present():
    evaluator = DiagramVisualEvaluator()
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
    out = evaluator.evaluate(
        question="Draw the block diagram of a microcontroller.",
        student_answer="Diagram showing CPU, RAM, ROM, and I/O ports.",
        model_answer="Block diagram including CPU, Memory, and Peripherals.",
        rubric={"max_score": 10},
        image_bytes=fake_png,
    )

    assert out.status == "success"
    assert out.claims[0].score_factor >= 0.7
    assert "visual answer provided" in out.claims[0].reasoning.lower()
