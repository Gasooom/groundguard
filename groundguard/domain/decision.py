from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from groundguard.domain.contradiction import ContradictionResult
from groundguard.domain.grounding import GroundingResult
from groundguard.domain.relevance import RelevanceResult
from groundguard.evaluation.decision_metrics import reliability_score
from groundguard.evaluation.thresholds import DEFAULT_THRESHOLD_POLICY


DecisionLabel = Literal[
    "RELIABLE",
    "UNRELIABLE",
]

SystemDecisionLabel = Literal[
    "ACCEPT",
    "FLAG",
    "REJECT",
]


@dataclass(frozen=True)
class DecisionResult:
    """
    Final deterministic GroundGuard decision.

    Internal reliability:
        RELIABLE / UNRELIABLE

    Public system decision:
        ACCEPT / FLAG / REJECT
    """

    label: DecisionLabel
    reliable: bool

    system_decision: SystemDecisionLabel

    grounding_score: float
    relevance_score: float
    contradiction_score: float

    reliability_score: float
    threshold: float

    reason: str


def _build_reason(
    grounding: GroundingResult,
    relevance: RelevanceResult,
    contradiction: ContradictionResult,
    *,
    reliability: float,
    threshold: float,
) -> str:
    if contradiction.label == "CONTRADICTORY":
        return (
            "REJECT because the contradiction component "
            "detected a contradiction with the supplied evidence."
        )

    if grounding.label == "UNSUPPORTED":
        return (
            "REJECT because the grounding component "
            "determined that the answer is not supported "
            "by the supplied evidence."
        )

    if relevance.label == "IRRELEVANT":
        return (
            "REJECT because the relevance component "
            "determined that the answer is not relevant "
            "to the question."
        )

    if grounding.label == "PARTIALLY_SUPPORTED":
        return (
            "FLAG because the grounding component "
            "determined that the answer is only partially "
            "supported by the supplied evidence."
        )

    if reliability < threshold:
        return (
            "FLAG because the computed reliability score "
            f"({reliability:.4f}) is below the configured "
            f"threshold ({threshold:.4f})."
        )

    return (
        "ACCEPT because the grounding, relevance, and "
        "contradiction components are satisfactory and "
        f"the reliability score ({reliability:.4f}) meets "
        f"the configured threshold ({threshold:.4f})."
    )


def evaluate_decision(
    *,
    grounding: GroundingResult,
    relevance: RelevanceResult,
    contradiction: ContradictionResult,
    threshold: float | None = None,
) -> DecisionResult:
    """
    Combine GroundGuard evaluation signals into one decision.

    Hard safety rules have priority:

        CONTRADICTORY
            -> REJECT

        UNSUPPORTED
            -> REJECT

        IRRELEVANT
            -> REJECT

        PARTIALLY_SUPPORTED
            -> FLAG

    For otherwise acceptable component labels, the Sprint 6
    reliability score is evaluated against the configured
    threshold.

        score >= threshold
            -> ACCEPT

        score < threshold
            -> FLAG
    """

    configured_threshold = (
        DEFAULT_THRESHOLD_POLICY.candidate_threshold
        if threshold is None
        else threshold
    )

    if not 0.0 <= configured_threshold <= 1.0:
        raise ValueError(
            "threshold must be between 0.0 and 1.0"
        )

    grounding_score = round(grounding.score, 4)
    relevance_score = round(relevance.score, 4)
    contradiction_score = round(contradiction.score, 4)

    score = reliability_score(
        grounding_score=grounding_score,
        relevance_score=relevance_score,
        contradiction_score=contradiction_score,
    )

    if contradiction.label == "CONTRADICTORY":
        system_decision: SystemDecisionLabel = "REJECT"

    elif grounding.label == "UNSUPPORTED":
        system_decision = "REJECT"

    elif relevance.label == "IRRELEVANT":
        system_decision = "REJECT"

    elif grounding.label == "PARTIALLY_SUPPORTED":
        system_decision = "FLAG"

    elif score >= configured_threshold:
        system_decision = "ACCEPT"

    else:
        system_decision = "FLAG"

    if system_decision == "ACCEPT":
        label: DecisionLabel = "RELIABLE"
        reliable = True
    else:
        label = "UNRELIABLE"
        reliable = False

    return DecisionResult(
        label=label,
        reliable=reliable,
        system_decision=system_decision,
        grounding_score=grounding_score,
        relevance_score=relevance_score,
        contradiction_score=contradiction_score,
        reliability_score=score,
        threshold=round(configured_threshold, 4),
        reason=_build_reason(
            grounding,
            relevance,
            contradiction,
            reliability=score,
            threshold=configured_threshold,
        ),
    )