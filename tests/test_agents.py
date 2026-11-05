import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from groundguard.agents.evaluate import evaluate_trace
from groundguard.agents.schema_validate import validate
from groundguard.agents.trace import parse_trace
from groundguard.api.app import create_app
from groundguard.api.settings import Settings
from groundguard.core.errors import InvalidInput
from groundguard.policy import load_builtin, load_policy_text
from groundguard.policy.model import PolicyError


PROBES = json.loads((Path(__file__).resolve().parent / "agent_probes" / "traces.json").read_text())["probes"]

# probe id -> why the engine does not meet the expectation
KNOWN_LIMITATIONS = {
    "final_contradiction_01": "guards compare years, not full dates: '5 March 2026' vs '3 March 2026' is "
                              "NOT_ENOUGH_INFO (FLAG), not CONTRADICTED",
}


def _outcome(probe):
    report = evaluate_trace(probe["trace"])
    problems = []
    if set(report["failed_checks"]) != set(probe["expected_failed_checks"]):
        problems.append(f"failed checks {report['failed_checks']} != {probe['expected_failed_checks']}")
    if probe["must_accept"] and report["decision"]["decision"] != "ACCEPT":
        problems.append("expected ACCEPT")
    return report, problems


@pytest.mark.parametrize("probe", [p for p in PROBES if p["must_not_accept"]], ids=lambda p: p["trace"]["id"])
def test_no_trace_with_a_fault_is_accepted(probe):
    report, _ = _outcome(probe)
    assert report["decision"]["decision"] != "ACCEPT"


def test_failing_trace_probes_are_exactly_the_known_limitations():
    failing = {p["trace"]["id"]: problems for p in PROBES if (problems := _outcome(p)[1])}
    assert set(failing) == set(KNOWN_LIMITATIONS), failing


@pytest.mark.parametrize(
    "value, schema, errors",
    [
        ({"a": "x"}, {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}, 0),
        ({}, {"type": "object", "required": ["a"]}, 1),
        ({"a": 1}, {"type": "object", "properties": {"a": {"type": "string"}}}, 1),
        ({"a": True}, {"type": "object", "properties": {"a": {"type": "integer"}}}, 1),  # bool is not an integer
        ({"b": 1}, {"type": "object", "additionalProperties": False}, 1),
        ("ab", {"type": "string", "minLength": 3}, 1),
        ("abcd", {"type": "string", "maxLength": 3}, 1),
        ("x1", {"type": "string", "pattern": "^[0-9]+$"}, 1),
        (11, {"type": "integer", "minimum": 1, "maximum": 10}, 1),
        (2.5, {"type": "number"}, 0),
        ([1, "x"], {"type": "array", "items": {"type": "integer"}}, 1),
        ("b", {"enum": ["a"]}, 1),
        (None, {"type": ["string", "null"]}, 0),
        ("x", {"type": "string", "format": "email"}, 1),  # unsupported keyword is an error, not ignored
    ],
)
def test_schema_subset_validator(value, schema, errors):
    assert len(validate(value, schema)) == errors


def _base():
    return copy.deepcopy(PROBES[0]["trace"])


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda t: t.pop("goal"), "missing 'goal'"),
        (lambda t: t.update(extra=1), "unknown keys"),
        (lambda t: t["steps"].append({"kind": "dream"}), "kind must be"),
        (lambda t: t["steps"][0].update(error="boom"), "exactly one of 'result' or 'error'"),
        (lambda t: t["tools"].append(t["tools"][0]), "duplicate tool names"),
        (lambda t: t.update(policy={"max_tool_calls": 0}), "positive integer"),
        (lambda t: t.update(policy={"budget": 3}), "only 'forbidden_tools'"),
    ],
)
def test_trace_parsing_rejects_malformed_traces(mutate, message):
    trace = _base()
    mutate(trace)
    with pytest.raises(InvalidInput, match=message):
        parse_trace(trace)


def test_report_contains_checks_final_answer_and_manifest():
    report = evaluate_trace(PROBES[0]["trace"])
    assert [c["name"] for c in report["checks"]][:3] == ["tool_allowlist", "argument_validity", "redundant_calls"]
    statuses = {c["name"]: c["status"] for c in report["checks"]}
    assert statuses["call_budget"] == "NOT_APPLICABLE" and statuses["tool_selection"] == "NOT_APPLICABLE"
    assert report["final_answer"]["verdicts"][0]["label"] == "SUPPORTED"
    assert report["final_answer"]["verdicts"][0]["evidence"][0]["source_id"] == "step-0:get_order"
    assert report["manifest"]["policy"]["id"] == "agent-default"


def test_tool_selection_reports_match_kinds():
    probe = next(p for p in PROBES if p["trace"]["id"] == "tool_selection_01")
    check = next(c for c in evaluate_trace(probe["trace"])["checks"] if c["name"] == "tool_selection")
    assert check["match"] == {"exact_sequence": False, "subsequence": False, "set": False}


def test_trace_check_condition_is_validated():
    with pytest.raises(PolicyError, match="must be one of"):
        load_policy_text('''
[policy]
id = "t"
version = "1"
description = "t"
[[rule]]
id = "r"
when = { trace_check_failed = "vibes" }
decision = "REJECT"
description = "d"
[default]
id = "a"
decision = "ACCEPT"
description = "a"
''')
    assert load_builtin("agent-default").for_traces is True
    assert load_builtin("default").for_traces is False


def test_trace_api(tmp_path):
    client = TestClient(create_app(Settings(database_path=str(tmp_path / "gg.db"), auth="disabled")))
    probe = next(p for p in PROBES if p["trace"]["id"] == "unknown_tool_01")
    response = client.post("/v2/traces/evaluate", json={"trace": probe["trace"]})
    assert response.status_code == 200
    assert response.json()["decision"]["rule"] == "trace.tool_allowlist"

    bad = client.post("/v2/traces/evaluate", json={"trace": {"id": "x"}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_input"
    wrong_policy = client.post("/v2/traces/evaluate", json={"trace": probe["trace"], "policy": "default"})
    assert wrong_policy.status_code == 422
    # Trace policies are not offered for answer evaluation.
    assert "agent-default" not in {p["id"] for p in client.get("/v2/policies").json()}
