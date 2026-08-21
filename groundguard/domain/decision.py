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


@dataclass(frozen=True)
class DecisionResult:
    """
    Final deterministic reliability decision.

    The decision layer consumes the already-evaluated
    Grounding, Relevance, and Contradiction results and
    produces one system-level reliability decision.
    """

    label: DecisionLabel
    reliable: bool

    grounding_score: float
    relevance_score: float
    contradiction_score: float

    reason: str


def _build_reason(
    grounding: GroundingResult,
    relevance: RelevanceResult,
    contradiction: ContradictionResult,
) -> str:
    """
    Produce a deterministic human-readable explanation.

    Priority:

        1. contradiction
        2. grounding
        3. relevance
        4. reliable
    """

    if contradiction.label == "CONTRADICTORY":
        return (
            "Unreliable because the contradiction component "
            "detected a contradiction with the supplied evidence."
        )

    if grounding.label == "UNSUPPORTED":
        return (
            "Unreliable because the grounding component "
            "determined that the answer is not supported "
            "by the supplied evidence."
        )

    if grounding.label == "PARTIALLY_SUPPORTED":
        return (
            "Unreliable because the grounding component "
            "determined that the answer is only partially "
            "supported by the supplied evidence."
        )

    if relevance.label == "IRRELEVANT":
        return (
            "Unreliable because the relevance component "
            "determined that the answer is not relevant "
            "to the question."
        )

    return (
        "Reliable because the grounding, relevance, and "
        "contradiction components indicate that the answer "
        "is sufficiently grounded, relevant, and non-contradictory."
    )


def evaluate_decision(
    *,
    grounding: GroundingResult,
    relevance: RelevanceResult,
    contradiction: ContradictionResult,
) -> DecisionResult:
    """
    Combine GroundGuard's three evaluation signals into a
    final deterministic reliability decision.

    Decision policy:

        CONTRADICTORY
            -> UNRELIABLE

        UNSUPPORTED grounding
            -> UNRELIABLE

        PARTIALLY_SUPPORTED grounding
            -> UNRELIABLE

        IRRELEVANT
            -> UNRELIABLE

        otherwise
            -> RELIABLE

    No weighted scoring or threshold tuning is performed here.
    Those concerns belong to later Sprint 6 stages.
    """

    if contradiction.label == "CONTRADICTORY":
        label: DecisionLabel = "UNRELIABLE"
        reliable = False

    elif grounding.label in {
        "UNSUPPORTED",
        "PARTIALLY_SUPPORTED",
    }:
        label = "UNRELIABLE"
        reliable = False

    elif relevance.label == "IRRELEVANT":
        label = "UNRELIABLE"
        reliable = False

    else:
        label = "RELIABLE"
        reliable = True

    return DecisionResult(
        label=label,
        reliable=reliable,
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