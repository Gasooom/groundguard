from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


RelevanceLabel = Literal[
    "RELEVANT",
    "IRRELEVANT",
]


@dataclass(frozen=True)
class RelevanceResult:
    score: float
    relevant: bool
    label: RelevanceLabel


STOP_WORDS = {
    "what",
    "when",
    "where",
    "who",
    "which",
    "why",
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
}


NUMBER_WORDS = {
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
}


SEMANTIC_ALIASES = {
    "manufacture": {
        "manufacture",
        "manufactures",
        "manufactured",
        "make",
        "makes",
        "made",
        "produce",
        "produces",
        "produced",
    },
    "employee": {
        "employee",
        "employees",
        "employ",
        "employs",
        "employed",
        "people",
        "staff",
        "workers",
    },
    "headquarter": {
        "headquarter",
        "headquartered",
        "headquarters",
        "based",
        "located",
    },
    "industry": {
        "industry",
        "industries",
        "operate",
        "operates",
        "operated",
        "develop",
        "develops",
        "developed",
        "sector",
    },
    "launch": {
        "launch",
        "launched",
        "launches",
        "release",
        "released",
        "releases",
        "introduce",
        "introduced",
        "introduces",
        "found",
        "founded",
    },
}


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def stem_token(token: str) -> str:
    """
    Apply lightweight word-form normalization.

    Examples:
        sells -> sell
        offers -> offer
        products -> product
    """

    if len(token) <= 4:
        return token

    if token.endswith("ies"):
        return token[:-3] + "y"

    if token.endswith("ing"):
        return token[:-3]

    if token.endswith("ed"):
        return token[:-2]

    if token.endswith("es"):
        return token[:-2]

    if token.endswith("s"):
        return token[:-1]

    return token


def tokens(text: str) -> set[str]:
    raw_tokens = normalize(text).split()

    return {
        stem_token(token)
        for token in raw_tokens
    }


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

    if normalized.startswith("why "):
        return "reason"

    if normalized.startswith("what "):
        return "general"

    return "general"


def question_keywords(question: str) -> set[str]:
    return {
        token
        for token in tokens(question)
        if token not in STOP_WORDS
    }


def semantic_token_match(
    question_token: str,
    answer_tokens: set[str],
) -> bool:
    """
    Match a question token against lightweight
    semantic alias groups.
    """

    if question_token in answer_tokens:
        return True

    for aliases in SEMANTIC_ALIASES.values():
        normalized_aliases = {
            stem_token(alias)
            for alias in aliases
        }

        if question_token in normalized_aliases:
            if normalized_aliases & answer_tokens:
                return True

    return False


def calculate_relevance_score(
    question: str,
    answer: str,
) -> float:
    keywords = question_keywords(question)

    if not keywords:
        return 0.0

    answer_tokens = tokens(answer)

    matched = sum(
        semantic_token_match(
            keyword,
            answer_tokens,
        )
        for keyword in keywords
    )

    return matched / len(keywords)


def contains_number(text: str) -> bool:
    normalized = normalize(text)

    if re.search(
        r"\b\d+(?:\.\d+)?\b",
        normalized,
    ):
        return True

    return bool(
        tokens(normalized)
        & {
            stem_token(word)
            for word in NUMBER_WORDS
        }
    )


def answer_matches_question_type(
    question: str,
    answer: str,
) -> bool:
    q_type = question_type(question)
    normalized = normalize(answer)

    if q_type == "temporal":
        temporal_patterns = [
            r"\b(?:19|20)\d{2}\b",
            r"\bnext year\b",
            r"\blast year\b",
            r"\bthis year\b",
            r"\btoday\b",
            r"\btomorrow\b",
            r"\byesterday\b",
            r"\bnext month\b",
            r"\blast month\b",
            r"\bthis month\b",
            r"\bnext week\b",
            r"\blast week\b",
            r"\bthis week\b",
            r"\bduring\b",
            r"\bin \d{4}\b",
        ]

        return any(
            re.search(pattern, normalized)
            for pattern in temporal_patterns
        )

    if q_type == "numeric":
        return contains_number(answer)

    if q_type == "location":
        location_terms = {
            "in",
            "at",
            "from",
            "based",
            "located",
            "headquartered",
        }

        normalized_location_terms = {
            stem_token(term)
            for term in location_terms
        }

        return bool(
            tokens(answer)
            & normalized_location_terms
        )

    if q_type == "person":
        return len(tokens(answer)) >= 2

    if q_type == "specific":
        question_tokens = tokens(question)
        answer_tokens = tokens(answer)

        location_question_terms = {
            stem_token("city"),
            stem_token("country"),
            stem_token("location"),
        }

        if question_tokens & location_question_terms:
            location_answer_terms = {
                stem_token("in"),
                stem_token("at"),
                stem_token("from"),
                stem_token("based"),
                stem_token("located"),
                stem_token("headquartered"),
            }

            return bool(
                answer_tokens & location_answer_terms
            )

        return True

    return True


def evaluate_relevance(
    question: str,
    answer: str,
    relevant_threshold: float = 0.5,
) -> RelevanceResult:

    if not question.strip() or not answer.strip():
        return RelevanceResult(
            score=0.0,
            relevant=False,
            label="IRRELEVANT",
        )

    score = calculate_relevance_score(
        question,
        answer,
    )

    if not answer_matches_question_type(
        question,
        answer,
    ):
        return RelevanceResult(
            score=round(score, 4),
            relevant=False,
            label="IRRELEVANT",
        )

    relevant = score >= relevant_threshold

    return RelevanceResult(
        score=round(score, 4),
        relevant=relevant,
        label=(
            "RELEVANT"
            if relevant
            else "IRRELEVANT"
        ),
    )