"""Code and Programming Evaluator (Requirement B).

Specialized in evaluating programming questions, algorithm syntax,
control structures, and implementation logic.
"""

from __future__ import annotations

import ast
import logging
import re
from typing import List, Optional

from backend.app.schemas.evaluator_contracts import CriterionClaim, EvaluatorOutput, SourceReference
from backend.app.services.evaluators.base import extract_verifiable_quotes

logger = logging.getLogger(__name__)

_CODE_KEYWORDS = {
    "def ", "return ", "if ", "else:", "elif ", "for ", "while ", "import ",
    "class ", "int ", "float ", "char ", "void ", "public ", "static ", "function",
    "SELECT ", "FROM ", "WHERE ", "print(", "console.log"
}


def _detect_code_presence(text: str) -> bool:
    """Detect whether text contains code constructs or programming syntax."""
    lines = text.split("\n")
    code_like_lines = sum(
        1 for line in lines
        if any(kw in line for kw in _CODE_KEYWORDS)
        or re.search(r"[{};()\[\]=<>!]", line)
    )
    return code_like_lines >= 1 or any(kw in text for kw in _CODE_KEYWORDS)


def _try_parse_python(code_str: str) -> tuple[bool, Optional[str], List[str]]:
    """Attempt AST parse on candidate python code. Returns (valid, error_msg, constructs)."""
    try:
        tree = ast.parse(code_str)
        constructs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                constructs.append(f"Function: {node.name}")
            elif isinstance(node, (ast.For, ast.While)):
                constructs.append("Loop construct")
            elif isinstance(node, ast.If):
                constructs.append("Conditional branch")
            elif isinstance(node, ast.Return):
                constructs.append("Return statement")
        return True, None, constructs
    except SyntaxError as e:
        return False, str(e), []


class CodeEvaluator:
    name: str = "code"

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
        """Evaluate programming logic, syntax validity, and algorithmic constructs."""
        is_code_question = any(
            kw in question.lower()
            for kw in ["code", "function", "program", "algorithm", "implement", "write a python", "write a c", "class", "loop", "method"]
        ) or _detect_code_presence(model_answer)

        if not is_code_question:
            return EvaluatorOutput(
                evaluator_name=self.name,
                status="skipped",
                confidence=1.0,
                evidence=[],
                claims=[],
                observations=["Non-programming question; code evaluator skipped."],
            )

        if not student_answer.strip():
            return EvaluatorOutput(
                evaluator_name=self.name,
                status="success",
                confidence=1.0,
                evidence=[],
                claims=[
                    CriterionClaim(
                        criterion_name="Code Implementation",
                        assessment="missing",
                        score_factor=0.0,
                        reasoning="No code solution was provided.",
                        evidence_quotes=[],
                    )
                ],
                observations=["Empty submission for coding question."],
            )

        # Code lines as candidate quotes
        candidate_quotes = [
            line.strip() for line in student_answer.split("\n")
            if len(line.strip()) > 5 and any(c in line for c in "()={}[];:<>")
        ]
        verified_evidence = extract_verifiable_quotes(student_answer, candidate_quotes[:4])

        has_code = _detect_code_presence(student_answer)
        if not has_code:
            return EvaluatorOutput(
                evaluator_name=self.name,
                status="success",
                confidence=0.85,
                evidence=[],
                claims=[
                    CriterionClaim(
                        criterion_name="Code Implementation",
                        assessment="missing",
                        score_factor=0.1,
                        reasoning="Student wrote an explanation but provided no code implementation.",
                        evidence_quotes=[],
                    )
                ],
                observations=["Explanation provided without actual code implementation."],
            )

        # Try Python AST parse
        is_valid_py, py_err, constructs = _try_parse_python(student_answer)

        # Keyword alignment with model answer
        model_kw = [kw.strip() for kw in _CODE_KEYWORDS if kw in model_answer]
        matched_kw = [kw for kw in model_kw if kw in student_answer]
        kw_ratio = len(matched_kw) / max(len(model_kw), 1) if model_kw else 0.8

        if is_valid_py:
            score_factor = round(min(1.0, 0.5 + 0.5 * kw_ratio), 2)
            assessment_label = "fulfilled" if score_factor >= 0.8 else "partially_fulfilled"
            reasoning = f"Valid syntax. Identified structures: {', '.join(set(constructs)) or 'basic logic'}."
        else:
            # Tolerant parsing for partial scripts / other languages (C/Java/pseudocode)
            score_factor = round(min(0.75, 0.3 + 0.4 * kw_ratio), 2)
            assessment_label = "partially_fulfilled"
            reasoning = f"Code structure detected with minor syntax issues: {py_err or 'unparsed'}"

        claims = [
            CriterionClaim(
                criterion_name="Code Implementation",
                assessment=assessment_label,
                score_factor=score_factor,
                reasoning=reasoning,
                evidence_quotes=verified_evidence,
            )
        ]

        return EvaluatorOutput(
            evaluator_name=self.name,
            status="success",
            confidence=0.88,
            evidence=verified_evidence,
            claims=claims,
            observations=[
                f"Syntax validity: {is_valid_py}.",
                f"Constructs found: {list(set(constructs))}.",
                f"Matched expected keywords: {matched_kw}.",
            ],
            metadata={
                "syntax_valid": is_valid_py,
                "constructs": constructs,
                "matched_keywords": matched_kw,
            },
        )
