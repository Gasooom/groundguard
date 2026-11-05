import pytest
from fastapi.testclient import TestClient

from groundguard.api.app import app
from groundguard.core.errors import InvalidInput
from groundguard.core.types import ClaimVerdict, SourceDocument
from groundguard.pipeline import PipelineConfig, derive_v1_labels, evaluate_v2
from groundguard.policy import decide, facts_from_v2, load_builtin


client = TestClient(app)


def _verdict(label):
    return ClaimVerdict(claim_id="c", label=label, raw_score=0.0, evidence=(), verifier="t@1", rationale="")


@pytest.mark.parametrize(
    "labels, expected",
    [
        (["SUPPORTED", "SUPPORTED"], ("SUPPORTED", "NOT_CONTRADICTORY")),
        (["SUPPORTED", "NOT_ENOUGH_INFO"], ("PARTIALLY_SUPPORTED", "NOT_CONTRADICTORY")),
        (["NOT_ENOUGH_INFO"], ("UNSUPPORTED", "NOT_CONTRADICTORY")),
        (["SUPPORTED", "CONTRADICTED"], ("PARTIALLY_SUPPORTED", "CONTRADICTORY")),
        (["CONTRADICTED"], ("UNSUPPORTED", "CONTRADICTORY")),
        ([], ("UNSUPPORTED", "NOT_CONTRADICTORY")),
    ],
)
def test_derived_v1_labels(labels, expected):
    derived = derive_v1_labels([_verdict(label) for label in labels])
    assert (derived["grounding_label"], derived["contradiction_label"]) == expected


@pytest.mark.parametrize(
    "labels, relevant, pii, injection, rule, decision",
    [
        (["SUPPORTED"], True, True, False, "safety.pii", "REJECT"),
        (["SUPPORTED"], True, False, True, "safety.prompt_injection", "REJECT"),
        (["SUPPORTED", "CONTRADICTED"], True, False, False, "grounding.contradicted", "REJECT"),
        (["SUPPORTED"], False, False, False, "relevance.irrelevant", "REJECT"),
        (["NOT_ENOUGH_INFO"], True, False, False, "grounding.none_supported", "REJECT"),
        ([], True, False, False, "grounding.none_supported", "REJECT"),
        (["SUPPORTED", "NOT_ENOUGH_INFO"], True, False, False, "grounding.not_enough_info", "FLAG"),
        (["SUPPORTED"], True, False, False, "default.accept", "ACCEPT"),
        # Priority: safety beats contradiction beats relevance.
        (["CONTRADICTED"], False, True, False, "safety.pii", "REJECT"),
        (["CONTRADICTED"], False, False, False, "grounding.contradicted", "REJECT"),
    ],
)
def test_provisional_m2_policy_rules_in_priority_order(labels, relevant, pii, injection, rule, decision):
    # Same cases as the M2 provisional-rule test; the rules now live in
    # groundguard/policy/builtin/provisional-m2.toml.
    result = decide(
        load_builtin("provisional-m2"),
        facts_from_v2(
            [_verdict(label) for label in labels],
            relevant=relevant,
            pii_detected=pii,
            injection_detected=injection,
        ),
    )
    assert (result.rule, result.decision) == (rule, decision)


def test_provisional_m2_rule_order():
    policy = load_builtin("provisional-m2")
    assert [r.id for r in policy.rules] + [policy.default_rule_id] == [
        "safety.pii",
        "safety.prompt_injection",
        "grounding.contradicted",
        "relevance.irrelevant",
        "grounding.none_supported",
        "grounding.not_enough_info",
        "default.accept",
    ]


def test_pipeline_uses_default_policy_and_records_it_in_the_manifest():
    report = evaluate_v2(
        question="What is Drug X approved for?",
        context="Drug X is approved to treat hypertension in adults.",
        answer="Drug X is approved to treat hypertension in children.",
    )
    assert (report.decision.decision, report.decision.rule) == ("HUMAN_REVIEW", "grounding.qualifier_mismatch")
    assert report.decision.matched_rules == ("grounding.qualifier_mismatch", "grounding.none_supported", "grounding.not_enough_info")
    default = load_builtin("default")
    assert report.manifest["policy"] == {"id": "default", "version": "2.0.0", "hash": default.hash}

    m2 = evaluate_v2(
        question="What is Drug X approved for?",
        context="Drug X is approved to treat hypertension in adults.",
        answer="Drug X is approved to treat hypertension in children.",
        policy=load_builtin("provisional-m2"),
    )
    assert (m2.decision.decision, m2.decision.rule) == ("REJECT", "grounding.none_supported")
    assert m2.manifest["config_hash"] != report.manifest["config_hash"]


def test_pipeline_rejects_v1_only_policies():
    with pytest.raises(InvalidInput, match="only works with the v1 engine"):
        evaluate_v2(question="q", answer="a", context="c", policy=load_builtin("v1-compat"))


def test_evaluate_v2_end_to_end_reports_claims_verdicts_and_manifest():
    report = evaluate_v2(
        question="What does Orion Labs sell?",
        context="Orion Labs sells project-management software and encrypted messaging tools.",
        answer="Orion Labs sells project-management software, encrypted messaging tools, and accounting software.",
    )

    assert [claim.text for claim in report.claims] == [
        "Orion Labs sells project-management software",
        "Orion Labs sells encrypted messaging tools",
        "Orion Labs sells accounting software",
    ]
    assert [verdict.label for verdict in report.verdicts] == ["SUPPORTED", "SUPPORTED", "NOT_ENOUGH_INFO"]
    assert report.labels["grounding_label"] == "PARTIALLY_SUPPORTED"
    assert (report.decision.decision, report.decision.rule) == ("FLAG", "grounding.not_enough_info")
    assert report.manifest["engine"] == "v2"
    assert report.manifest["policy"]["id"] == "default"
    assert report.manifest["verifier_chain"] == ["guards@2", "structured_facts@1", "lexical@1-content-1"]
    assert len(report.manifest["config_hash"]) == 64


