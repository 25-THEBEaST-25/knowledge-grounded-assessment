
import logging

from fastapi import APIRouter, HTTPException

from backend.app.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
)
from backend.app.services.orchestrator_service import evaluate_with_orchestrator, get_trace
from backend.app.services.evaluation_service import (
    GeminiUnavailableError,
    evaluate_answer,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/evaluation",
    tags=["Evaluation"],
)


@router.post("/evaluate", response_model=EvaluationResponse)
def evaluate(request: EvaluationRequest):
    """Evaluate an answer through the assessment orchestrator."""
    try:
        result = evaluate_with_orchestrator(
            assessment_id=request.assessment_id,
            question_id=request.question_id,
            question=request.question,
            student_answer=request.student_answer,
            model_answer=request.model_answer,
            rubric=request.rubric,
        )
        return result

    except GeminiUnavailableError as exc:
        logger.warning("Evaluation unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception:
        logger.exception("Orchestrated evaluation failed")
        raise HTTPException(
            status_code=500,
            detail="Evaluation failed. Please try again later.",
        ) from None


@router.get("/trace/{trace_id}")
def get_evaluation_trace(trace_id: str):
    """Retrieve the trace for a previous evaluation."""
    trace = get_trace(trace_id)

    if not trace:
        raise HTTPException(
            status_code=404,
            detail=f"Trace '{trace_id}' not found.",
        )

    return trace
