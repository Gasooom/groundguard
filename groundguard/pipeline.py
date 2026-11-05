"""Engine v2: claim-level evaluation pipeline.

    answer ─► segment ─► claims ─┐
    context ─► chunk ────────────┼─► per claim: BM25 candidates ─► verifier chain ─► verdict
    question ─► relevance (v1)   │
    answer ─► PII + injection (v1)
                                  └─► derived labels ─► provisional decision ─► report

The provisional decision rules below are replaced by the declarative policy
engine in M3, which must reproduce them exactly. The v1 engine
(``groundguard.application.evaluator``) is untouched and still serves
``POST /evaluate``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Sequence

from groundguard.claims.segmenter import segment
from groundguard.core.errors import InvalidInput
from groundguard.core.serialization import sha256_json
from groundguard.core.types import (
    GRANULARITIES,
    Claim,
    ClaimVerdict,
    DecisionLabel,
    Granularity,
    SourceDocument,
)
from groundguard.domain.pii import detect_pii
from groundguard.domain.prompt_injection import detect_prompt_injection
from groundguard.domain.relevance import evaluate_relevance
from groundguard.evidence.bm25 import select_evidence
from groundguard.evidence.chunking import chunk_sources
from groundguard.verifiers.base import Verifier, VerifierChain
from groundguard.verifiers.guards import GuardVerifier
from groundguard.verifiers.lexical import LexicalMode, LexicalVerifier
from groundguard.verifiers.structured_facts import StructuredFactsVerifier


ENGINE_VERSION = "2.0.0-m2"


@dataclass(frozen=True)
class PipelineConfig:
    granularity: Granularity = "conjunct"
    top_k: int = 5
    guards: bool = True
    structured_facts: bool = True
    min_topic_dice: float = 0.5
    lexical_mode: LexicalMode = "content"
    lexical_threshold: float = 1.0

    def __post_init__(self) -> None:
        if self.granularity not in GRANULARITIES:
            raise InvalidInput(f"granularity must be one of {GRANULARITIES}")
        if self.top_k < 1:
            raise InvalidInput("top_k must be positive")

    def chain(self) -> VerifierChain:
        verifiers: list[Verifier] = []
        if self.guards:
            verifiers.append(GuardVerifier(min_topic_dice=self.min_topic_dice))
        if self.structured_facts:
            verifiers.append(StructuredFactsVerifier())
        verifiers.append(LexicalVerifier(threshold=self.lexical_threshold, mode=self.lexical_mode))
        return VerifierChain(tuple(verifiers))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ------------------------------------------------------------ decision (M2)

RuleId = Literal[
    "safety.pii",
    "safety.prompt_injection",
    "grounding.contradicted",
    "relevance.irrelevant",
    "grounding.none_supported",
    "grounding.not_enough_info",
    "default.accept",
]

PROVISIONAL_RULES: tuple[tuple[RuleId, DecisionLabel, str], ...] = (
    ("safety.pii", "REJECT", "PII was detected in the answer."),
    ("safety.prompt_injection", "REJECT", "Prompt-injection patterns were detected in the answer."),
    ("grounding.contradicted", "REJECT", "At least one claim is contradicted by the evidence."),
    ("relevance.irrelevant", "REJECT", "The answer does not address the question."),
    ("grounding.none_supported", "REJECT", "No claim in the answer is supported by the evidence."),
    ("grounding.not_enough_info", "FLAG", "Some claims cannot be verified from the evidence."),
    ("default.accept", "ACCEPT", "Every claim is supported and no check failed."),
)


@dataclass(frozen=True)
class Decision:
    decision: DecisionLabel
    rule: RuleId
    reason: str
    policy: str = "provisional-m2"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def provisional_decision(
    verdicts: Sequence[ClaimVerdict],
    *,
    relevant: bool,
    pii_detected: bool,
    injection_detected: bool,
) -> Decision:
    labels = [verdict.label for verdict in verdicts]
    fired: dict[RuleId, bool] = {
        "safety.pii": pii_detected,
        "safety.prompt_injection": injection_detected,
        "grounding.contradicted": "CONTRADICTED" in labels,
        "relevance.irrelevant": not relevant,
        "grounding.none_supported": "SUPPORTED" not in labels,
        "grounding.not_enough_info": "NOT_ENOUGH_INFO" in labels,
        "default.accept": True,
    }
    for rule, decision, reason in PROVISIONAL_RULES:
        if fired[rule]:
            return Decision(decision, rule, reason)
    raise AssertionError("default rule always fires")  # pragma: no cover


def derive_v1_labels(verdicts: Sequence[ClaimVerdict]) -> dict[str, str]:
    """Answer-level labels in the v1 vocabulary (GROUNDGUARD_V2.md §7)."""

    labels = [verdict.label for verdict in verdicts]
    supported = labels.count("SUPPORTED")
    if labels and supported == len(labels):
        grounding = "SUPPORTED"
    elif supported:
        grounding = "PARTIALLY_SUPPORTED"
    else:
        grounding = "UNSUPPORTED"
    contradiction = "CONTRADICTORY" if "CONTRADICTED" in labels else "NOT_CONTRADICTORY"
    return {"grounding_label": grounding, "contradiction_label": contradiction}


# ------------------------------------------------------------------- report


@dataclass(frozen=True)
class EvaluationReportV2:
    question: str
    answer: str
    sources: tuple[SourceDocument, ...]
    claims: tuple[Claim, ...]
    verdicts: tuple[ClaimVerdict, ...]
    labels: dict[str, str]
    relevance: dict[str, Any]
    safety: dict[str, Any]
    decision: Decision
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "sources": [source.to_dict() for source in self.sources],
            "claims": [claim.to_dict() for claim in self.claims],
            "verdicts": [verdict.to_dict() for verdict in self.verdicts],
            "labels": dict(self.labels),
            "relevance": dict(self.relevance),
            "safety": dict(self.safety),
            "decision": self.decision.to_dict(),
            "manifest": dict(self.manifest),
        }


def _sources(
    context: str | None,
    contexts: Sequence[SourceDocument] | None,
) -> tuple[SourceDocument, ...]:
    if (context is None) == (contexts is None):
        raise InvalidInput("provide exactly one of 'context' or 'contexts'")
    if context is not None:
        if not context.strip():
            raise InvalidInput("context must not be empty")
        return (SourceDocument(id="context", text=context),)
    assert contexts is not None
    if not contexts:
        raise InvalidInput("contexts must not be empty")
    ids = [source.id for source in contexts]
    if len(ids) != len(set(ids)):
        raise InvalidInput("source ids must be unique")
    if any(not source.text.strip() for source in contexts):
        raise InvalidInput("source text must not be empty")
    return tuple(contexts)


def evaluate_v2(
    *,
    question: str,
    answer: str,
    context: str | None = None,
    contexts: Sequence[SourceDocument] | None = None,
    config: PipelineConfig | None = None,
) -> EvaluationReportV2:
    """Evaluate an answer claim by claim against the supplied sources."""

    if not question.strip():
        raise InvalidInput("question must not be empty")
    if not answer.strip():
        raise InvalidInput("answer must not be empty")
    config = config or PipelineConfig()
    sources = _sources(context, contexts)
    chain = config.chain()

    claims = segment(answer, config.granularity)
    chunks = chunk_sources(sources)
    verdicts = tuple(
        chain.verify(claim, select_evidence(claim.text, chunks, top_k=config.top_k))
        for claim in claims
        if claim.assertive
    )

    relevance = evaluate_relevance(question, answer)
    pii = detect_pii(answer)
    injection = detect_prompt_injection(answer)

    decision = provisional_decision(
        verdicts,
        relevant=relevance.relevant,
        pii_detected=pii.detected,
        injection_detected=injection.detected,
    )

    config_dict = config.to_dict()
    manifest = {
        "engine": "v2",
        "engine_version": ENGINE_VERSION,
        "verifier_chain": list(chain.ids),
        "config": config_dict,
        "config_hash": sha256_json({"engine_version": ENGINE_VERSION, **config_dict}),
        "decision_policy": decision.policy,
        "relevance": "v1 domain.relevance (answer level)",
        "safety": "v1 domain.pii + domain.prompt_injection (answer only)",
    }

    return EvaluationReportV2(
        question=question,
        answer=answer,
        sources=sources,
        claims=claims,
        verdicts=verdicts,
        labels=derive_v1_labels(verdicts),
        relevance={"label": relevance.label, "score": relevance.score},
        safety={
            "safe": not (pii.detected or injection.detected),
            "pii_detected": pii.detected,
            "pii_categories": list(pii.categories),
            "prompt_injection_detected": injection.detected,
            "prompt_injection_categories": list(injection.categories),
            "evidence": [*pii.evidence, *injection.evidence],
        },
        decision=decision,
        manifest=manifest,
    )
