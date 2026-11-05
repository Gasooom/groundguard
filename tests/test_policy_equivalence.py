"""Builtin policies must reproduce the decisions they replace.

- provisional-m2 vs the frozen M2 rule code (tests/reference/m2_provisional.py):
  identical decision, rule id and reason on all legacy records and probes.
- v1-compat vs the v0.1.0 decision engine: identical system_decision on all
  legacy records (reason texts are intentionally not reproduced).
"""

import json
from pathlib import Path

import pytest

from groundguard.application.evaluator import evaluate
from groundguard.bench.datasets import load_legacy_v1
from groundguard.claims.segmenter import segment
from groundguard.core.types import SourceDocument
from groundguard.domain.pii import detect_pii
from groundguard.domain.prompt_injection import detect_prompt_injection
from groundguard.domain.relevance import evaluate_relevance
from groundguard.evidence.bm25 import select_evidence
from groundguard.evidence.chunking import chunk_sources
from groundguard.pipeline import PipelineConfig
from groundguard.policy import decide, facts_from_v1, facts_from_v2, load_builtin
from tests.reference.m2_provisional import provisional_decision


PROBES = json.loads(
    (Path(__file__).resolve().parent / "probes" / "probes.json").read_text(encoding="utf-8")
)["probes"]

CASES = [(r.id, r.question, r.context, r.answer) for r in load_legacy_v1().records] + [
    (p["id"], p["question"], p["context"], p["answer"]) for p in PROBES
]


def _verdicts(question, context, answer):
    config = PipelineConfig()
    chain = config.chain()
    chunks = chunk_sources([SourceDocument("context", context)])
    return [
        chain.verify(claim, select_evidence(claim.text, chunks, top_k=config.top_k))
        for claim in segment(answer, config.granularity)
        if claim.assertive
    ]


@pytest.mark.parametrize("case", CASES, ids=[case[0] for case in CASES])
def test_provisional_m2_policy_matches_frozen_m2_rules(case):
    _, question, context, answer = case
    verdicts = _verdicts(question, context, answer)
    relevant = evaluate_relevance(question, answer).relevant
    pii = detect_pii(answer).detected
    injection = detect_prompt_injection(answer).detected

    expected = provisional_decision(
        [verdict.label for verdict in verdicts],
        relevant=relevant,
        pii_detected=pii,
        injection_detected=injection,
    )
    actual = decide(
        load_builtin("provisional-m2"),
        facts_from_v2(verdicts, relevant=relevant, pii_detected=pii, injection_detected=injection),
    )
    assert (actual.decision, actual.rule, actual.reason) == expected


@pytest.mark.parametrize("case", CASES, ids=[case[0] for case in CASES])
def test_v1_compat_policy_matches_v1_decision_engine(case):
    _, question, context, answer = case
    result = evaluate(question=question, context=context, answer=answer)
    assert decide(load_builtin("v1-compat"), facts_from_v1(result)).decision == result.decision.system_decision
