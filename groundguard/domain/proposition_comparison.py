from __future__ import annotations

import re
from typing import Literal

from groundguard.domain.propositions import Proposition


ComparisonResult = Literal[
    "SAME",
    "CONFLICTING",
    "UNRELATED",
]


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_SYNONYMS = {
    "bicycles": "bikes",
    "bicycle": "bikes",
    "bike": "bikes",
    "people": "employees",
    "employee": "employees",
    "employees": "employees",
    "yrs": "years",
}


def _normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return " ".join(
        _SYNONYMS.get(token, token)
        for token in text.split()
    )


def _normalize_subject(subject: str) -> str:
    return _normalize_text(subject)


def _normalize_predicate(predicate: str) -> str:
    return _normalize_text(predicate)


def _normalize_object(value: str) -> str:
    return _normalize_text(value)


# ---------------------------------------------------------------------------
# Numeric normalization
# ---------------------------------------------------------------------------

_NUMBER_WORDS = {
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


def _normalize_numeric_value(value: str) -> str:
    normalized = _normalize_text(value)

    if normalized in _NUMBER_WORDS:
        return _NUMBER_WORDS[normalized]

    return normalized


# ---------------------------------------------------------------------------
# Token / object comparison
# ---------------------------------------------------------------------------

def _token_set(text: str) -> set[str]:
    return set(
        _normalize_text(text).split()
    )


def _objects_are_equivalent(
    left: str,
    right: str,
) -> bool:
    left_normalized = _normalize_object(left)
    right_normalized = _normalize_object(right)

    if left_normalized == right_normalized:
        return True

    left_tokens = _token_set(left_normalized)
    right_tokens = _token_set(right_normalized)

    if not left_tokens or not right_tokens:
        return False

    return (
        left_tokens == right_tokens
        or left_tokens.issubset(right_tokens)
        or right_tokens.issubset(left_tokens)
    )


# ---------------------------------------------------------------------------
# Attribute comparison
# ---------------------------------------------------------------------------

def _attributes_conflict(
    left: Proposition,
    right: Proposition,
) -> bool:
    shared_attributes = (
        set(left.attributes)
        & set(right.attributes)
    )

    for attribute in shared_attributes:
        left_value = _normalize_text(
            left.attributes[attribute]
        )

        right_value = _normalize_text(
            right.attributes[attribute]
        )

        if attribute in {
            "year",
            "count",
            "number",
        }:
            left_value = _normalize_numeric_value(
                left_value
            )
            right_value = _normalize_numeric_value(
                right_value
            )

        if left_value != right_value:
            return True

    return False


def _attributes_are_equivalent(
    left: Proposition,
    right: Proposition,
) -> bool:
    if not left.attributes and not right.attributes:
        return True

    shared_attributes = (
        set(left.attributes)
        & set(right.attributes)
    )

    if not shared_attributes:
        return True

    for attribute in shared_attributes:
        left_value = _normalize_text(
            left.attributes[attribute]
        )

        right_value = _normalize_text(
            right.attributes[attribute]
        )

        if attribute in {
            "year",
            "count",
            "number",
        }:
            left_value = _normalize_numeric_value(
                left_value
            )
            right_value = _normalize_numeric_value(
                right_value
            )

        if left_value != right_value:
            return False

    return True


# ---------------------------------------------------------------------------
# Predicate-specific comparison
# ---------------------------------------------------------------------------

_SINGLE_VALUE_PREDICATES = {
    "founded",
    "headquartered_in",
    "capital_city",
    "has_employees",
    "has_offices",
    "revenue",
    "launched",
    "composition",
}


_SET_VALUE_PREDICATES = {
    "operates_in",
    "expanded_into",
}


_MULTI_VALUE_PREDICATES = {
    "manufactures",
    "sells",
    "provides",
    "offers",
}


def _numeric_objects_conflict(
    left: Proposition,
    right: Proposition,
) -> bool:
    return (
        _normalize_numeric_value(left.object)
        != _normalize_numeric_value(right.object)
    )


def _single_value_conflict(
    left: Proposition,
    right: Proposition,
) -> bool:
    return not _objects_are_equivalent(
        left.object,
        right.object,
    )


def _set_value_conflict(
    left: Proposition,
    right: Proposition,
) -> bool:
    left_value = _normalize_object(left.object)
    right_value = _normalize_object(right.object)

    return left_value != right_value


def _revenue_conflict(
    left: Proposition,
    right: Proposition,
) -> bool:
    left_value = _normalize_object(left.object)
    right_value = _normalize_object(right.object)

    if left_value == right_value:
        return False

    left_match = re.fullmatch(
        r"([\d,.]+)\s+(million|billion|thousand)",
        left_value,
    )

    right_match = re.fullmatch(
        r"([\d,.]+)\s+(million|billion|thousand)",
        right_value,
    )

    if not left_match or not right_match:
        return True

    left_amount = float(
        left_match.group(1).replace(",", "")
    )

    right_amount = float(
        right_match.group(1).replace(",", "")
    )

    left_unit = left_match.group(2)
    right_unit = right_match.group(2)

    multipliers = {
        "thousand": 1_000,
        "million": 1_000_000,
        "billion": 1_000_000_000,
    }

    left_amount *= multipliers[left_unit]
    right_amount *= multipliers[right_unit]

    return left_amount != right_amount


def _composition_conflict(
    left: Proposition,
    right: Proposition,
) -> bool:
    left_tokens = _token_set(left.object)
    right_tokens = _token_set(right.object)

    if left_tokens == right_tokens:
        return False

    # Composition claims describe a complete factual composition.
    # If the normalized compositions differ, treat them as conflicting.
    return True


def _predicate_values_conflict(
    predicate: str,
    left: Proposition,
    right: Proposition,
) -> bool:
    normalized_predicate = _normalize_predicate(
        predicate
    )

    if normalized_predicate in {
        "has_employees",
        "has_offices",
    }:
        return _numeric_objects_conflict(
            left,
            right,
        )

    if normalized_predicate == "revenue":
        return _revenue_conflict(
            left,
            right,
        )

    if normalized_predicate == "composition":
        return _composition_conflict(
            left,
            right,
        )

    if normalized_predicate in {
        "founded",
        "headquartered_in",
        "capital_city",
        "launched",
    }:
        return _single_value_conflict(
            left,
            right,
        )

    if normalized_predicate in _SET_VALUE_PREDICATES:
        return _set_value_conflict(
            left,
            right,
        )

    # Multi-valued predicates are additive.
    #
    # Example:
    #   "NovaTech manufactures electric bikes."
    #   "NovaTech manufactures electric bicycles and battery chargers."
    #
    # These are not contradictions because the second claim can contain
    # additional information.
    if normalized_predicate in _MULTI_VALUE_PREDICATES:
        return False

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare_propositions(
    left: Proposition,
    right: Proposition,
) -> ComparisonResult:
    """
    Compare two structured propositions.

    SAME:
        Both propositions express the same fact.

    CONFLICTING:
        Both propositions describe the same factual dimension but
        assert incompatible values.

    UNRELATED:
        The propositions do not establish a direct contradiction.
    """

    left_subject = _normalize_subject(
        left.subject
    )

    right_subject = _normalize_subject(
        right.subject
    )

    if left_subject != right_subject:
        return "UNRELATED"

    left_predicate = _normalize_predicate(
        left.predicate
    )

    right_predicate = _normalize_predicate(
        right.predicate
    )

    if left_predicate != right_predicate:
        return "UNRELATED"

    # Attributes represent additional dimensions of the same fact.
    if _attributes_conflict(
        left,
        right,
    ):
        return "CONFLICTING"

    # Exact / semantic object agreement.
    if _objects_are_equivalent(
        left.object,
        right.object,
    ):
        if _attributes_are_equivalent(
            left,
            right,
        ):
            return "SAME"

    # Predicate-specific contradiction rules.
    if _predicate_values_conflict(
        left_predicate,
        left,
        right,
    ):
        return "CONFLICTING"

    return "UNRELATED"