from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .claims import evaluate_claims


GroundingLabel = Literal[
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "UNSUPPORTED",
]


@dataclass(frozen=True)
class GroundingResult:
    score: float
    grounded: bool
    evidence: list[str] = field(default_factory=list)
    label: GroundingLabel = "UNSUPPORTED"


NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
}


def normalize(text: str) -> str:
    text = text.lower()

    for word, number in NUMBER_WORDS.items():
        text = re.sub(
            rf"\b{word}\b",
            number,
            text,
        )

    text = re.sub(r"[^\w\s]", " ", text)

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def token_set(text: str) -> set[str]:
    return set(
        normalize(text).split()
    )


def similarity(
    answer: str,
    context: str,
) -> float:

    answer_tokens = token_set(answer)
    context_tokens = token_set(context)

    if not answer_tokens:
        return 0.0

    return len(
        answer_tokens & context_tokens
    ) / len(answer_tokens)


def factual_values(text: str) -> set[str]:
    normalized = normalize(text)

    return set(
        re.findall(
            r"\b\d+(?:\.\d+)?\b",
            normalized,
        )
    )


def has_conflicting_factual_value(
    answer: str,
    context: str,
) -> bool:

    answer_values = factual_values(answer)
    context_values = factual_values(context)

    if answer_values and context_values:
        return answer_values.isdisjoint(
            context_values
        )

    return False


def question_type(question: str) -> str:

    normalized = normalize(question)

    if normalized.startswith("when "):
        return "temporal"

    if (
        normalized.startswith("how many ")
        or normalized.startswith("how much ")
    ):
        return "numeric"

    if normalized.startswith("where "):
        return "location"

    if normalized.startswith("who "):
        return "person"

    if normalized.startswith("which "):
        return "specific"

    if normalized.startswith("what "):
        return "general"

    return "general"


def question_keywords(
    question: str,
) -> set[str]:

    stop_words = {
        "what",
        "when",
        "where",
        "who",
        "which",
        "how",
        "many",
        "much",
        "does",
        "do",
        "did",
        "is",
        "are",
        "was",
        "were",
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "for",
        "to",
        "and",
        "company",
    }

    return {
        token
        for token in token_set(question)
        if token not in stop_words
    }


def question_answer_alignment(
    question: str,
    answer: str,
) -> float:

    keywords = question_keywords(
        question
    )

    if not keywords:
        return 1.0

    answer_tokens = token_set(answer)

    return len(
        keywords & answer_tokens
    ) / len(keywords)


def answer_matches_question_type(
    question: str,
    answer: str,
) -> bool:

    q_type = question_type(question)

    answer_normalized = normalize(answer)

    if q_type == "temporal":
        return bool(
            re.search(
                r"\b(?:19|20)\d{2}\b",
                answer_normalized,
            )
        )

    if q_type == "numeric":
        return bool(
            re.search(
                r"\b\d+(?:\.\d+)?\b",
                answer_normalized,
            )
        )

    if q_type == "location":

        location_words = {
            "in",
            "at",
            "from",
            "based",
            "headquartered",
            "located",
        }

        return bool(
            token_set(answer)
            & location_words
        )

    return True


def evaluate_grounding(
    context: str,
    answer: str,
    *,
    question: str | None = None,
    supported_threshold: float = 0.80,
    partial_threshold: float = 0.40,
) -> GroundingResult:

    if not context.strip() or not answer.strip():
        return GroundingResult(
            score=0.0,
            grounded=False,
            evidence=[],
            label="UNSUPPORTED",
        )

    # Question-aware validation
    if question:

        alignment = question_answer_alignment(
            question,
            answer,
        )

        if alignment == 0.0:
            return GroundingResult(
                score=0.0,
                grounded=False,
                evidence=[],
                label="UNSUPPORTED",
            )

        if not answer_matches_question_type(
            question,
            answer,
        ):
            return GroundingResult(
                score=0.0,
                grounded=False,
                evidence=[],
                label="UNSUPPORTED",
            )

    # Claim-level evaluation
    claim_results = evaluate_claims(
        context,
        answer,
        supported_threshold=supported_threshold,
    )

    if not claim_results:
        return GroundingResult(
            score=0.0,
            grounded=False,
            evidence=[],
            label="UNSUPPORTED",
        )

    scores = [
        claim.score
        for claim in claim_results
    ]

    evidence = [
        item
        for claim in claim_results
        for item in claim.evidence
    ]

    supported_count = sum(
        claim.score >= supported_threshold
        for claim in claim_results
    )

    partial_count = sum(
        partial_threshold <= claim.score < supported_threshold
        for claim in claim_results
    )

    unsupported_count = sum(
        claim.score < partial_threshold
        for claim in claim_results
    )

    total_claims = len(claim_results)

    overall_score = (
        sum(scores) / total_claims
    )

    if unsupported_count == total_claims:
        label: GroundingLabel = "UNSUPPORTED"

    elif supported_count == total_claims:
        label = "SUPPORTED"

    elif supported_count > 0 or partial_count > 0:
        label = "PARTIALLY_SUPPORTED"

    else:
        label = "UNSUPPORTED"

    return GroundingResult(
        score=round(
            overall_score,
            4,
        ),
        grounded=label != "UNSUPPORTED",
        evidence=evidence,
        label=label,
    )