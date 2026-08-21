from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClaimResult:
    claim: str
    evidence: list[str]
    score: float
    supported: bool


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

    text = re.sub(
        r"[^\w\s]",
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def sentence_split(text: str) -> list[str]:
    sentences = re.split(
        r"(?<=[.!?])\s+",
        text.strip(),
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


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
    return set(
        re.findall(
            r"\b\d+(?:\.\d+)?\b",
            normalize(text),
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


def best_context_match(
    answer_sentence: str,
    context_sentences: list[str],
) -> tuple[str, float]:

    best_context = ""
    best_score = 0.0

    answer_values = factual_values(
        answer_sentence
    )

    for context_sentence in context_sentences:

        score = similarity(
            answer_sentence,
            context_sentence,
        )

        if score <= 0:
            continue

        context_values = factual_values(
            context_sentence
        )

        # If both sentences contain factual values,
        # their values must agree.
        if answer_values and context_values:
            if answer_values.isdisjoint(
                context_values
            ):
                continue

        if score > best_score:
            best_score = score
            best_context = context_sentence

    return best_context, best_score


def evaluate_claims(
    context: str,
    answer: str,
    supported_threshold: float = 0.80,
) -> list[ClaimResult]:

    context_sentences = sentence_split(
        context
    )

    answer_sentences = sentence_split(
        answer
    )

    results: list[ClaimResult] = []

    for claim in answer_sentences:

        evidence, score = best_context_match(
            claim,
            context_sentences,
        )

        results.append(
            ClaimResult(
                claim=claim,
                evidence=(
                    [evidence]
                    if evidence
                    else []
                ),
                score=round(
                    score,
                    4,
                ),
                supported=(
                    score
                    >= supported_threshold
                ),
            )
        )

    return results