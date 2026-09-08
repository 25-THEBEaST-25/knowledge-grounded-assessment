from typing import List, Optional

from pydantic import BaseModel, Field


class IngestedQuestionOut(BaseModel):
    question_id: str
    question_text: str
    model_answer: str
    max_score: Optional[float] = Field(default=None, description="Best-effort extraction; None if not confidently found.")
    source: str
    mapping_confidence: float = Field(ge=0, le=1)
    detected: bool


class MaterialIngestionResponse(BaseModel):
    questions: List[IngestedQuestionOut]
    raw_text_preview: str
    extraction_engine: str
