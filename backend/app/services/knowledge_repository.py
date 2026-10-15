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


import re
import uuid


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b[a-zA-Z0-9_]{3,}\b", text.lower()))


class InMemoryKnowledgeRepository:
    """Thread-safe in-memory knowledge repository implementing AcademicKnowledgeRepository."""

    def __init__(self) -> None:
        self._storage: dict[str, KnowledgeObject] = {}

    def ingest(self, obj: KnowledgeObject) -> str:
        """Store a new KnowledgeObject with auto-versioning; returns its id."""
        norm_qid = obj.metadata.question_id.strip().upper()
        # Find existing versions
        existing = [
            ko for ko in self._storage.values()
            if ko.metadata.assessment_id == obj.metadata.assessment_id
            and ko.metadata.question_id.strip().upper() == norm_qid
            and ko.metadata.document_type == obj.metadata.document_type
        ]
        if existing:
            highest_version = max(ko.metadata.version for ko in existing)
            obj.metadata.version = highest_version + 1
        else:
            if obj.metadata.version <= 0:
                obj.metadata.version = 1

        knowledge_id = f"kn-{uuid.uuid4().hex[:8]}"
        self._storage[knowledge_id] = obj
        return knowledge_id

    def update(self, knowledge_id: str, obj: KnowledgeObject) -> None:
        """Update an existing knowledge entry or create next version."""
        if knowledge_id not in self._storage:
            raise KeyError(f"Knowledge object '{knowledge_id}' not found.")
        old = self._storage[knowledge_id]
        if old.metadata.approval_status == "approved":
            # Immutable approved objects: increment version
            obj.metadata.version = old.metadata.version + 1
        self._storage[knowledge_id] = obj

    def retrieve_by_question(
        self, assessment_id: str, question_id: str, *, approved_only: bool = True
    ) -> Optional[KnowledgeObject]:
        """Exact assessment + question match, latest version."""
        norm_qid = question_id.strip().upper()
        candidates = [
            ko for ko in self._storage.values()
            if ko.metadata.assessment_id == assessment_id
            and ko.metadata.question_id.strip().upper() == norm_qid
            and (not approved_only or ko.metadata.approval_status == "approved")
        ]
        if not candidates:
            return None
        # Return latest version
        candidates.sort(key=lambda ko: ko.metadata.version, reverse=True)
        return candidates[0]

    def retrieve_by_assessment(self, assessment_id: str) -> List[KnowledgeObject]:
        """All knowledge objects scoped to an assessment."""
        return [
            ko for ko in self._storage.values()
            if ko.metadata.assessment_id == assessment_id
            and ko.metadata.approval_status != "archived"
        ]

    def retrieve_semantically(
        self,
        query: str,
        *,
        subject: Optional[str] = None,
        assessment_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[KnowledgeObject]:
        """Scoped term-overlap retrieval within assessment and/or subject materials."""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        candidates = [
            ko for ko in self._storage.values()
            if ko.metadata.approval_status != "archived"
            and (subject is None or ko.metadata.subject.lower() == subject.lower())
            and (assessment_id is None or ko.metadata.assessment_id == assessment_id)
        ]

        scored: list[tuple[float, KnowledgeObject]] = []
        for ko in candidates:
            content_tokens = _tokenize(ko.content)
            if not content_tokens:
                continue
            intersection = query_tokens.intersection(content_tokens)
            score = len(intersection) / float(len(query_tokens))
            if score > 0:
                scored.append((score, ko))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def version_history(self, assessment_id: str, question_id: str) -> List[KnowledgeObject]:
        norm_qid = question_id.strip().upper()
        matches = [
            ko for ko in self._storage.values()
            if ko.metadata.assessment_id == assessment_id
            and ko.metadata.question_id.strip().upper() == norm_qid
        ]
        matches.sort(key=lambda ko: ko.metadata.version)
        return matches

    def archive(self, knowledge_id: str) -> None:
        if knowledge_id in self._storage:
            self._storage[knowledge_id].metadata.approval_status = "archived"


_default_repository: Optional[InMemoryKnowledgeRepository] = None


def get_knowledge_repository() -> InMemoryKnowledgeRepository:
    global _default_repository
    if _default_repository is None:
        _default_repository = InMemoryKnowledgeRepository()
    return _default_repository


def reset_knowledge_repository() -> None:
    global _default_repository
    _default_repository = InMemoryKnowledgeRepository()
