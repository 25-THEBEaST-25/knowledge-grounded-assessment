from fastapi import APIRouter, HTTPException

from backend.app.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
)
from backend.app.services.evaluation_service import evaluate_answer


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

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {exc}",
        )