import hashlib
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.materials import (
    IngestedQuestionOut,
    MaterialApprovalRequest,
    MaterialApprovalResponse,
    MaterialIngestionResponse,
    RubricCriterionOut,
)
from backend.app.services.ingestion_service import (
    MAX_UPLOAD_BYTES,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_KINDS,
    UnsupportedDocumentError,
    ingest_document,
)
from backend.app.services.retrieval_service import (
    get_knowledge_repository,
    register_approved_question_material,
    register_approved_reference_material,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/materials", tags=["Materials"])


@router.get("/types")
def get_supported_material_types():
    """Return supported academic material categories, formats, and limits."""
    return {
        "supported_kinds": [
            {
                "kind": "question_paper",
                "label": "Question Paper",
                "description": "Exam question paper (.pdf, .docx, .txt, .png, .jpg)",
            },
            {
                "kind": "model_answer",
                "label": "Model Answers",
                "description": "Faculty-approved solution key (.pdf, .docx, .txt)",
            },
            {
                "kind": "rubric",
                "label": "Rubric / Marking Scheme",
                "description": "Criteria breakdown and mark distributions (.pdf, .docx, .txt)",
            },
            {
                "kind": "notes",
                "label": "Lecture Notes & Study Material",
                "description": "Course reference notes for knowledge-grounded evaluation (.pdf, .docx, .txt)",
            },
            {
                "kind": "pyq",
                "label": "Previous Year Questions (PYQs)",
                "description": "Past assessment questions for evaluation grounding (.pdf, .docx, .txt)",
            },
        ],
        "supported_extensions": sorted(list(SUPPORTED_EXTENSIONS)),
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
    }


@router.post("/ingest", response_model=MaterialIngestionResponse)
async def ingest(
    file: UploadFile = File(...),
    kind: str = Form(
        ...,
        description='"question_paper", "model_answer", "rubric", "notes", "lecture_notes", "reference", or "pyq"',
    ),
    assessment_id: Optional[str] = Form(None),
):
    """Faculty material ingestion: upload an academic resource and get back structured,
    question-wise or section-wise content for faculty review -- never auto-published."""
    if kind not in SUPPORTED_KINDS:
        raise HTTPException(
            status_code=422,
            detail=f'`kind` must be one of: {", ".join(sorted(SUPPORTED_KINDS))}.',
        )

    content = await file.read()
    filename = file.filename or "upload"

    try:
        result = ingest_document(filename, content, kind)
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Material ingestion failed")
        raise HTTPException(
            status_code=500,
            detail="Document ingestion failed. Please try again later.",
        )

    rubric_out = None
    if result.rubric_criteria:
        rubric_out = {
            qid: [RubricCriterionOut(**c) for c in crits]
            for qid, crits in result.rubric_criteria.items()
        }

    return MaterialIngestionResponse(
        questions=[IngestedQuestionOut(**q.__dict__) for q in result.questions],
        raw_text_preview=result.raw_text_preview,
        extraction_engine=result.extraction_engine,
        document_type=result.document_type,
        rubric_criteria=rubric_out,
        sections_preview=result.sections_preview,
        status="awaiting_review",
        filename=filename,
        size_bytes=len(content),
    )


@router.post("/approve", response_model=MaterialApprovalResponse)
def approve_material(request: MaterialApprovalRequest):
    """Faculty approval and indexing of extracted academic material into the knowledge repository.

    Only approved content is indexed and made eligible for grounded retrieval during evaluation.
    """
    if request.document_type not in SUPPORTED_KINDS:
        raise HTTPException(
            status_code=422,
            detail=f'Invalid document_type. Must be one of: {", ".join(sorted(SUPPORTED_KINDS))}.',
        )

    repo = get_knowledge_repository()
    indexed_count = 0
    knowledge_ids = []

    # 1. Notes / Reference / Lecture Notes / PYQs
    if request.document_type in ("reference", "notes", "lecture_notes"):
        content_text = request.content or ""
        if not content_text and request.questions:
            content_text = "\n\n".join(q.model_answer for q in request.questions if q.model_answer)

        if content_text.strip():
            kid = register_approved_reference_material(
                assessment_id=request.assessment_id,
                content=content_text,
                source_file=request.filename,
                document_type=request.document_type,
                subject=request.subject,
                repository=repo,
            )
            if kid:
                knowledge_ids.append(kid)
                indexed_count += 1

    # 2. Question papers, Model answers, Rubrics, PYQs
    elif request.questions:
        for q in request.questions:
            rubric_dict = {}
            if request.rubric_criteria and q.question_id in request.rubric_criteria:
                rubric_dict = {
                    "criteria": [
                        {
                            "name": c.code or c.description[:30],
                            "description": c.description,
                            "max_score": c.max_marks,
                        }
                        for c in request.rubric_criteria[q.question_id]
                    ]
                }
            elif q.max_score:
                rubric_dict = {"max_score": q.max_score}

            register_approved_question_material(
                assessment_id=request.assessment_id,
                question_id=q.question_id,
                model_answer=q.model_answer,
                rubric=rubric_dict,
                question_text=q.question_text,
                source_file=request.filename,
                subject=request.subject,
                repository=repo,
            )
            indexed_count += 1
            knowledge_ids.append(f"{request.assessment_id}:{q.question_id}")

    return MaterialApprovalResponse(
        status="approved",
        assessment_id=request.assessment_id,
        document_type=request.document_type,
        indexed_chunks=indexed_count,
        knowledge_ids=knowledge_ids,
        message=f"Successfully approved and indexed {indexed_count} items from {request.filename}.",
    )


@router.get("/status/{assessment_id}")
def get_assessment_materials_status(assessment_id: str):
    """Retrieve indexing and approval status of academic resources for an assessment."""
    repo = get_knowledge_repository()
    items = repo.retrieve_by_assessment(assessment_id)

    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for ko in items:
        dtype = ko.metadata.document_type
        by_type.setdefault(dtype, []).append(
            {
                "question_id": ko.metadata.question_id,
                "source_file": ko.metadata.source_file,
                "version": ko.metadata.version,
                "approval_status": ko.metadata.approval_status,
                "created_at": ko.metadata.created_at.isoformat(),
                "content_preview": ko.content[:150] + ("..." if len(ko.content) > 150 else ""),
            }
        )

    return {
        "assessment_id": assessment_id,
        "total_approved_knowledge_objects": len(items),
        "materials_by_type": by_type,
    }

