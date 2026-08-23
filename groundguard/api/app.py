from __future__ import annotations

from fastapi import FastAPI

from groundguard.application.evaluator import evaluate
from groundguard.api.schemas import (
    EvaluateRequest,
    EvaluateResponse,
)


app = FastAPI(
    title="GroundGuard",
    description="LLM reliability evaluation and hallucination detection system",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/evaluate",
    response_model=EvaluateResponse,
)
def evaluate_answer(
    request: EvaluateRequest,
) -> EvaluateResponse:
    result = evaluate(
        question=request.question,
        context=request.context,
        answer=request.answer,
        threshold=request.threshold,
    )

    return EvaluateResponse(
        label=result.decision.label,
        reliable=result.decision.reliable,
        system_decision=result.decision.system_decision,
        grounding_score=result.decision.grounding_score,
        relevance_score=result.decision.relevance_score,
        contradiction_score=result.decision.contradiction_score,
        reliability_score=result.decision.reliability_score,
        threshold=result.decision.threshold,
        grounding_label=result.grounding.label,
        relevance_label=result.relevance.label,
        contradiction_label=result.contradiction.label,
        pii_detected=result.pii.detected,
        pii_categories=list(result.pii.categories),
        prompt_injection_detected=result.prompt_injection.detected,
        safety_safe=result.safety.safe,
        safety_evidence=result.safety.evidence,
        reason=result.decision.reason,
    )