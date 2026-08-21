from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from groundguard.domain.proposition_comparison import (
    compare_propositions,
)
from groundguard.domain.propositions import (
    Proposition,
    extract_propositions,
)


ContradictionLabel = Literal[
    "CONTRADICTORY",
    "NOT_CONTRADICTORY",
]


@dataclass(frozen=True)
class ContradictionResult:
    score: float
    contradictory: bool
    label: ContradictionLabel
    evidence: list[str]


def _propositions_conflict(
    answer_propositions: list[Proposition],
    evidence_propositions: list[Proposition],
) -> bool:
    """
    Determine whether any answer proposition directly conflicts
    with an evidence proposition.

    We intentionally require the proposition comparison layer to
    establish the conflict. Mere lexical overlap is not enough.
    """

    for answer_proposition in answer_propositions:
        for evidence_proposition in evidence_propositions:
            comparison = compare_propositions(
                answer_proposition,
                evidence_proposition,
            )

            if comparison == "CONFLICTING":
                return True

    return False


def _propositions_are_supported(
    answer_propositions: list[Proposition],
    evidence_propositions: list[Proposition],
) -> bool:
    """
    Determine whether at least one answer proposition has a
    corresponding proposition in the evidence.

    This is useful for avoiding accidental contradiction decisions
    when the answer and evidence discuss completely different facts.
    """

    for answer_proposition in answer_propositions:
        for evidence_proposition in evidence_propositions:
            comparison = compare_propositions(
                answer_proposition,
                evidence_proposition,
            )

            if comparison == "SAME":
                return True

    return False


def evaluate_contradiction(
    answer: str,
    evidence: str,
) -> ContradictionResult:
    """
    Evaluate whether an answer contradicts supplied evidence.

    The contradiction engine follows a structured pipeline:

        text
          ↓
        proposition extraction
          ↓
        proposition comparison
          ↓
        contradiction decision

    A contradiction requires two propositions that refer to the
    same factual dimension but assert incompatible values.

    Unrelated facts are NOT contradictions.
    """

    if not answer.strip() or not evidence.strip():
        return ContradictionResult(
            score=0.0,
            contradictory=False,
            label="NOT_CONTRADICTORY",
            evidence=[],
        )

    answer_propositions = extract_propositions(
        answer
    )

    evidence_propositions = extract_propositions(
        evidence
    )

    # If we cannot confidently structure either side, fall back to
    # the conservative result: do not claim contradiction.
    #
    # This is preferable to false-positive contradiction detection.
    if not answer_propositions or not evidence_propositions:
        return ContradictionResult(
            score=0.0,
            contradictory=False,
            label="NOT_CONTRADICTORY",
            evidence=[],
        )

    if _propositions_conflict(
        answer_propositions,
        evidence_propositions,
    ):
        return ContradictionResult(
            score=1.0,
            contradictory=True,
            label="CONTRADICTORY",
            evidence=[evidence],
        )

    return ContradictionResult(
        score=0.0,
        contradictory=False,
        label="NOT_CONTRADICTORY",
        evidence=[],
    )