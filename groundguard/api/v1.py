"""v0.1.0 HTTP routes, unchanged in behavior.

Moved out of app.py so the app can be built by ``create_app``; each route
now reads its store from ``request.app.state`` instead of a module global.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
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


router = APIRouter()


def _v1_store(request: Request) -> EvaluationStore:
    store: EvaluationStore = request.app.state.v1_store
    return store


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
def dashboard_page() -> HTMLResponse:
    return dashboard()


@router.get("/evaluations")
def get_evaluations(
    request: Request,
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

    return _v1_store(request).get_all(
        limit=limit,
        offset=offset,
        system_decision=system_decision,
    )


@router.get("/evaluations/stats")
def get_evaluation_stats(request: Request) -> dict[str, float | int]:
    """
    Return aggregate statistics for persisted evaluations.
    """

    records = _v1_store(request).get_all()

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


@router.get("/evaluations/{evaluation_id}")
def get_evaluation(
    request: Request,
    evaluation_id: str,
) -> dict:
    """
    Return one persisted evaluation by ID.
    """

    record = _v1_store(request).get_by_id(evaluation_id)

    if record is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Evaluation not found",
        )

    return record


@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
)
def evaluate_answer(
    http_request: Request,
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

    evaluation_id = _v1_store(http_request).save(record)

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