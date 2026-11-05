import pytest
from fastapi.testclient import TestClient

from groundguard.api.app import create_app
from groundguard.api.security import RateLimiter
from groundguard.api.settings import Settings
from groundguard.cli import main


PAYLOAD = {"question": "When was Acme founded?", "context": "Acme was founded in 2010.",
           "answer": "Acme was founded in 2010."}


def make(tmp_path, **overrides):
    settings = Settings(database_path=str(tmp_path / "gg.db"), **overrides)
    app = create_app(settings)
    return app, TestClient(app)


def test_v2_requires_a_key_and_returns_the_error_envelope(tmp_path):
    _, client = make(tmp_path)
    response = client.post("/v2/evaluate", json=PAYLOAD)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthorized"
    assert client.get("/v2/policies").status_code == 401


def test_bearer_and_x_api_key_headers_are_accepted(tmp_path):
    app, client = make(tmp_path)
    key = app.state.v2_store.create_api_key("tenant-a")
    assert client.post("/v2/evaluate", json=PAYLOAD, headers={"Authorization": f"Bearer {key}"}).status_code == 200
    assert client.post("/v2/evaluate", json=PAYLOAD, headers={"X-API-Key": key}).status_code == 200
    assert client.post("/v2/evaluate", json=PAYLOAD, headers={"X-API-Key": key + "x"}).status_code == 401


def test_revoked_keys_are_rejected(tmp_path):
    app, client = make(tmp_path)
    store = app.state.v2_store
    key = store.create_api_key("tenant-a")
    store.revoke_api_key(key.split("_", 2)[1])
    assert client.post("/v2/evaluate", json=PAYLOAD, headers={"X-API-Key": key}).status_code == 401


def test_rate_limit_returns_429_with_retry_after(tmp_path):
    app, client = make(tmp_path, rate_limit_per_minute=2)
    key = app.state.v2_store.create_api_key("tenant-a")
    headers = {"X-API-Key": key}
    assert [client.post("/v2/evaluate", json=PAYLOAD, headers=headers).status_code for _ in range(2)] == [200, 200]
    limited = client.post("/v2/evaluate", json=PAYLOAD, headers=headers)
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1
    assert limited.json()["error"]["code"] == "rate_limited"
    # Another key has its own bucket.
    other = app.state.v2_store.create_api_key("tenant-b")
    assert client.post("/v2/evaluate", json=PAYLOAD, headers={"X-API-Key": other}).status_code == 200


def test_body_size_limit(tmp_path):
    app, client = make(tmp_path, auth="disabled", max_body_bytes=2048)
    big = dict(PAYLOAD, context="x " * 2000)
    response = client.post("/v2/evaluate", json=big)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_v2_validation_errors_use_the_envelope_but_v1_keeps_fastapi_default(tmp_path):
    _, client = make(tmp_path, auth="disabled")
    v2 = client.post("/v2/evaluate", json={"question": "q"})
    assert v2.status_code == 422
    assert v2.json()["error"]["code"] == "invalid_request"
    assert {"loc", "msg", "type"} <= set(v2.json()["error"]["details"][0])

    v1 = client.post("/evaluate", json={"question": "q"})
    assert v1.status_code == 422
    assert "detail" in v1.json()


def test_v1_routes_stay_unauthenticated(tmp_path):
    _, client = make(tmp_path)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/evaluate", json=PAYLOAD).status_code == 200


def test_rate_limiter_refills_over_time():
    now = [0.0]
    limiter = RateLimiter(60, clock=lambda: now[0])  # one token per second, capacity 60
    assert all(limiter.acquire("k") == 0.0 for _ in range(60))
    wait = limiter.acquire("k")
    assert wait == pytest.approx(1.0)
    now[0] += 1.0
    assert limiter.acquire("k") == 0.0
    assert limiter.acquire("other") == 0.0


@pytest.mark.parametrize(
    "env, message",
    [
        ({"GROUNDGUARD_AUTH": "off"}, "GROUNDGUARD_AUTH"),
        ({"GROUNDGUARD_PAYLOAD_MODE": "all"}, "PAYLOAD_MODE"),
        ({"GROUNDGUARD_RATE_LIMIT_PER_MINUTE": "0"}, "RATE_LIMIT"),
        ({"GROUNDGUARD_MAX_BODY_BYTES": "10"}, "MAX_BODY_BYTES"),
    ],
)
def test_settings_validation(env, message):
    with pytest.raises(ValueError, match=message):
        Settings.from_env(env)


def test_settings_defaults_are_secure():
    settings = Settings.from_env({})
    assert settings.auth == "required"
    assert settings.payload_mode == "redacted"


def test_keys_cli(tmp_path, capsys):
    db = str(tmp_path / "gg.db")
    assert main(["keys", "create", "--tenant", "acme", "--label", "ci", "--db", db]) == 0
    key = capsys.readouterr().out.strip()
    assert key.startswith("gg_")
    assert main(["keys", "list", "--db", db]) == 0
    listing = capsys.readouterr().out
    assert "tenant=acme" in listing and "active" in listing and key.split("_", 2)[2] not in listing
    key_id = key.split("_", 2)[1]
    assert main(["keys", "revoke", key_id, "--db", db]) == 0
    assert main(["keys", "revoke", key_id, "--db", db]) == 2
