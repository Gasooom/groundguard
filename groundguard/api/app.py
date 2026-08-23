from __future__ import annotations

from fastapi import FastAPI
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


app = FastAPI(
    title="GroundGuard",
    description=(
        "LLM reliability evaluation and "
        "hallucination detection system"
    ),
    version="0.1.0",
)


_evaluation_history: list[EvaluationRecord] = []


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
def get_evaluations() -> list[dict]:
    """
    Return evaluations recorded during the current process.
    """

    return [
        record.to_dict()
        for record in _evaluation_history
    ]


@app.get("/evaluations/stats")
def get_evaluation_stats() -> dict[str, float | int]:
    """
    Return aggregate statistics for evaluations recorded
    during the current process.
    """

    total = len(_evaluation_history)

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
        record.system_decision == "ACCEPT"
        for record in _evaluation_history
    )

    flag = sum(
        record.system_decision == "FLAG"
        for record in _evaluation_history
    )

    reject = sum(
        record.system_decision == "REJECT"
        for record in _evaluation_history
    )

    average_reliability = (
        sum(
            record.reliability_score
            for record in _evaluation_history
        )
        / total
    )

    safety_violations = sum(
        not record.safety_safe
        for record in _evaluation_history
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

    _evaluation_history.append(record)

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
        prompt_injection_detected=(
            result.prompt_injection.detected
        ),
        safety_safe=result.safety.safe,
        safety_evidence=result.safety.evidence,
        reason=result.decision.reason,
    )