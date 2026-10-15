"""Base evaluator protocol and common utilities."""

from __future__ import annotations

import re
from typing import List, Optional, Protocol

from backend.app.schemas.evaluator_contracts import EvaluatorOutput, SourceReference


class BaseEvaluator(Protocol):
    """Protocol for all specialized assessment evaluators."""

    @property
    def name(self) -> str: ...

    def evaluate(
        self,
        question: str,
        student_answer: str,
        model_answer: str,
        rubric: dict,
        retrieved_sources: Optional[List[SourceReference]] = None,
        image_bytes: Optional[bytes] = None,
        **kwargs,
    ) -> EvaluatorOutput: ...


def extract_verifiable_quotes(student_answer: str, candidate_phrases: List[str]) -> List[str]:
    """Verify which candidate evidence quotes actually exist verbatim or near-verbatim

    in the student's answer text. Prevents fabricated evidence from being recorded.
    """
    if not student_answer or not candidate_phrases:
        return []

    norm_student = re.sub(r"\s+", " ", student_answer.strip().lower())
    verified: List[str] = []

    for phrase in candidate_phrases:
        clean_phrase = re.sub(r"\s+", " ", phrase.strip())
        if not clean_phrase:
            continue
        # Exact substring search (case-insensitive)
        if clean_phrase.lower() in norm_student:
            verified.append(clean_phrase)
        else:
            # Word overlap check for partial match with at least 80% tokens
            tokens = clean_phrase.lower().split()
            if len(tokens) >= 3:
                token_count = sum(1 for t in tokens if t in norm_student)
                if token_count / len(tokens) >= 0.8:
                    verified.append(clean_phrase)

    return verified
