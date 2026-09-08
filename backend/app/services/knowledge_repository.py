"""Storage abstraction for approved academic knowledge -- model answers,
question papers, rubrics (B5/B6).

This defines the CONTRACT a future implementation must satisfy (PostgreSQL
first, a Qdrant-backed semantic layer later per B6) so the rest of the
application never depends on a specific storage technology.

THERE IS NO CONCRETE IMPLEMENTATION OF THIS INTERFACE IN THE RUNNING SYSTEM.
For this milestone, ingested + faculty-approved material is stored via the
existing frontend localStorage mechanism
(frontend/app/lib/localAssessments.ts) exactly as B5 instructs ("use the
project's existing available persistence mechanism"). This file exists so
that swapping in a real repository later is a matter of implementing these
methods against the metadata shape already defined here, not redesigning
every caller -- it is a documented roadmap interface point, not a live
component. Do not import this into API routes and do not claim it is wired
up; nothing in this codebase currently calls it.

B7 (question-specific retrieval): once a real implementation exists,
retrieve_by_question must always be preferred over retrieve_semantically for
grading -- an evaluation should never be grounded in a different question's
model answer merely because it's semantically similar. Grading correctness
depends on this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Protocol


@dataclass
class KnowledgeMetadata:
    """Fields a future Qdrant payload / SQL row would carry (B5's list)."""

    subject: str
    assessment_id: str
    semester: str
    academic_year: str
    question_id: str
    subquestion_id: Optional[str] = None
    co: Optional[str] = None  # Course Outcome code, e.g. "CO3"
    po: Optional[str] = None  # Program Outcome code, e.g. "PO2"
    document_type: str = "model_answer"  # "model_answer" | "question_paper" | "rubric" | "reference"
    source_file: str = ""
    page: Optional[int] = None
    faculty_owner: str = ""
    version: int = 1
    approval_status: str = "pending"  # "pending" | "approved" | "archived" (B8)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class KnowledgeObject:
    metadata: KnowledgeMetadata
    content: str  # question text, model answer, or rubric (as text/JSON string)


class AcademicKnowledgeRepository(Protocol):
    """Conceptual operations a real implementation must provide."""

    def ingest(self, obj: KnowledgeObject) -> str:
        """Store a new KnowledgeObject; returns its id."""
        ...

    def update(self, knowledge_id: str, obj: KnowledgeObject) -> None:
        """Create a new version (B8) -- must never silently overwrite an
        already-approved version in place."""
        ...

    def retrieve_by_question(
        self, assessment_id: str, question_id: str, *, approved_only: bool = True
    ) -> Optional[KnowledgeObject]:
        """The primary grading-time lookup (B7): exact assessment + question
        match, latest approved version. Must never fall back to a different
        question's content."""
        ...

    def retrieve_by_assessment(self, assessment_id: str) -> List[KnowledgeObject]: ...

    def retrieve_semantically(
        self, query: str, *, subject: Optional[str] = None, top_k: int = 5
    ) -> List[KnowledgeObject]:
        """Roadmap (B6): requires an embedding model + a vector store
        (Qdrant), neither of which is configured anywhere in this repository.
        Not implemented -- exists to document the intended future signature."""
        ...

    def version_history(self, assessment_id: str, question_id: str) -> List[KnowledgeObject]: ...

    def archive(self, knowledge_id: str) -> None: ...
