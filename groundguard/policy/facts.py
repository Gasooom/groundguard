"""Facts a policy decides on, built from v2 verdicts or from a v1 result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Sequence

from groundguard.core.types import ClaimVerdict, VerdictLabel

if TYPE_CHECKING:
    from groundguard.application.evaluator import EvaluationResult


CheckName = Literal["pii", "prompt_injection", "relevance", "source_injection", "citation"]
CHECK_NAMES: tuple[CheckName, ...] = ("pii", "prompt_injection", "relevance", "source_injection", "citation")


@dataclass(frozen=True)
class ClaimFact:
    label: VerdictLabel
    confidence: float | None
    signals: frozenset[str]


@dataclass(frozen=True)
class V1Facts:
    """Outputs of the v0.1.0 evaluator, used only by v1-compatible policies."""

    unsafe: bool
    grounding: str
    relevance: str
    contradiction: str
    reliability_below_threshold: bool


@dataclass(frozen=True)
class EvaluationFacts:
    claims: tuple[ClaimFact, ...]
    failed_checks: frozenset[CheckName]
    v1: V1Facts | None = None


def facts_from_v2(
    verdicts: Sequence[ClaimVerdict],
    *,
    relevant: bool,
    pii_detected: bool,
    injection_detected: bool,
    source_injection_detected: bool = False,
    citation_failed: bool = False,
) -> EvaluationFacts:
    failed: set[CheckName] = set()
    if pii_detected:
        failed.add("pii")
    if injection_detected:
        failed.add("prompt_injection")
    if not relevant:
        failed.add("relevance")
    if source_injection_detected:
        failed.add("source_injection")
    if citation_failed:
        failed.add("citation")
    claims = tuple(
        ClaimFact(
            label=verdict.label,
            confidence=verdict.confidence,
            signals=frozenset(str(name) for name in verdict.signals.get("fired", ())),
        )
        for verdict in verdicts
    )
    return EvaluationFacts(claims=claims, failed_checks=frozenset(failed))


def facts_from_v1(result: "EvaluationResult") -> EvaluationFacts:
    """Facts for v1-compatible policies. Claim-level facts are empty: v1 has none."""

    failed: set[CheckName] = set()
    if result.pii.detected:
        failed.add("pii")
    if result.prompt_injection.detected:
        failed.add("prompt_injection")
    if result.relevance.label == "IRRELEVANT":
        failed.add("relevance")
    decision = result.decision
    return EvaluationFacts(
        claims=(),
        failed_checks=frozenset(failed),
        v1=V1Facts(
            unsafe=not result.safety.safe,
            grounding=result.grounding.label,
            relevance=result.relevance.label,
            contradiction=result.contradiction.label,
            reliability_below_threshold=decision.reliability_score < decision.threshold,
        ),
    )
