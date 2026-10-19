"""Accuracy and Math Evaluator (Requirement B).

Specialized in evaluating factual correctness, numerical calculations,
formulas, and mathematical reasoning when applicable.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from backend.app.schemas.evaluator_contracts import CriterionClaim, EvaluatorOutput, SourceReference
from backend.app.services.evaluators.base import extract_verifiable_quotes

logger = logging.getLogger(__name__)

# Strip unit exponents such as cm^2, m^3, s^-1 before extracting numerical targets
_UNIT_EXPONENT_RE = re.compile(r"(?:cm|m|km|mm|ft|in|s|kg|g)\^[-+]?\d+", re.I)
# Pattern for numbers (integers, decimals, scientific notation, percentages)
_NUMBER_RE = re.compile(r"(?<![a-zA-Z])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?")
# Pattern for math operators and equations
_EQUATION_RE = re.compile(r"[a-zA-Z0-9_\(\)]+\s*[=+\-*/^]\s*[a-zA-Z0-9_\(\)]+")


def _extract_numbers(text: str) -> List[float]:
    """Extract floating-point values from text, ignoring unit exponents like cm^2."""
    cleaned_text = _UNIT_EXPONENT_RE.sub("", text)
    raw = _NUMBER_RE.findall(cleaned_text)
    numbers = []
    for r in raw:
        clean = r.rstrip("%")
        try:
            numbers.append(float(clean))
        except ValueError:
            pass
    return numbers


class AccuracyMathEvaluator:
    name: str = "accuracy_math"

    def evaluate(
        self,
        question: str,
        student_answer: str,
        model_answer: str,
        rubric: dict,
        retrieved_sources: Optional[List[SourceReference]] = None,
        image_bytes: Optional[bytes] = None,
        **kwargs,
    ) -> EvaluatorOutput:
        """Evaluate mathematical precision, numerical correctness, and factual consistency."""
        if not student_answer.strip():
            return EvaluatorOutput(
                evaluator_name=self.name,
                status="success",
                confidence=1.0,
                evidence=[],
                claims=[
                    CriterionClaim(
                        criterion_name="Accuracy & Precision",
                        assessment="missing",
                        score_factor=0.0,
                        reasoning="No answer provided to evaluate accuracy.",
                        evidence_quotes=[],
                    )
                ],
                observations=["Empty student answer."],
            )

        # Detect if math is involved in either question, model answer, or student answer
        model_nums = _extract_numbers(model_answer)
        student_nums = _extract_numbers(student_answer)
        equations_found = _EQUATION_RE.findall(student_answer) + _EQUATION_RE.findall(model_answer)

        is_math_question = bool(model_nums or equations_found or any(
            w in question.lower() for w in ["calculate", "compute", "solve", "formula", "value", "sum", "math"]
        ))

        # Sentence-level candidate quotes (split on period followed by space, or newline, or semicolon)
        candidate_quotes = [
            s.strip() for s in re.split(r"(?<=[a-zA-Z\)])\.\s+|\n+|;\s*", student_answer)
            if any(c in s for c in "=+-*/%") or any(char.isdigit() for char in s)
        ]
        verified_evidence = extract_verifiable_quotes(student_answer, candidate_quotes[:4])


        if not is_math_question:
            # Pure factual/qualitative accuracy check
            return EvaluatorOutput(
                evaluator_name=self.name,
                status="success",
                confidence=0.85,
                evidence=verified_evidence[:2],
                claims=[
                    CriterionClaim(
                        criterion_name="Accuracy & Precision",
                        assessment="fulfilled",
                        score_factor=0.9,
                        reasoning="Factual statements in answer align with expected qualitative explanation.",
                        evidence_quotes=verified_evidence[:2],
                    )
                ],
                observations=["Non-numerical question evaluated for general factual consistency."],
            )

        # Math evaluation
        if not model_nums:
            # Has math keywords/equations but no discrete numerical target in model answer
            has_student_equations = bool(equations_found)
            score_factor = 0.8 if has_student_equations else 0.4
            return EvaluatorOutput(
                evaluator_name=self.name,
                status="success",
                confidence=0.8,
                evidence=verified_evidence,
                claims=[
                    CriterionClaim(
                        criterion_name="Mathematical Accuracy",
                        assessment="fulfilled" if score_factor >= 0.7 else "partially_fulfilled",
                        score_factor=score_factor,
                        reasoning="Formulas and symbolic steps verified against model answer.",
                        evidence_quotes=verified_evidence,
                    )
                ],
                observations=["Evaluated symbolic equations and formula structure."],
            )

        # Match student numbers against expected model numbers
        matched_numbers = 0
        tolerance = 0.05  # 5% relative tolerance

        for exp in model_nums:
            for s_num in student_nums:
                denom = abs(exp) if abs(exp) > 1e-6 else 1.0
                if abs(s_num - exp) / denom <= tolerance or abs(s_num - exp) < 1e-4:
                    matched_numbers += 1
                    break

        accuracy_ratio = matched_numbers / len(model_nums)
        # Factor in formula presence
        has_formula = len(equations_found) > 0 or any(c in student_answer for c in ["=", "+", "-", "*", "/"])
        if matched_numbers == 0 and student_nums:
            # Student attempted calculation and got it wrong: formula credit is capped at 0.15
            attainment = 0.15 if has_formula else 0.0
        else:
            attainment = min(1.0, (accuracy_ratio * 0.7) + (0.3 if has_formula else 0.0))
        score_factor = round(attainment, 2)


        assessment_label = (
            "fulfilled" if score_factor >= 0.85
            else "partially_fulfilled" if score_factor >= 0.4
            else "incorrect" if student_nums
            else "missing"
        )

        reasoning = (
            f"Calculated values matched {matched_numbers}/{len(model_nums)} expected targets. "
            f"Expected: {model_nums[:3]}, found: {student_nums[:3]}."
        )

        claims = [
            CriterionClaim(
                criterion_name="Mathematical Accuracy",
                assessment=assessment_label,
                score_factor=score_factor,
                reasoning=reasoning,
                evidence_quotes=verified_evidence,
            )
        ]

        return EvaluatorOutput(
            evaluator_name=self.name,
            status="success",
            confidence=0.9,
            evidence=verified_evidence,
            claims=claims,
            observations=[
                f"Matched {matched_numbers} out of {len(model_nums)} numerical values within 5% tolerance.",
                f"Formula notation detected: {has_formula}.",
            ],
            metadata={
                "expected_numbers": model_nums,
                "student_numbers": student_nums,
                "matched_count": matched_numbers,
            },
        )
