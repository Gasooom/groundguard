from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from groundguard.domain.contradiction import ContradictionResult
from groundguard.domain.grounding import GroundingResult
from groundguard.domain.relevance import RelevanceResult


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
    Final deterministic reliability decision.

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

    reason: str


def _build_system_decision(
    grounding: GroundingResult,
    relevance: RelevanceResult,
    contradiction: ContradictionResult,
) -> SystemDecisionLabel:
    """
    Map component results to GroundGuard's public decision.

    Priority:

        contradiction      -> REJECT
        unsupported        -> REJECT
        irrelevant         -> REJECT
        partially supported -> FLAG
        otherwise          -> ACCEPT
    """

    if contradiction.label == "CONTRADICTORY":
        return "REJECT"

    if grounding.label == "UNSUPPORTED":
        return "REJECT"

    if relevance.label == "IRRELEVANT":
        return "REJECT"

    if grounding.label == "PARTIALLY_SUPPORTED":
        return "FLAG"

    return "ACCEPT"


def _build_reason(
    grounding: GroundingResult,
    relevance: RelevanceResult,
    contradiction: ContradictionResult,
) -> str:
    """
    Produce a deterministic human-readable explanation.
    """

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

    return (
        "ACCEPT because the grounding, relevance, and "
        "contradiction components indicate that the answer "
        "is sufficiently grounded, relevant, and "
        "non-contradictory."
    )


def evaluate_decision(
    *,
    grounding: GroundingResult,
    relevance: RelevanceResult,
    contradiction: ContradictionResult,
) -> DecisionResult:
    """
    Combine GroundGuard's evaluation signals into the final
    deterministic system decision.

    Policy:

        CONTRADICTORY
            -> REJECT

        UNSUPPORTED
            -> REJECT

        IRRELEVANT
            -> REJECT

        PARTIALLY_SUPPORTED
            -> FLAG

        SUPPORTED + RELEVANT + NOT_CONTRADICTORY
            -> ACCEPT
    """

    system_decision = _build_system_decision(
        grounding,
        relevance,
        contradiction,
    )

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
        grounding_score=round(
            grounding.score,
            4,
        ),
        relevance_score=round(
            relevance.score,
            4,
        ),
        contradiction_score=round(
            contradiction.score,
            4,
        ),
        reason=_build_reason(
            grounding,
            relevance,
            contradiction,
        ),
    )