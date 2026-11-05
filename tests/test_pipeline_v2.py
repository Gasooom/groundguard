import pytest
from fastapi.testclient import TestClient

from groundguard.api.app import app
from groundguard.core.errors import InvalidInput
from groundguard.core.types import ClaimVerdict, SourceDocument
from groundguard.pipeline import (
    PROVISIONAL_RULES,
    PipelineConfig,
    derive_v1_labels,
    evaluate_v2,
    provisional_decision,
)


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
def test_provisional_decision_rules_in_priority_order(labels, relevant, pii, injection, rule, decision):
    result = provisional_decision(
        [_verdict(label) for label in labels],
        relevant=relevant,
        pii_detected=pii,
        injection_detected=injection,
    )
    assert (result.rule, result.decision) == (rule, decision)


def test_rule_table_is_complete_and_ordered():
    assert [rule for rule, _, _ in PROVISIONAL_RULES][-1] == "default.accept"
    assert len({rule for rule, _, _ in PROVISIONAL_RULES}) == len(PROVISIONAL_RULES)


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
    assert report.manifest["verifier_chain"] == ["guards@1", "structured_facts@1", "lexical@1-content-1"]
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
