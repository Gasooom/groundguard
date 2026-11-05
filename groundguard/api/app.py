"""GroundGuard HTTP service.

``create_app(settings)`` builds the application. The module-level ``app``
is built from the environment for ``uvicorn groundguard.api.app:app``.

- v0.1.0 routes (``/evaluate``, ``/evaluations``, ``/dashboard``, ...) keep
  their behavior and remain unauthenticated (legacy).
- ``/v2`` routes require an API key unless ``GROUNDGUARD_AUTH=disabled``,
  are rate limited per key, cap request bodies, and return errors as
  ``{"error": {"code", "message", "details"?}}``.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse

from groundguard.api.security import ApiError, RateLimiter
from groundguard.api.settings import Settings
from groundguard.api.v1 import router as v1_router
from groundguard.api.v2 import router as v2_router
from groundguard.storage import EvaluationStore
from groundguard.storage.v2_store import V2Store


logger = logging.getLogger("groundguard.api")


def _is_v2(request: Request) -> bool:
    return request.url.path.startswith("/v2/") or request.url.path == "/v2"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    application = FastAPI(
        title="GroundGuard",
        description="LLM reliability evaluation and hallucination detection system",
        version="0.1.0",
    )
    application.state.settings = settings
    application.state.v1_store = EvaluationStore(settings.database_path)
    application.state.v2_store = V2Store(settings.database_path)
    application.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
    if settings.auth == "disabled":
        logger.warning("GROUNDGUARD_AUTH=disabled: /v2 routes accept unauthenticated requests")

    @application.middleware("http")
    async def limit_v2_body(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if _is_v2(request) and request.method in ("POST", "PUT", "PATCH"):
            length = request.headers.get("content-length")
            if length is None:
                error = ApiError(411, "length_required", "requests to /v2 must send Content-Length")
                return JSONResponse(error.body(), status_code=error.status)
            if not length.isdigit() or int(length) > settings.max_body_bytes:
                error = ApiError(
                    413, "payload_too_large",
                    f"request body exceeds {settings.max_body_bytes} bytes",
                )
                return JSONResponse(error.body(), status_code=error.status)
        return await call_next(request)

    @application.exception_handler(ApiError)
    async def api_error(request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(error.body(), status_code=error.status, headers=error.headers)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> Any:
        if not _is_v2(request):
            return await request_validation_exception_handler(request, error)  # v1: FastAPI default
        details = jsonable_encoder(
            [{"loc": list(item.get("loc", ())), "msg": item.get("msg"), "type": item.get("type")}
             for item in error.errors()]
        )
        body = ApiError(422, "invalid_request", "the request does not match the schema", details=details).body()
        return JSONResponse(body, status_code=422)

    application.include_router(v1_router)
    application.include_router(v2_router)
    return application


app = create_app()
