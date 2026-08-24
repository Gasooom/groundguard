from __future__ import annotations

from pydantic import BaseModel, Field


class EvaluateRequest(BaseModel):
    question: str = Field(min_length=1)
    context: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )


class EvaluateResponse(BaseModel):
    evaluation_id: str

    label: str
    reliable: bool
    system_decision: str

    grounding_score: float
    relevance_score: float
    contradiction_score: float

    reliability_score: float
    threshold: float

    grounding_label: str
    relevance_label: str
    contradiction_label: str

    pii_detected: bool
    pii_categories: list[str]

    prompt_injection_detected: bool

    safety_safe: bool
    safety_evidence: list[str]

    reason: str