def test_non_assertive_claims_are_reported_but_not_verified():
    report = evaluate_v2(
        question="How long is the warranty?",
        context="The warranty lasts two years.",
        answer="The warranty lasts two years. Is that enough?",
    )
    assert [claim.assertive for claim in report.claims] == [True, False]
    assert len(report.verdicts) == 1


def test_multiple_sources_keep_their_ids():
    report = evaluate_v2(
        question="Where is Acme based?",
        contexts=[
            SourceDocument("doc-a", "Acme sells routers."),
            SourceDocument("doc-b", "Acme is based in Kigali."),
        ],
        answer="Acme is based in Kigali.",
    )
    (verdict,) = report.verdicts
    assert verdict.label == "SUPPORTED"
    assert verdict.evidence[0].source_id == "doc-b"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"question": " ", "answer": "a", "context": "c"},
        {"question": "q", "answer": " ", "context": "c"},
        {"question": "q", "answer": "a"},
        {"question": "q", "answer": "a", "context": "c", "contexts": [SourceDocument("x", "y")]},
        {"question": "q", "answer": "a", "contexts": []},
        {"question": "q", "answer": "a", "contexts": [SourceDocument("x", "y"), SourceDocument("x", "z")]},
    ],
)
def test_evaluate_v2_rejects_invalid_input(kwargs):
    with pytest.raises(InvalidInput):
        evaluate_v2(**kwargs)


def test_config_validation():
    with pytest.raises(InvalidInput):
        PipelineConfig(granularity="word")
    with pytest.raises(InvalidInput):
        PipelineConfig(top_k=0)


def test_api_v2_evaluate_returns_contradiction_with_evidence_span():
    context = "Acme Corp is headquartered in Berlin, Germany. It was founded in 2010."
    response = client.post(
        "/v2/evaluate",
        json={"question": "Where is Acme headquartered?", "context": context,
              "answer": "Acme is not headquartered in Berlin."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"]["decision"] == "REJECT"
    assert data["decision"]["rule"] == "grounding.contradicted"
    (verdict,) = data["verdicts"]
    assert verdict["label"] == "CONTRADICTED"
    assert verdict["signals"]["fired"] == ["negation"]
    span = verdict["evidence"][0]["span"]
    assert context[span["start"] : span["end"]] == "Acme Corp is headquartered in Berlin, Germany"


def test_api_v2_accepts_multiple_contexts_and_options():
    response = client.post(
        "/v2/evaluate",
        json={
            "question": "Where is Acme based?",
            "contexts": [{"id": "doc-1", "text": "Acme is based in Kigali."}],
            "answer": "Acme is based in Kigali.",
            "options": {"granularity": "sentence", "top_k": 3},
        },
    )
    assert response.status_code == 200
    assert response.json()["manifest"]["config"]["granularity"] == "sentence"


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "q", "answer": "a"},                                    # no context
        {"question": "q", "answer": "a", "context": "c", "contexts": [{"id": "x", "text": "y"}]},
        {"question": "q", "answer": "a" * 20_001, "context": "c"},           # oversize
        {"question": "q", "answer": "a", "context": "c", "options": {"top_k": 0}},
        {"question": "q", "answer": "a", "context": "c", "options": {"granularity": "word"}},
    ],
)
def test_api_v2_rejects_invalid_requests(payload):
    assert client.post("/v2/evaluate", json=payload).status_code == 422


def test_api_v2_maps_library_validation_errors_to_error_envelope():
    response = client.post(
        "/v2/evaluate",
        json={"question": "q", "answer": "a", "contexts": [{"id": "x", "text": "y"}, {"id": "x", "text": "z"}]},
    )
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "invalid_input", "message": "source ids must be unique"}}


def test_v1_evaluate_endpoint_is_unchanged_by_v2():
    response = client.post(
        "/evaluate",
        json={"question": "Where is Acme headquartered?",
              "context": "Acme Corp is headquartered in Berlin, Germany.",
              "answer": "Acme is not headquartered in Berlin."},
    )
    # v1 still accepts this negation (documented audit finding); v2 rejects it.
    assert response.status_code == 200
    assert response.json()["system_decision"] == "ACCEPT"


def test_api_v2_policy_selection():
    payload = {
        "question": "What is Drug X approved for?",
        "context": "Drug X is approved to treat hypertension in adults.",
        "answer": "Drug X is approved to treat hypertension in children.",
    }
    decisions = {}
    for name in ("default", "provisional-m2", "strict"):
        response = client.post("/v2/evaluate", json=payload | {"policy": name})
        assert response.status_code == 200
        data = response.json()
        assert data["decision"]["policy"]["id"] == name
        decisions[name] = data["decision"]["decision"]
    assert decisions == {"default": "HUMAN_REVIEW", "provisional-m2": "REJECT", "strict": "REJECT"}

    for bad in ("v1-compat", "nonexistent"):
        assert client.post("/v2/evaluate", json=payload | {"policy": bad}).status_code == 422


def test_api_v2_lists_v2_policies_with_hashes():
    response = client.get("/v2/policies")
    assert response.status_code == 200
    policies = {item["id"]: item for item in response.json()}
    assert set(policies) == {"default", "provisional-m2", "strict"}
    assert policies["default"]["hash"] == load_builtin("default").hash
    assert policies["default"]["rules"][4]["id"] == "grounding.qualifier_mismatch"
