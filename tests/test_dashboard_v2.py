import json
import re

from fastapi.testclient import TestClient

from groundguard.api.app import create_app
from groundguard.api.settings import Settings


def make(tmp_path, **overrides):
    app = create_app(Settings(database_path=str(tmp_path / "gg.db"), **overrides))
    return app, TestClient(app)


def test_dashboard_is_self_contained_and_served_with_security_headers(tmp_path):
    _, client = make(tmp_path)
    response = client.get("/v2/dashboard")
    assert response.status_code == 200  # the page needs no key; its data calls do
    html = response.text
    assert "<title>GroundGuard Console</title>" in html
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    # No external resources and no HTML-string sinks: all data goes through textContent.
    assert not re.search(r"(?:src|href)=\"https?://", html)
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert sink not in html


def test_benchmark_runs_endpoints(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    run = {"kind": "claims", "predictions_hash": "abc", "metrics": {"all": {}},
           "manifest": {"dataset": {"id": "d", "version": "1"}, "config": {"engine": "v2", "split": "dev",
                        "policy": {"id": "default"}}, "git": {"commit": "f00"}}}
    (results / "run-a.json").write_text(json.dumps(run))
    (results / "notes.txt").write_text("ignored")
    (tmp_path / "secret.json").write_text("{}")
    app, client = make(tmp_path, results_dir=str(results))
    headers = {"X-API-Key": app.state.v2_store.create_api_key("t")}

    listing = client.get("/v2/benchmarks/runs", headers=headers).json()
    assert listing["results_dir_present"] is True
    assert [r["name"] for r in listing["runs"]] == ["run-a.json"]
    assert listing["runs"][0]["policy"] == "default"

    detail = client.get("/v2/benchmarks/runs/run-a.json", headers=headers).json()
    assert detail["metrics"] == {"all": {}}
    assert "predictions" not in detail

    for bad in ("../secret.json", "..%2Fsecret.json", ".hidden.json", "notes.txt", "missing.json"):
        assert client.get(f"/v2/benchmarks/runs/{bad}", headers=headers).status_code == 404
    assert client.get("/v2/benchmarks/runs").status_code == 401


def test_benchmark_runs_without_results_directory(tmp_path):
    _, client = make(tmp_path, auth="disabled", results_dir=str(tmp_path / "absent"))
    assert client.get("/v2/benchmarks/runs").json() == {"results_dir_present": False, "runs": []}


def test_committed_run_files_are_listed_from_a_checkout(tmp_path):
    _, client = make(tmp_path, auth="disabled")
    names = {r["name"] for r in client.get("/v2/benchmarks/runs").json()["runs"]}
    assert "v0.1.0-baseline.context.json" in names
