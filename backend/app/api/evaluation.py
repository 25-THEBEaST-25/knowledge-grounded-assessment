import logging

from fastapi import APIRouter, HTTPException

from backend.app.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
)
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
    try:
        return evaluate_answer(
            question=request.question,
            student_answer=request.student_answer,
            model_answer=request.model_answer,
            rubric=request.rubric,
        )
    except GeminiUnavailableError as exc:
        logger.warning("Evaluation unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("Evaluation failed")
        raise HTTPException(
            status_code=500,
            detail="Evaluation failed. Please try again later.",
        )


@router.get("/trace/{trace_id}")

def get_evaluation_trace(trace_id: str):
    from backend.app.services.orchestrator_service import get_trace

    trace = get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found.")
    return trace