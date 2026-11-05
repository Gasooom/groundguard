"""Minimal HTTP client for the GroundGuard /v2 API (standard library only).

    from groundguard.sdk import Client
    client = Client("http://localhost:8000", api_key="gg_...")
    result = client.evaluate(question="...", context="...", answer="...")
    result["decision"]["decision"]   # ACCEPT | FLAG | REJECT | HUMAN_REVIEW

Retries: 429 (honouring Retry-After) and 5xx responses, and connection
errors, up to ``max_retries`` times with exponential backoff. Other 4xx
errors are raised immediately as ``ApiRequestError``.

For in-process use without a server, call ``groundguard.pipeline.evaluate_v2``.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], HttpResponse]


class ApiRequestError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def urllib_transport(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
) -> HttpResponse:
    request = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (caller-chosen URL)
            return HttpResponse(response.status, dict(response.headers), response.read())
    except urllib.error.HTTPError as error:
        return HttpResponse(error.code, dict(error.headers or {}), error.read())


class Client:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._transport = transport
        self._sleep = sleep

    # ----------------------------------------------------------- requests

    def _request(self, method: str, path: str, *, params: Mapping[str, Any] | None = None,
                 payload: Any = None) -> Any:
        query = {key: value for key, value in (params or {}).items() if value is not None}
        url = self.base_url + path + (("?" + urllib.parse.urlencode(query)) if query else "")
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))

        attempt = 0
        while True:
            try:
                response = self._transport(method, url, headers, body, self.timeout)
            except (urllib.error.URLError, ConnectionError, TimeoutError) as error:
                if attempt >= self.max_retries:
                    raise ApiRequestError(0, "connection_error", str(error)) from error
                self._sleep(self.backoff_seconds * 2**attempt)
                attempt += 1
                continue

            if response.status == 429 or response.status >= 500:
                if attempt < self.max_retries:
                    retry_after = _header(response.headers, "retry-after")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else self.backoff_seconds * 2**attempt
                    self._sleep(delay)
                    attempt += 1
                    continue
            data = json.loads(response.body.decode("utf-8")) if response.body else None
            if response.status >= 400:
                envelope = (data or {}).get("error", {}) if isinstance(data, dict) else {}
                raise ApiRequestError(
                    response.status,
                    envelope.get("code", "http_error"),
                    envelope.get("message", f"HTTP {response.status}"),
                    envelope.get("details"),
                )
            return data

    # ---------------------------------------------------------- endpoints

    def evaluate(
        self,
        *,
        question: str,
        answer: str,
        context: str | None = None,
        contexts: Sequence[Mapping[str, str]] | None = None,
        policy: str | None = None,
        granularity: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"question": question, "answer": answer, "persist": persist}
        if context is not None:
            payload["context"] = context
        if contexts is not None:
            payload["contexts"] = [dict(item) for item in contexts]
        if policy is not None:
            payload["policy"] = policy
        if granularity is not None:
            payload["options"] = {"granularity": granularity}
        result: dict[str, Any] = self._request("POST", "/v2/evaluate", payload=payload)
        return result

    def evaluate_batch(self, items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        result = self._request("POST", "/v2/evaluate/batch", payload={"items": [dict(i) for i in items]})
        return list(result["results"])

    def get_evaluation(self, evaluation_id: str) -> dict[str, Any]:
        result: dict[str, Any] = self._request("GET", f"/v2/evaluations/{urllib.parse.quote(evaluation_id)}")
        return result

    def list_evaluations(self, *, limit: int = 50, decision: str | None = None,
                         cursor: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "GET", "/v2/evaluations", params={"limit": limit, "decision": decision, "cursor": cursor}
        )
        return result

    def stats(self, *, since: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = self._request("GET", "/v2/stats", params={"since": since})
        return result

    def policies(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/v2/policies"))


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None
