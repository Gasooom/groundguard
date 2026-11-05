"""HTTP adapter for the v2 claim-level engine.

Every route requires an API key unless the service runs with
GROUNDGUARD_AUTH=disabled (see groundguard.api.security). Input sizes are
capped so a single request cannot exhaust the process. Callers can
choose a builtin policy by name; uploading arbitrary policy files waits for
authentication (M7).
"""

from __future__ import annotations

from typing import Any, Literal

import base64
import math

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator

from groundguard.api.security import ApiError, Principal, RateLimiter, authenticate
from groundguard.agents.evaluate import evaluate_trace
from groundguard.api.settings import Settings
from groundguard.storage.v2_store import V2Store
from groundguard.core.errors import InvalidInput
from groundguard.core.types import SourceDocument
from groundguard.pipeline import PipelineConfig, evaluate_v2
from groundguard.policy import DEFAULT_POLICY, builtin_names, load_builtin


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
    policy: str = Field(default=DEFAULT_POLICY, description="Name of a builtin policy (GET /v2/policies).")
    persist: bool = Field(default=True, description="Store the evaluation (subject to the service payload mode).")

    @model_validator(mode="after")
    def _exactly_one_context_field(self) -> "EvaluateV2Request":
        if (self.context is None) == (self.contexts is None):
            raise ValueError("provide exactly one of 'context' or 'contexts'")
        if self.policy not in v2_policy_names():
            raise ValueError(f"unknown policy {self.policy!r}; known: {list(v2_policy_names())}")
        return self


def v2_policy_names() -> tuple[str, ...]:
    """Builtin policies for answer evaluation (v1-only and trace policies excluded)."""

    return tuple(
        name for name in builtin_names()
        if not load_builtin(name).requires_v1 and not load_builtin(name).for_traces
    )


def trace_policy_names() -> tuple[str, ...]:
    return tuple(name for name in builtin_names() if load_builtin(name).for_traces)


def require_principal(request: Request) -> Principal:
    return authenticate(request)


def require_principal_uncharged(request: Request) -> Principal:
    """Authenticate without charging the rate limiter (the route charges)."""

    return authenticate(request, cost=0.0)


router = APIRouter(prefix="/v2", tags=["v2"])


def _evaluate(request: EvaluateV2Request) -> dict[str, Any]:
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
            policy=load_builtin(request.policy),
        )
    except InvalidInput as error:
        raise ApiError(422, "invalid_input", str(error)) from None
    return report.to_dict()


def _store(http_request: Request) -> V2Store:
    store: V2Store = http_request.app.state.v2_store
    return store


def _persist(http_request: Request, principal: Principal, request: EvaluateV2Request, report: dict[str, Any]) -> str | None:
    if not request.persist:
        return None
    settings: Settings = http_request.app.state.settings
    return _store(http_request).save_evaluation(principal.tenant_id, report, settings.payload_mode)


@router.post("/evaluate")
def evaluate_answer_v2(
    request: EvaluateV2Request,
    http_request: Request,
    principal: Principal = Depends(require_principal),
) -> Any:
    """Claim-level evaluation: claims, per-claim verdicts with evidence spans,
    derived labels, safety signals, and the policy decision with its rule trace.
    The response carries ``evaluation_id`` (``null`` when ``persist`` is false)."""

    report = _evaluate(request)
    return {"evaluation_id": _persist(http_request, principal, request, report), **report}


class BatchRequest(BaseModel):
    items: list[EvaluateV2Request] = Field(min_length=1)


@router.post("/evaluate/batch")
def evaluate_batch(
    batch: BatchRequest,
    http_request: Request,
    principal: Principal = Depends(require_principal_uncharged),
) -> Any:
    """Evaluate up to GROUNDGUARD_MAX_BATCH_ITEMS answers. Each item is charged
    to the rate limiter. Item errors are reported per item, not for the batch."""

    settings: Settings = http_request.app.state.settings
    if len(batch.items) > settings.max_batch_items:
        raise ApiError(
            413, "batch_too_large", f"a batch may contain at most {settings.max_batch_items} items",
            details={"items": len(batch.items)},
        )
    limiter: RateLimiter = http_request.app.state.rate_limiter
    wait = limiter.acquire(principal.rate_key, float(len(batch.items)))
    if wait > 0:
        raise ApiError(
            429, "rate_limited", "rate limit exceeded",
            details={"retry_after_seconds": math.ceil(wait)},
            headers={"Retry-After": str(math.ceil(wait))},
        )
    results: list[dict[str, Any]] = []
    for index, item in enumerate(batch.items):
        try:
            report = _evaluate(item)
        except ApiError as error:
            results.append({"index": index, **error.body()})
            continue
        results.append({"index": index, "evaluation_id": _persist(http_request, principal, item, report), **report})
    return {"results": results}


def _encode_cursor(created_at: str, evaluation_id: str) -> str:
    return base64.urlsafe_b64encode(f"{created_at}|{evaluation_id}".encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        created_at, evaluation_id = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8").split("|", 1)
    except (ValueError, UnicodeDecodeError):
        raise ApiError(422, "invalid_cursor", "cursor is not valid") from None
    return created_at, evaluation_id


@router.get("/evaluations")
def list_evaluations(
    http_request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    decision: Literal["ACCEPT", "FLAG", "REJECT", "HUMAN_REVIEW"] | None = None,
    cursor: str | None = None,
    principal: Principal = Depends(require_principal),
) -> Any:
    """The caller's evaluations, newest first, without report bodies.
    Pass ``next_cursor`` back as ``cursor`` for the next page."""

    rows = _store(http_request).list_evaluations(
        principal.tenant_id,
        limit=limit,
        decision=decision,
        before=None if cursor is None else _decode_cursor(cursor),
    )
    next_cursor = _encode_cursor(rows[-1]["created_at"], rows[-1]["id"]) if len(rows) == limit else None
    return {"items": rows, "next_cursor": next_cursor}


@router.get("/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str, http_request: Request, principal: Principal = Depends(require_principal)) -> Any:
    record = _store(http_request).get_evaluation(principal.tenant_id, evaluation_id)
    if record is None:
        raise ApiError(404, "not_found", "evaluation not found")
    return record


@router.get("/stats")
def stats(
    http_request: Request,
    since: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}"),
    principal: Principal = Depends(require_principal),
) -> Any:
    """Aggregates over the caller's evaluations (SQL GROUP BY)."""

    return _store(http_request).stats(principal.tenant_id, since=since)


@router.get("/policies")
def list_policies(principal: Principal = Depends(require_principal)) -> Any:
    """Builtin policies usable with the v2 engine: rules, versions and content hashes."""

    return [load_builtin(name).to_dict() | {"hash": load_builtin(name).hash} for name in v2_policy_names()]


class TraceEvaluateRequest(BaseModel):
    trace: dict[str, Any]
    policy: str = Field(default="agent-default", description="Name of a builtin trace policy.")


@router.post("/traces/evaluate")
def evaluate_agent_trace(request: TraceEvaluateRequest, principal: Principal = Depends(require_principal)) -> Any:
    """Deterministic checks over an agent execution trace (tool allowlist,
    argument schemas, redundancy, budget, error handling, tool-output
    injection, state consistency, final-answer grounding against tool
    outputs, expected tools), then a trace policy decision. Not persisted."""

    if request.policy not in trace_policy_names():
        raise ApiError(422, "invalid_input", f"unknown trace policy {request.policy!r}; known: {list(trace_policy_names())}")
    try:
        return evaluate_trace(request.trace, policy=load_builtin(request.policy))
    except InvalidInput as error:
        raise ApiError(422, "invalid_input", str(error)) from None
