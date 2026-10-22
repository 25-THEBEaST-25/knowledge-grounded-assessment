"""Faculty-approved academic knowledge retrieval service (Requirement C).

Retrieves authorized chunks from faculty-provided materials, approved model
answers, and rubrics, strictly scoped to the specified assessment.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from backend.app.schemas.evaluator_contracts import SourceReference
from backend.app.services.ingestion_service import IngestedQuestion, ingest_document
from backend.app.services.knowledge_repository import (
    AcademicKnowledgeRepository,
    KnowledgeMetadata,
    KnowledgeObject,
    get_knowledge_repository,
)
from backend.app.services.segmentation_service import normalize_question_id

logger = logging.getLogger(__name__)


def register_approved_question_material(
    assessment_id: str,
    question_id: str,
    model_answer: str,
    rubric: dict,
    question_text: str = "",
    source_file: str = "faculty_portal",
    subject: str = "General",
    repository: Optional[AcademicKnowledgeRepository] = None,
) -> None:
    """Store approved model answer, rubric, and question text into the repository."""
    repo = repository or get_knowledge_repository()
    norm_qid = normalize_question_id(question_id)

    # 1. Model answer
    if model_answer.strip():
        meta_ma = KnowledgeMetadata(
            subject=subject,
            assessment_id=assessment_id,
            semester="",
            academic_year="",
            question_id=norm_qid,
            document_type="model_answer",
            source_file=source_file,
            approval_status="approved",
        )
        repo.ingest(KnowledgeObject(metadata=meta_ma, content=model_answer.strip()))

    # 2. Faculty Rubric
    if rubric:
        meta_rb = KnowledgeMetadata(
            subject=subject,
            assessment_id=assessment_id,
            semester="",
            academic_year="",
            question_id=norm_qid,
            document_type="rubric",
            source_file=source_file,
            approval_status="approved",
        )
        repo.ingest(KnowledgeObject(metadata=meta_rb, content=json.dumps(rubric)))

    # 3. Question paper text if available
    if question_text.strip():
        meta_qp = KnowledgeMetadata(
            subject=subject,
            assessment_id=assessment_id,
            semester="",
            academic_year="",
            question_id=norm_qid,
            document_type="question_paper",
            source_file=source_file,
            approval_status="approved",
        )
        repo.ingest(KnowledgeObject(metadata=meta_qp, content=question_text.strip()))


def register_approved_reference_material(
    assessment_id: str,
    content: str,
    source_file: str,
    document_type: str = "notes",  # "notes" | "lecture_notes" | "reference" | "pyq"
    subject: str = "General",
    repository: Optional[AcademicKnowledgeRepository] = None,
) -> str:
    """Store approved lecture notes, study materials, or PYQ chunks in the repository."""
    repo = repository or get_knowledge_repository()
    if not content.strip():
        return ""
    meta = KnowledgeMetadata(
        subject=subject,
        assessment_id=assessment_id,
        semester="",
        academic_year="",
        question_id="GLOBAL",
        document_type=document_type,
        source_file=source_file,
        approval_status="approved",
    )
    return repo.ingest(KnowledgeObject(metadata=meta, content=content.strip()))


def index_material_document(
    assessment_id: str,
    filename: str,
    content: bytes,
    kind: str,
    subject: str = "General",
    faculty_owner: str = "",
    repository: Optional[AcademicKnowledgeRepository] = None,
) -> List[IngestedQuestion]:
    """Ingest a faculty document (PDF/DOCX/TXT) using existing ingestion_service
    and store question-wise knowledge objects scoped to this assessment.
    """
    repo = repository or get_knowledge_repository()
    result = ingest_document(filename, content, kind)

    if kind in ("reference", "notes", "lecture_notes"):
        register_approved_reference_material(
            assessment_id=assessment_id,
            content=result.raw_text_preview,
            source_file=filename,
            document_type=kind,
            subject=subject,
            repository=repo,
        )
        return result.questions

    for q in result.questions:
        norm_qid = normalize_question_id(q.question_id)
        text = q.model_answer if kind == "model_answer" else q.question_text
        if not text.strip():
            continue

        meta = KnowledgeMetadata(
            subject=subject,
            assessment_id=assessment_id,
            semester="",
            academic_year="",
            question_id=norm_qid,
            document_type=kind,
            source_file=filename,
            faculty_owner=faculty_owner,
            approval_status="approved",
        )
        repo.ingest(KnowledgeObject(metadata=meta, content=text.strip()))

    return result.questions


def retrieve_grounding_sources(
    assessment_id: str,
    question_id: str,
    student_answer: str = "",
    top_k: int = 4,
    repository: Optional[AcademicKnowledgeRepository] = None,
) -> List[SourceReference]:
    """Retrieve relevant chunks scoped strictly to `assessment_id` and `question_id`.

    Never retrieves chunks across different assessments. Returns a list of
    SourceReference objects for the evaluation trace.
    """
    repo = repository or get_knowledge_repository()
    norm_qid = normalize_question_id(question_id)
    references: List[SourceReference] = []

    # 1. Exact question-specific lookup (B7): highest priority
    all_assessment_items = repo.retrieve_by_assessment(assessment_id)
    question_specific_items = [
        ko for ko in all_assessment_items
        if normalize_question_id(ko.metadata.question_id).lower() == norm_qid.lower()
    ]

    for ko in question_specific_items:
        excerpt = ko.content[:280] + ("..." if len(ko.content) > 280 else "")
        references.append(
            SourceReference(
                source_file=ko.metadata.source_file or "Faculty Model Material",
                document_type=ko.metadata.document_type,
                excerpt=excerpt,
                relevance_score=1.0,
                page=ko.metadata.page,
                question_id=norm_qid,
            )
        )

    # 2. Scoped semantic / term-overlap search in authorized assessment material
    if student_answer.strip():
        semantic_matches = repo.retrieve_semantically(
            query=student_answer,
            assessment_id=assessment_id,
            top_k=top_k,
        )
        for match in semantic_matches:
            # Avoid duplicate references
            if any(ref.excerpt == match.content[:280] for ref in references):
                continue
            match_qid = normalize_question_id(match.metadata.question_id)
            score = 0.85 if match_qid.lower() == norm_qid.lower() else 0.50
            references.append(
                SourceReference(
                    source_file=match.metadata.source_file or "Assessment Material",
                    document_type=match.metadata.document_type,
                    excerpt=match.content[:280],
                    relevance_score=score,
                    page=match.metadata.page,
                    question_id=match_qid,
                )
            )

    return references[:top_k]
