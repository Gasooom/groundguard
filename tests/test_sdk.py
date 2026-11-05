import pytest
from fastapi.testclient import TestClient

from groundguard.api.app import create_app
from groundguard.api.settings import Settings
from groundguard.sdk import ApiRequestError, Client, HttpResponse


def in_process(tmp_path, **overrides):
    """A transport that sends SDK requests to the real app via TestClient."""

    app = create_app(Settings(database_path=str(tmp_path / "gg.db"), **overrides))
    test_client = TestClient(app)

    def transport(method, url, headers, body, timeout):
        path = url.removeprefix("http://groundguard.test")
        response = test_client.request(method, path, headers=dict(headers), content=body)
        return HttpResponse(response.status_code, dict(response.headers), response.content)

    return app, transport


def test_sdk_round_trip_against_the_real_app(tmp_path):
    app, transport = in_process(tmp_path)
    key = app.state.v2_store.create_api_key("tenant-a")
    client = Client("http://groundguard.test", api_key=key, transport=transport)

    result = client.evaluate(question="When was Acme founded?", context="Acme was founded in 2010.",
                             answer="Acme was founded in 2010.", policy="strict")
    assert result["decision"]["decision"] == "ACCEPT"
    assert result["decision"]["policy"]["id"] == "strict"
    assert client.get_evaluation(result["evaluation_id"])["decision"] == "ACCEPT"
    assert client.list_evaluations(limit=10)["items"][0]["id"] == result["evaluation_id"]
    assert client.stats()["total"] == 1
    assert {p["id"] for p in client.policies()} == {"default", "provisional-m2", "strict"}

    batch = client.evaluate_batch([
        {"question": "When was Acme founded?", "context": "Acme was founded in 2010.", "answer": "Acme was founded in 1999."}
    ])
    assert batch[0]["decision"]["decision"] == "REJECT"


def test_sdk_raises_typed_errors_without_retrying_4xx(tmp_path):
    app, transport = in_process(tmp_path)
    sleeps = []
    client = Client("http://groundguard.test", api_key="gg_bad_key", transport=transport, sleep=sleeps.append)
    with pytest.raises(ApiRequestError) as raised:
        client.stats()
    assert (raised.value.status, raised.value.code) == (401, "unauthorized")
    assert sleeps == []


def test_sdk_retries_429_honouring_retry_after_then_succeeds():
    calls = []

    def transport(method, url, headers, body, timeout):
        calls.append(url)
        if len(calls) < 3:
            return HttpResponse(429, {"Retry-After": "2"}, b'{"error": {"code": "rate_limited", "message": "slow down"}}')
        return HttpResponse(200, {}, b'{"total": 0}')

    sleeps = []
    client = Client("http://x.test", transport=transport, sleep=sleeps.append)
    assert client.stats() == {"total": 0}
    assert sleeps == [2.0, 2.0]


def test_sdk_gives_up_after_max_retries():
    sleeps = []
    client = Client(
        "http://x.test", max_retries=2, backoff_seconds=0.1, sleep=sleeps.append,
        transport=lambda *args: HttpResponse(503, {}, b'{"error": {"code": "unavailable", "message": "down"}}'),
    )
    with pytest.raises(ApiRequestError) as raised:
        client.stats()
    assert raised.value.status == 503
    assert sleeps == [0.1, 0.2]


def test_sdk_retries_connection_errors():
    attempts = []

    def transport(*args):
        attempts.append(1)
        raise ConnectionError("refused")

    client = Client("http://x.test", max_retries=1, sleep=lambda s: None, transport=transport)
    with pytest.raises(ApiRequestError, match="connection_error"):
        client.stats()
    assert len(attempts) == 2


def test_sdk_validates_configuration():
    with pytest.raises(ValueError):
        Client("localhost:8000")
    with pytest.raises(ValueError):
        Client("http://x.test", max_retries=-1)
