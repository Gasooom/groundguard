"""Authentication, rate limiting and the v2 error envelope."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import Request

from groundguard.api.settings import Settings
from groundguard.storage.v2_store import V2Store


class ApiError(Exception):
    """An error rendered as ``{"error": {"code", "message", "details"?}}``."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers or {}

    def body(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        return {"error": error}


class RateLimiter:
    """Token bucket per principal, in process memory.

    Capacity and refill are both ``per_minute`` tokens per minute. With
    several worker processes, each has its own buckets, so the effective
    limit multiplies; a shared limiter is needed for multi-replica
    deployments (ADR-009).
    """

    def __init__(self, per_minute: int, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.capacity = float(per_minute)
        self.rate = per_minute / 60.0
        self.clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str, cost: float = 1.0) -> float:
        """Take ``cost`` tokens. Returns 0 on success, else seconds to wait."""

        with self._lock:
            now = self.clock()
            tokens, updated = self._buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - updated) * self.rate)
            if tokens >= cost:
                self._buckets[key] = (tokens - cost, now)
                return 0.0
            self._buckets[key] = (tokens, now)
            return (cost - tokens) / self.rate


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    rate_key: str


def _presented_key(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.headers.get("x-api-key")


def authenticate(request: Request, *, cost: float = 1.0) -> Principal:
    """Resolve the caller and charge the rate limiter."""

    settings: Settings = request.app.state.settings
    store: V2Store = request.app.state.v2_store
    limiter: RateLimiter = request.app.state.rate_limiter

    if settings.auth == "disabled":
        principal = Principal(tenant_id="default", rate_key=f"ip:{request.client.host if request.client else '-'}")
    else:
        presented = _presented_key(request)
        tenant = store.authenticate(presented) if presented else None
        if tenant is None:
            raise ApiError(
                401,
                "unauthorized",
                "a valid API key is required (Authorization: Bearer gg_... or X-API-Key)",
                headers={"WWW-Authenticate": "Bearer"},
            )
        key_id = presented.split("_", 2)[1] if presented else "-"
        principal = Principal(tenant_id=tenant, rate_key=f"key:{key_id}")

    wait = limiter.acquire(principal.rate_key, cost)
    if wait > 0:
        raise ApiError(
            429,
            "rate_limited",
            "rate limit exceeded",
            details={"retry_after_seconds": math.ceil(wait)},
            headers={"Retry-After": str(math.ceil(wait))},
        )
    return principal
