import importlib.util

import pytest

from groundguard.core.errors import InvalidInput
from groundguard.core.text import is_negated, overlap
from groundguard.core.types import Claim, EvidenceSpan, Span
from groundguard.pipeline import PipelineConfig, evaluate_v2
from groundguard.verifiers.nli import (
    NLIScores,
    NLIVerifier,
    TransformersNLIModel,
    VerifierUnavailable,
    get_nli_model,
    register_nli_model,
)


class FakeNLI:
    """Deterministic stand-in: entailment = lexical coverage, contradiction on polarity flips."""

    def __init__(self, revision):
        self._revision = revision
        self.calls = 0

    @property
    def name(self):
        return "fake/overlap-nli"

    @property
    def revision(self):
        return self._revision

    def predict(self, pairs):
        self.calls += 1
        results = []
        for premise, hypothesis in pairs:
            coverage = overlap(hypothesis, premise)
            flipped = is_negated(premise) != is_negated(hypothesis)
            if flipped and coverage > 0.8:
                results.append(NLIScores(0.02, 0.08, 0.9))
            else:
                results.append(NLIScores(coverage, 1 - coverage, 0.0))
        return results


register_nli_model("fake/", FakeNLI)


def claim(text):
    return Claim("c1", text, Span(0, len(text)), "sentence")


def evidence(*texts):
    return tuple(EvidenceSpan("ctx", Span(0, len(t)), t, 1.0) for t in texts)


VERIFIER = NLIVerifier(FakeNLI("abc123"))


def test_supported_picks_highest_entailment_candidate():
    verdict = VERIFIER.verify(claim("Acme sells routers"), evidence("Kenya is large", "Acme sells routers"))
    assert verdict.label == "SUPPORTED"
    assert verdict.evidence[0].text == "Acme sells routers"
    assert verdict.verifier == "nli@1-fake/overlap-nli@abc123-e0.5-c0.5"


def test_contradiction_and_not_enough_info():
    contradicted = VERIFIER.verify(claim("Acme sells routers"), evidence("Acme does not sell routers"))
    assert contradicted.label == "CONTRADICTED"
    assert contradicted.signals["contradiction"] == 0.9
    nei = VERIFIER.verify(claim("Acme sells routers"), evidence("Kenya is large"))
    assert nei.label == "NOT_ENOUGH_INFO"
    assert VERIFIER.verify(claim("Acme sells routers"), ()).label == "NOT_ENOUGH_INFO"


def test_thresholds_are_validated():
    with pytest.raises(ValueError):
        NLIVerifier(FakeNLI("r"), entail_threshold=1.0)


def test_pipeline_uses_nli_backend_after_guards():
    config = PipelineConfig(backend="nli", nli_model="fake/overlap-nli", nli_revision="abc123")
    assert config.chain().ids == (
        "guards@2",
        "structured_facts@1",
        "nli@1-fake/overlap-nli@abc123-e0.5-c0.5",
    )
    report = evaluate_v2(question="When was Acme founded?", context="Acme was founded in 2010.",
                         answer="Acme was founded in 2010.", config=config)
    assert report.verdicts[0].verifier.startswith("nli@")
    assert report.decision.decision == "ACCEPT"


def test_nli_config_requires_model_and_pinned_revision():
    with pytest.raises(InvalidInput, match="pinned nli_revision"):
        PipelineConfig(backend="nli", nli_model="fake/overlap-nli")
    with pytest.raises(InvalidInput):
        PipelineConfig(backend="neural")


def test_models_are_cached_per_id_and_revision():
    assert get_nli_model("fake/overlap-nli", "r1") is get_nli_model("fake/overlap-nli", "r1")
    assert get_nli_model("fake/overlap-nli", "r1") is not get_nli_model("fake/overlap-nli", "r2")


def test_label_index_reads_model_label_names():
    assert TransformersNLIModel._label_index({0: "CONTRADICTION", 1: "ENTAILMENT", 2: "NEUTRAL"}) == {
        "contradict": 0, "entail": 1, "neutral": 2,
    }
    with pytest.raises(VerifierUnavailable):
        TransformersNLIModel._label_index({0: "LABEL_0", 1: "LABEL_1"})


@pytest.mark.skipif(importlib.util.find_spec("transformers") is not None, reason="extra installed")
def test_missing_extra_gives_a_clear_error():
    with pytest.raises(VerifierUnavailable, match=r"groundguard\[nli\]"):
        TransformersNLIModel("cross-encoder/nli-deberta-v3-small", "0" * 40)
