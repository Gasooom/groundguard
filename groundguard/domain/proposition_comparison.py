from __future__ import annotations

import re
from typing import Literal

from groundguard.domain.propositions import Proposition


ComparisonResult = Literal[
    "SAME",
    "CONFLICTING",
    "UNRELATED",
]


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


def _normalize_subject(
    subject: str,
) -> str:
    return _normalize_text(subject)


def _normalize_predicate(
    predicate: str,
) -> str:
    return _normalize_text(predicate)


def _normalize_object(
    value: str,
) -> str:
    return _normalize_text(value)


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


def _normalize_numeric_value(
    value: str,
) -> str:
    normalized = _normalize_text(value)

    if normalized in _NUMBER_WORDS:
        return _NUMBER_WORDS[normalized]

    return normalized


def _token_set(
    text: str,
) -> set[str]:
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

    left_tokens = _token_set(
        left_normalized
    )

    right_tokens = _token_set(
        right_normalized
    )

    if not left_tokens or not right_tokens:
        return False

    return (
        left_tokens == right_tokens
        or left_tokens.issubset(right_tokens)
        or right_tokens.issubset(left_tokens)
    )


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
            "percentage",
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
            "percentage",
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


_SINGLE_VALUE_PREDICATES = {
    "founded",
    "headquartered_in",
    "capital_city",
    "has_employees",
    "has_offices",
    "has_planets",
    "revenue",
    "launched",
    "composition",
    "entered_into",
    "percentage_of",
    "largest",
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
        _normalize_numeric_value(
            left.object
        )
        != _normalize_numeric_value(
            right.object
        )
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
    """Compare individual members of a set-valued factual field.

    The extractor represents list claims as separate propositions.
    Therefore two different members of the same set-valued predicate
    are conflicting at proposition level when compared directly.

    Example:
        DataWorks operates in Tanzania.
        DataWorks operates in Kenya.

    This does not mean that a company cannot operate in both places;
    it means the two propositions themselves describe different
    values for the same extracted factual slot.
    """

    return not _objects_are_equivalent(
        left.object,
        right.object,
    )


def _revenue_conflict(
    left: Proposition,
    right: Proposition,
) -> bool:
    left_value = _normalize_object(
        left.object
    )

    right_value = _normalize_object(
        right.object
    )

    if left_value == right_value:
        return False

    left_match = re.fullmatch(
        r"([\d,.]+)\s+"
        r"(million|billion|thousand)",
        left_value,
    )

    right_match = re.fullmatch(
        r"([\d,.]+)\s+"
        r"(million|billion|thousand)",
        right_value,
    )

    if not left_match or not right_match:
        return True

    left_amount = float(
        left_match.group(1).replace(
            ",",
            "",
        )
    )

    right_amount = float(
        right_match.group(1).replace(
            ",",
            "",
        )
    )

    multipliers = {
        "thousand": 1_000,
        "million": 1_000_000,
        "billion": 1_000_000_000,
    }

    left_amount *= multipliers[
        left_match.group(2)
    ]

    right_amount *= multipliers[
        right_match.group(2)
    ]

    return left_amount != right_amount


def _composition_conflict(
    left: Proposition,
    right: Proposition,
) -> bool:
    left_tokens = _token_set(
        left.object
    )

    right_tokens = _token_set(
        right.object
    )

    if left_tokens == right_tokens:
        return False

    return True


def _split_multi_value_object(
    value: str,
) -> set[str]:
    normalized = _normalize_object(
        value
    )

    normalized = re.sub(
        r"\s+and\s+",
        ",",
        normalized,
    )

    values = {
        item.strip()
        for item in normalized.split(",")
        if item.strip()
    }

    return values


def _multi_value_conflict(
    left: Proposition,
    right: Proposition,
) -> bool:
    """
    Multi-value predicates are additive.

    Different products/services do not automatically
    establish contradiction.

    Example:

        CloudCore sells accounting software.
        CloudCore sells backup software.

    Both can be true.
    """

    left_values = _split_multi_value_object(
        left.object
    )

    right_values = _split_multi_value_object(
        right.object
    )

    if not left_values or not right_values:
        return False

    if left_values == right_values:
        return False

    if (
        left_values.issubset(right_values)
        or right_values.issubset(left_values)
    ):
        return False

    return False


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
        "has_planets",
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
        "entered_into",
        "largest",
        "percentage_of",
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

    if normalized_predicate in _MULTI_VALUE_PREDICATES:
        return _multi_value_conflict(
            left,
            right,
        )

    return False


def compare_propositions(
    left: Proposition,
    right: Proposition,
) -> ComparisonResult:
    """
    Compare two structured propositions.

    SAME:
        Same subject, predicate, object and compatible attributes.

    CONFLICTING:
        Same factual dimension with incompatible values.

    UNRELATED:
        No direct contradiction can be established.

    The comparator deliberately follows:

        unsupported != contradictory
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

    if _attributes_conflict(
        left,
        right,
    ):
        return "CONFLICTING"

    if _objects_are_equivalent(
        left.object,
        right.object,
    ):
        if _attributes_are_equivalent(
            left,
            right,
        ):
            return "SAME"

    if _predicate_values_conflict(
        left_predicate,
        left,
        right,
    ):
        return "CONFLICTING"

    return "UNRELATED"