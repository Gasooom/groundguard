"""HTTP adapter for the v2 claim-level engine.

M2 scope: evaluation only, no persistence (storage with migrations is M7),
no authentication (M7). Input sizes are capped so a single request cannot
exhaust the process.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from groundguard.core.errors import InvalidInput
from groundguard.core.types import SourceDocument
from groundguard.pipeline import PipelineConfig, evaluate_v2


MAX_QUESTION_CHARS = 4_000
MAX_ANSWER_CHARS = 20_000
MAX_SOURCE_CHARS = 100_000
MAX_SOURCES = 50


class SourceIn(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=MAX_SOURCE_CHARS)


class OptionsIn(BaseModel):
    granularity: Literal["sentence", "clause", "conjunct"] = "conjunct"
    top_k: int = Field(default=5, ge=1, le=20)


class EvaluateV2Request(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    answer: str = Field(min_length=1, max_length=MAX_ANSWER_CHARS)
    context: str | None = Field(default=None, min_length=1, max_length=MAX_SOURCE_CHARS)
    contexts: list[SourceIn] | None = Field(default=None, min_length=1, max_length=MAX_SOURCES)
    options: OptionsIn = Field(default_factory=OptionsIn)

    @model_validator(mode="after")
    def _exactly_one_context_field(self) -> "EvaluateV2Request":
        if (self.context is None) == (self.contexts is None):
            raise ValueError("provide exactly one of 'context' or 'contexts'")
        return self


router = APIRouter(prefix="/v2", tags=["v2"])


@router.post("/evaluate")
def evaluate_answer_v2(request: EvaluateV2Request) -> Any:
    """Claim-level evaluation: claims, per-claim verdicts with evidence spans,
    derived labels, safety signals, and the provisional M2 decision."""

    try:
        report = evaluate_v2(
            question=request.question,
            answer=request.answer,
            context=request.context,
            contexts=(
                None
                if request.contexts is None
                else [SourceDocument(id=item.id, text=item.text) for item in request.contexts]
            ),
            config=PipelineConfig(
                granularity=request.options.granularity,
                top_k=request.options.top_k,
            ),
        )
    except InvalidInput as error:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_input", "message": str(error)}},
        )
    return report.to_dict()
