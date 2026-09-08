import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.schemas.materials import IngestedQuestionOut, MaterialIngestionResponse
from backend.app.services.ingestion_service import UnsupportedDocumentError, ingest_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/materials", tags=["Materials"])


@router.post("/ingest", response_model=MaterialIngestionResponse)
async def ingest(
    file: UploadFile = File(...),
    kind: str = Form(..., description='"question_paper" or "model_answer"'),
):
    """Faculty material ingestion (B1/B2): upload a question paper or
    model-answer document (.txt/.pdf/.docx) and get back structured,
    question-wise content for faculty review -- never auto-published (B4)."""
    if kind not in ("question_paper", "model_answer"):
        raise HTTPException(status_code=422, detail='`kind` must be "question_paper" or "model_answer".')

    content = await file.read()
    try:
        result = ingest_document(file.filename or "upload", content, kind)
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Material ingestion failed")
        raise HTTPException(status_code=500, detail="Document ingestion failed. Please try again later.")

    return MaterialIngestionResponse(
        questions=[IngestedQuestionOut(**q.__dict__) for q in result.questions],
        raw_text_preview=result.raw_text_preview,
        extraction_engine=result.extraction_engine,
    )
