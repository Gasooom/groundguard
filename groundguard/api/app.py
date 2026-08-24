from __future__ import annotations

import os

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from groundguard.api.dashboard import dashboard
from groundguard.api.schemas import (
    EvaluateRequest,
    EvaluateResponse,
)
from groundguard.application.evaluator import evaluate
from groundguard.evaluation.evaluation_record import (
    EvaluationRecord,
)
from groundguard.storage import EvaluationStore


DATABASE_PATH = os.getenv(
    "GROUNDGUARD_DATABASE_PATH",
    "groundguard.db",
)


app = FastAPI(
    title="GroundGuard",
    description=(
        "LLM reliability evaluation and "
        "hallucination detection system"
    ),
    version="0.1.0",
)


_store = EvaluationStore(DATABASE_PATH)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/dashboard",
    response_class=HTMLResponse,
)
def dashboard_page() -> HTMLResponse:
    return dashboard()


@app.get("/evaluations")
def get_evaluations(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    system_decision: str | None = Query(
        default=None,
    ),
) -> list[dict]:
    """
    Return persisted evaluations with pagination
    and optional decision filtering.
    """

    return _store.get_all(
        limit=limit,
        offset=offset,
        system_decision=system_decision,
    )


@app.get("/evaluations/stats")
def get_evaluation_stats() -> dict[str, float | int]:
    """
    Return aggregate statistics for persisted evaluations.
    """

    records = _store.get_all()

    total = len(records)

    if total == 0:
        return {
            "total": 0,
            "accept": 0,
            "flag": 0,
            "reject": 0,
            "accept_rate": 0.0,
            "flag_rate": 0.0,
            "reject_rate": 0.0,
            "average_reliability": 0.0,
            "safety_violations": 0,
        }

    accept = sum(
        record["system_decision"] == "ACCEPT"
        for record in records
    )

    flag = sum(
        record["system_decision"] == "FLAG"
        for record in records
    )

    reject = sum(
        record["system_decision"] == "REJECT"
        for record in records
    )

    average_reliability = (
        sum(
            record["reliability_score"]
            for record in records
        )
        / total
    )

    safety_violations = sum(
        not record["safety_safe"]
        for record in records
    )

    return {
        "total": total,
        "accept": accept,
        "flag": flag,
        "reject": reject,
        "accept_rate": round(
            accept / total,
            4,
        ),
        "flag_rate": round(
            flag / total,
            4,
        ),
        "reject_rate": round(
            reject / total,
            4,
        ),
        "average_reliability": round(
            average_reliability,
            4,
        ),
        "safety_violations": safety_violations,
    }


@app.get("/evaluations/{evaluation_id}")
def get_evaluation(
    evaluation_id: str,
) -> dict:
    """
    Return one persisted evaluation by ID.
    """

    record = _store.get_by_id(evaluation_id)

    if record is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Evaluation not found",
        )

    return record


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

    record = EvaluationRecord.from_evaluation(
        question=request.question,
        context=request.context,
        answer=request.answer,
        result=result,
    )

    evaluation_id = _store.save(record)

    return EvaluateResponse(
        evaluation_id=evaluation_id,
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
        prompt_injection_detected=(
            result.prompt_injection.detected
        ),
        safety_safe=result.safety.safe,
        safety_evidence=result.safety.evidence,
        reason=result.decision.reason,
    )