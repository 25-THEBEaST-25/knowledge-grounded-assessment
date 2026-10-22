"""Contracts and schemas for the assessment orchestrator, specialized evaluators,
source retrieval, and deterministic rubric scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    """Source reference from faculty-approved academic materials."""

    source_file: str
    document_type: str = "model_answer"  # "model_answer" | "question_paper" | "rubric" | "reference"
    excerpt: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    page: Optional[int] = None
    section: Optional[str] = None
    question_id: Optional[str] = None


class CriterionClaim(BaseModel):
    """Evaluator claim on a specific rubric criterion or competency."""

    criterion_name: str
    assessment: str = Field(
        description="'fulfilled', 'partially_fulfilled', 'missing', or 'incorrect'"
    )
    score_factor: float = Field(
        ge=0.0,
        le=1.0,
        description="Attainment factor (0.0 = no credit, 0.5 = partial, 1.0 = full)",
    )
    reasoning: str
    evidence_quotes: List[str] = Field(
        default_factory=list,
        description="Verifiable quotes extracted from the student's answer",
    )


class EvaluatorOutput(BaseModel):
    """Structured output from any specialized evaluator."""

    evaluator_name: str
    status: str = "success"  # "success" | "failed" | "skipped"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: List[str] = Field(
        default_factory=list,
        description="Direct quotes or extracted evidence from student response",
    )
    key_terms_present: List[str] = Field(default_factory=list)
    key_terms_missing: List[str] = Field(default_factory=list)
    claims: List[CriterionClaim] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class RubricCriterionSpec(BaseModel):
    """Normalized specification for a single rubric criterion."""

    name: str
    max_score: float = Field(gt=0.0)
    description: str = ""
    evaluator_type: str = "concept"  # "concept" | "accuracy" | "code" | "diagram" | "general"
    keywords: List[str] = Field(default_factory=list)


class CriterionScoreResult(BaseModel):
    """Deterministic score and audit details for one rubric criterion."""

    criterion_name: str
    max_score: float = Field(gt=0.0)
    awarded_score: float = Field(ge=0.0)
    attainment_factor: float = Field(ge=0.0, le=1.0)
    reasoning: str
    evaluator_name: str
    evidence_used: List[str] = Field(default_factory=list)
    verified_evidence: bool = True

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class EvaluationTrace(BaseModel):
    """Auditable trace of the complete evaluation execution."""

    trace_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    question_id: str
    routing_reasons: Dict[str, str] = Field(default_factory=dict)
    evaluators_run: List[str] = Field(default_factory=list)
    evaluators_failed: List[str] = Field(default_factory=list)
    retrieval_sources: List[SourceReference] = Field(default_factory=list)
    criteria_breakdown: List[CriterionScoreResult] = Field(default_factory=list)
    review_flags: List[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)




class OrchestrationResult(BaseModel):
    """Output from the Assessment Orchestrator before grading."""

    question_id: str
    selected_evaluators: List[str]
    routing_reasons: Dict[str, str]
    evaluator_outputs: Dict[str, EvaluatorOutput]
    retrieved_sources: List[SourceReference]
    execution_times_ms: Dict[str, float]
    failures: List[str] = Field(default_factory=list)
