import json
import logging
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import TypeAdapter, ValidationError
from starlette.concurrency import run_in_threadpool

from backend.app.schemas.handwritten import (
    HandwrittenEvaluationResponse,
    OCRLineOut,
    OCRResponse,
    QuestionSpec,
    SegmentOut,
    SegmentRequest,
    SegmentResponse,
)
from backend.app.services.ocr_service import (
    InvalidImageError,
    OCRUnavailableError,
    extract_text,
)
from backend.app.services.pipeline_service import evaluate_handwritten_image
from backend.app.services.segmentation_service import segment_answers

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/handwritten",
    tags=["Handwritten"],
)

_questions_adapter = TypeAdapter(List[QuestionSpec])

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


async def _read_image(image: UploadFile) -> bytes:
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload must be an image file.")
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 15 MB limit.")
    return data


@router.post("/ocr", response_model=OCRResponse)
async def ocr(image: UploadFile = File(...)):
    """Step 1: run PaddleOCR on a handwritten answer image."""
    data = await _read_image(image)
    try:
        result = await run_in_threadpool(extract_text, data)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OCRUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("OCR extraction failed")
        raise HTTPException(status_code=500, detail="OCR processing failed. Please try again later.")

    return OCRResponse(
        extracted_text=result.text,
        lines=[OCRLineOut(text=l.text, confidence=l.confidence, bbox=l.bbox) for l in result.lines],
        mean_confidence=result.mean_confidence,
        engine=result.engine,
    )


@router.post("/segment", response_model=SegmentResponse)
async def segment(request: SegmentRequest):
    """Step 2: split extracted text into per-question answers."""
    try:
        result = await run_in_threadpool(
            segment_answers,
            request.text,
            expected_question_ids=request.expected_question_ids,
        )
    except Exception:
        logger.exception("Segmentation failed")
        raise HTTPException(status_code=500, detail="Answer segmentation failed. Please try again later.")

    return SegmentResponse(
        segments=[SegmentOut(**s.__dict__) for s in result.segments],
        unassigned_preamble=result.unassigned_preamble,
    )


@router.post("/evaluate", response_model=HandwrittenEvaluationResponse)
async def evaluate(
    image: UploadFile = File(...),
    questions: str = Form(
        ...,
        description=(
            "JSON array of questions: "
            '[{"question_id":"Q1","question":"...","model_answer":"...","rubric":{...}}]'
        ),
    ),
):
    """Full vertical slice: image -> OCR -> segmentation -> evaluation per question."""
    try:
        specs = _questions_adapter.validate_python(json.loads(questions))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid `questions` JSON: {exc}")
    if not specs:
        raise HTTPException(status_code=422, detail="`questions` must contain at least one question.")

    data = await _read_image(image)
    try:
        return await run_in_threadpool(evaluate_handwritten_image, data, specs)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OCRUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("Handwritten evaluation failed")
        raise HTTPException(status_code=500, detail="Evaluation failed. Please try again later.")

