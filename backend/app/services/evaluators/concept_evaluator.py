"""Concept and Text Evaluator (Requirement B).

Specialized in evaluating conceptual understanding, terminology usage,
and extracted conceptual evidence verified against the student answer.
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

from backend.app.schemas.evaluator_contracts import CriterionClaim, EvaluatorOutput, SourceReference
from backend.app.services.evaluators.base import extract_verifiable_quotes

logger = logging.getLogger(__name__)


def _extract_key_terms(text: str) -> List[str]:
    """Extract key technical and conceptual nouns/phrases."""
    # Split on punctuation, filter stopwords
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "and", "or", "in", "on", "at",
        "to", "for", "with", "by", "from", "that", "this", "which", "as", "it", "its",
        "of", "be", "been", "have", "has", "had", "do", "does", "did", "can", "could",
    }
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_\-]{2,}\b", text.lower())
    meaningful = [w for w in words if w not in stopwords and len(w) > 3]
    # Unique preserving order
    seen = set()
    result = []
    for w in meaningful:
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result


class ConceptEvaluator:
    name: str = "concept_text"

    def evaluate(
        self,
        question: str,
        student_answer: str,
        model_answer: str,
        rubric: dict,
        retrieved_sources: Optional[List[SourceReference]] = None,
        image_bytes: Optional[bytes] = None,
        gemini_caller=None,
        **kwargs,
    ) -> EvaluatorOutput:
        """Evaluate conceptual alignment between student answer and model/grounding context."""
        if not student_answer.strip():
            return EvaluatorOutput(
                evaluator_name=self.name,
                status="success",
                confidence=1.0,
                evidence=[],
                key_terms_present=[],
                key_terms_missing=_extract_key_terms(model_answer)[:5],
                claims=[
                    CriterionClaim(
                        criterion_name="Conceptual Understanding",
                        assessment="missing",
                        score_factor=0.0,
                        reasoning="No student answer text provided.",
                        evidence_quotes=[],
                    )
                ],
                observations=["Empty student answer provided."],
            )

        model_terms = _extract_key_terms(model_answer)
        student_lower = student_answer.lower()

        present_terms = [t for t in model_terms if t in student_lower]
        missing_terms = [t for t in model_terms if t not in student_lower]

        # Extract sentences from student answer that contain key terms as candidate evidence
        sentences = re.split(r"[.\n;]+", student_answer)
        candidate_quotes = [
            s.strip() for s in sentences
            if len(s.strip()) > 10 and any(t in s.lower() for t in present_terms)
        ]
        verified_evidence = extract_verifiable_quotes(student_answer, candidate_quotes[:4])

        # Compute term-coverage attainment factor
        coverage = len(present_terms) / max(len(model_terms), 1) if model_terms else 1.0
        # Scale to an attainment factor between 0.0 and 1.0
        score_factor = round(min(1.0, max(0.0, coverage * 1.25)), 2)

        assessment_label = (
            "fulfilled" if score_factor >= 0.8
            else "partially_fulfilled" if score_factor >= 0.35
            else "missing" if score_factor == 0.0
            else "incorrect"
        )

        reasoning = (
            f"Student demonstrated understanding of key concepts ({', '.join(present_terms[:4]) or 'none detected'}). "
            f"Missing concepts: {', '.join(missing_terms[:3]) if missing_terms else 'none'}."
        )

        claims = [
            CriterionClaim(
                criterion_name="Conceptual Understanding",
                assessment=assessment_label,
                score_factor=score_factor,
                reasoning=reasoning,
                evidence_quotes=verified_evidence,
            )
        ]

        if "technical_terminology" in json.dumps(rubric).lower():
            claims.append(
                CriterionClaim(
                    criterion_name="Technical Terminology",
                    assessment="fulfilled" if len(present_terms) >= 3 else "partially_fulfilled",
                    score_factor=min(1.0, round(len(present_terms) / max(len(model_terms), 1), 2)),
                    reasoning=f"Used {len(present_terms)} expected technical terms.",
                    evidence_quotes=verified_evidence[:2],
                )
            )

        return EvaluatorOutput(
            evaluator_name=self.name,
            status="success",
            confidence=round(0.75 + 0.25 * min(1.0, len(verified_evidence) / 2.0), 2),
            evidence=verified_evidence,
            key_terms_present=present_terms,
            key_terms_missing=missing_terms[:6],
            claims=claims,
            observations=[
                f"Identified {len(present_terms)}/{len(model_terms)} model concepts.",
                f"Extracted {len(verified_evidence)} verified evidence quotes.",
            ],
            metadata={
                "model_terms_count": len(model_terms),
                "matched_terms_count": len(present_terms),
            },
        )
