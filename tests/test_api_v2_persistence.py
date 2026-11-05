from fastapi.testclient import TestClient

from groundguard.api.app import create_app
from groundguard.api.settings import Settings


GOOD = {"question": "When was Acme founded?", "context": "Acme was founded in 2010.",
        "answer": "Acme was founded in 2010."}
BAD = dict(GOOD, answer="Acme was founded in 1999.")


def make(tmp_path, **overrides):
    app = create_app(Settings(database_path=str(tmp_path / "gg.db"), **overrides))
    client = TestClient(app)
    key = app.state.v2_store.create_api_key("tenant-a")
    return app, client, {"X-API-Key": key}


def test_evaluate_persists_and_can_be_fetched(tmp_path):
    _, client, headers = make(tmp_path)
    created = client.post("/v2/evaluate", json=GOOD, headers=headers).json()
    assert created["evaluation_id"]
    fetched = client.get(f"/v2/evaluations/{created['evaluation_id']}", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["decision"] == "ACCEPT" and body["payload_mode"] == "redacted"
    assert body["report"]["decision"]["rule"] == "default.accept"


def test_persist_false_stores_nothing(tmp_path):
    _, client, headers = make(tmp_path)
    created = client.post("/v2/evaluate", json=dict(GOOD, persist=False), headers=headers).json()
    assert created["evaluation_id"] is None
    assert client.get("/v2/evaluations", headers=headers).json()["items"] == []


def test_tenants_cannot_see_each_others_evaluations(tmp_path):
    app, client, headers = make(tmp_path)
    other = {"X-API-Key": app.state.v2_store.create_api_key("tenant-b")}
    evaluation_id = client.post("/v2/evaluate", json=GOOD, headers=headers).json()["evaluation_id"]
    missing = client.get(f"/v2/evaluations/{evaluation_id}", headers=other)
    assert missing.status_code == 404
    assert missing.json() == {"error": {"code": "not_found", "message": "evaluation not found"}}
    assert client.get("/v2/stats", headers=other).json()["total"] == 0


def test_listing_with_cursor_and_decision_filter(tmp_path):
    _, client, headers = make(tmp_path)
    for payload in (GOOD, GOOD, GOOD, BAD):
        client.post("/v2/evaluate", json=payload, headers=headers)
    first = client.get("/v2/evaluations", params={"limit": 2}, headers=headers).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = client.get("/v2/evaluations", params={"limit": 2, "cursor": first["next_cursor"]}, headers=headers).json()
    assert len(second["items"]) == 2
    assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})
    rejected = client.get("/v2/evaluations", params={"decision": "REJECT"}, headers=headers).json()["items"]
    assert [i["rule"] for i in rejected] == ["grounding.contradicted"]
    assert client.get("/v2/evaluations", params={"cursor": "%%%"}, headers=headers).status_code == 422
    assert client.get("/v2/evaluations", params={"decision": "MAYBE"}, headers=headers).status_code == 422


def test_stats(tmp_path):
    _, client, headers = make(tmp_path)
    for payload in (GOOD, GOOD, BAD):
        client.post("/v2/evaluate", json=payload, headers=headers)
    stats = client.get("/v2/stats", headers=headers).json()
    assert stats["total"] == 3
    assert stats["decisions"]["ACCEPT"] == 2 and stats["decisions"]["REJECT"] == 1
    assert client.get("/v2/stats", params={"since": "yesterday"}, headers=headers).status_code == 422


def test_batch_reports_per_item_results_and_errors(tmp_path):
    _, client, headers = make(tmp_path)
    duplicate_ids = {"question": "q", "answer": "a",
                     "contexts": [{"id": "x", "text": "y"}, {"id": "x", "text": "z"}]}
    response = client.post("/v2/evaluate/batch", json={"items": [GOOD, BAD, duplicate_ids]}, headers=headers)
    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["index"] for r in results] == [0, 1, 2]
    assert results[0]["decision"]["decision"] == "ACCEPT"
    assert results[1]["decision"]["decision"] == "REJECT"
    assert results[2]["error"]["code"] == "invalid_input"
    assert len(client.get("/v2/evaluations", headers=headers).json()["items"]) == 2


def test_batch_limits_and_auth_order(tmp_path):
    _, client, headers = make(tmp_path, max_batch_items=2)
    too_many = client.post("/v2/evaluate/batch", json={"items": [GOOD] * 3}, headers=headers)
    assert too_many.status_code == 413 and too_many.json()["error"]["code"] == "batch_too_large"
    # Authentication is checked before the body is validated.
    assert client.post("/v2/evaluate/batch", json={"items": "nope"}).status_code == 401


def test_batch_items_are_charged_to_the_rate_limiter(tmp_path):
    _, client, headers = make(tmp_path, rate_limit_per_minute=3)
    assert client.post("/v2/evaluate/batch", json={"items": [GOOD] * 3}, headers=headers).status_code == 200
    assert client.post("/v2/evaluate", json=GOOD, headers=headers).status_code == 429
