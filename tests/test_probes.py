"""Behavioral probe suite for the v2 pipeline (tests/probes/probes.json).

Two kinds of assertion:

1. Hard rule: no probe marked ``must_not_accept`` may be accepted. There is
   no exception list for false accepts.
2. Every other expectation (must_accept, expected_contradicted) must hold
   except for the probes listed in KNOWN_LIMITATIONS, and the set of
   failing probes must equal that list exactly. An improvement or a
   regression therefore fails this test until the list is updated on
   purpose, with a reason.
"""

import json
from pathlib import Path

import pytest

from groundguard.pipeline import evaluate_v2


PROBES = json.loads(
    (Path(__file__).resolve().parent / "probes" / "probes.json").read_text(encoding="utf-8")
)["probes"]

# probe id -> why the default v2 engine fails it
KNOWN_LIMITATIONS = {
    "para_01_audit": "paraphrase without lexical overlap; needs an NLI backend (M4)",
    "para_02": "synonym (established/founded); deterministic coverage has no synonyms",
    "para_03": "nominalization and unit abbreviation (weighs/weight, kilograms/kg)",
    "num_04_control": "v1 relevance (reused unchanged) rejects 'how long' answers without a matched keyword",
    "list_04_control": "v1 relevance treats every 'when' question as requiring a year",
    "ctrl_02": "v1 relevance treats every 'when' question as requiring a year",
}


def _evaluate(probe):
    return evaluate_v2(question=probe["question"], context=probe["context"], answer=probe["answer"])


def _failures(probe, report):
    failures = []
    decision = report.decision.decision
    contradicted = report.labels["contradiction_label"] == "CONTRADICTORY"
    if probe["must_accept"] and decision != "ACCEPT":
        failures.append(f"expected ACCEPT, got {decision} ({report.decision.rule})")
    if probe["expected_contradicted"] is not None and contradicted != probe["expected_contradicted"]:
        failures.append(f"expected contradicted={probe['expected_contradicted']}, got {contradicted}")
    return failures


MUST_NOT_ACCEPT = [probe for probe in PROBES if probe["must_not_accept"]]


@pytest.mark.parametrize("probe", MUST_NOT_ACCEPT, ids=[probe["id"] for probe in MUST_NOT_ACCEPT])
def test_no_false_accepts(probe):
    report = _evaluate(probe)
    assert report.decision.decision != "ACCEPT", (probe["id"], probe["rationale"])


def test_failing_probes_are_exactly_the_known_limitations():
    failing = {}
    for probe in PROBES:
        failures = _failures(probe, _evaluate(probe))
        if failures:
            failing[probe["id"]] = failures

    unexpected = {key: value for key, value in failing.items() if key not in KNOWN_LIMITATIONS}
    fixed = sorted(set(KNOWN_LIMITATIONS) - set(failing))
    assert not unexpected, f"new probe failures: {unexpected}"
    assert not fixed, f"probes now pass; remove them from KNOWN_LIMITATIONS: {fixed}"


def test_known_limitations_reference_real_probes():
    ids = {probe["id"] for probe in PROBES}
    assert set(KNOWN_LIMITATIONS) <= ids


def test_audit_probes_have_evidence_spans():
    probe = next(p for p in PROBES if p["id"] == "neg_01_audit")
    report = _evaluate(probe)
    (verdict,) = report.verdicts
    assert verdict.label == "CONTRADICTED"
    (span,) = verdict.evidence
    assert probe["context"][span.span.start : span.span.end] == span.text
    assert "Berlin" in span.text
