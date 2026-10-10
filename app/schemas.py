from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class ExtractedField(BaseModel):
    value: str | None
    confidence: float = Field(ge=0, le=1)
    evidence: str | None = None

class Citation(BaseModel):
    policy_id: str
    clause: str
    source: str
    quote: str

class ConsultationResponse(BaseModel):
    consultation_id: str
    created_at: datetime
    status: Literal["completed", "needs_review"]
    ocr_text: str
    extracted_fields: dict[str, ExtractedField]
    answer: str
    citations: list[Citation]
    needs_human_review: bool
    warnings: list[str] = []

class HealthResponse(BaseModel):
    status: str
    app: str
