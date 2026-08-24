from __future__ import annotations

from dataclasses import dataclass, replace
import re
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

    This function is intentionally conservative and does not use
    question context.
    """

    if _set_predicate_conflicts(
        answer_propositions,
        evidence_propositions,
    ):
        return ContradictionResult(
            score=1.0,
            contradictory=True,
            label="CONTRADICTORY",
            evidence=[evidence],
        )

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
    Determine whether at least one answer proposition has an
    equivalent proposition in the evidence.
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


def _question_mentions_predicate(
    question: str,
    proposition: Proposition,
) -> bool:
    """
    Determine whether the question appears to ask about the
    factual dimension represented by the proposition.

    This is intentionally conservative.
    """

    normalized_question = question.lower()

    predicate = proposition.predicate.lower()

    predicate_terms = {
        "founded": (
            "founded",
            "established",
            "started",
            "created",
            "when",
            "year",
        ),
        "capital_city": (
            "capital",
            "city",
        ),
        "has_employees": (
            "employee",
            "employees",
            "staff",
            "people",
            "how many",
        ),
        "has_offices": (
            "office",
            "offices",
            "locations",
            "how many",
        ),
        "has_planets": (
            "planet",
            "planets",
            "how many",
        ),
        "revenue": (
            "revenue",
            "income",
            "sales",
            "earn",
            "generated",
        ),
        "launched": (
            "launched",
            "launch",
            "released",
            "release",
            "when",
            "year",
        ),
        "entered_into": (
            "entered",
            "enter",
            "market",
            "country",
            "when",
            "year",
        ),
        "headquartered_in": (
            "headquartered",
            "headquarters",
            "located",
            "location",
            "where",
        ),
        "operates_in": (
            "operate",
            "operates",
            "operating",
            "where",
            "countries",
            "locations",
        ),
        "expanded_into": (
            "expanded",
            "expand",
            "market",
            "country",
            "where",
            "when",
        ),
        "manufactures": (
            "manufacture",
            "manufactures",
            "make",
            "makes",
            "products",
            "product",
        ),
        "sells": (
            "sell",
            "sells",
            "sold",
            "products",
            "product",
        ),
        "provides": (
            "provide",
            "provides",
            "services",
            "service",
            "equipment",
            "software",
        ),
        "offers": (
            "offer",
            "offers",
            "services",
            "service",
            "products",
            "product",
        ),
        "composition": (
            "consists",
            "contains",
            "made",
            "composition",
            "components",
        ),
        "percentage_of": (
            "percent",
            "percentage",
            "%",
            "how much",
        ),
        "largest": (
            "largest",
            "biggest",
            "greatest",
        ),
    }

    terms = predicate_terms.get(
        predicate,
        (),
    )

    return any(
        term in normalized_question
        for term in terms
    )


def _objects_are_obviously_different(
    left: Proposition,
    right: Proposition,
) -> bool:
    """
    Determine whether two propositions contain clearly different
    factual values.

    This is used only for question-aware additive predicates.

    Example:

        CloudCore sells accounting software.
        CloudCore sells backup software.

    The objects are clearly different.

    We do NOT treat this as a contradiction without question context,
    because both products could legitimately exist.
    """

    left_object = left.object.lower().strip()
    right_object = right.object.lower().strip()

    if not left_object or not right_object:
        return False

    left_tokens = set(re.findall(r"\b[a-z0-9]+\b", left_object))
    right_tokens = set(re.findall(r"\b[a-z0-9]+\b", right_object))

    if not left_tokens or not right_tokens:
        return False

    # Additive facts can legitimately have different values. Treat them
    # as contradictory only when the answer and evidence share no
    # meaningful lexical content at all. This preserves paraphrases and
    # partially overlapping product/service lists.
    stopwords = {
        "the", "a", "an", "and", "or", "of", "for", "to",
        "in", "on", "with", "its", "their", "software", "services",
        "service", "systems", "system", "tools", "equipment",
    }
    left_tokens -= stopwords
    right_tokens -= stopwords

    return not (left_tokens & right_tokens)


def _question_aware_additive_conflict(
    question: str,
    answer_proposition: Proposition,
    evidence_proposition: Proposition,
) -> bool:
    """
    Detect a contradiction for additive factual predicates when
    the question explicitly asks for that factual dimension.

    Additive predicates include:

        sells
        provides
        offers
        manufactures
        operates_in
        expanded_into

    These predicates are normally allowed to contain multiple values.

    Therefore:

        CloudCore sells accounting software.
        CloudCore sells backup software.

    is NOT automatically contradictory.

    But when the question asks:

        What products does CloudCore sell?

    and the benchmark/evaluation treats the supplied evidence as
    the authoritative answer to that question, a materially
    different answer should be treated as contradictory.
    """

    predicate = (
        answer_proposition.predicate.lower()
    )

    additive_predicates = {
        "sells",
        "provides",
        "offers",
        "manufactures",
        "operates_in",
        "expanded_into",
    }

    if predicate not in additive_predicates:
        return False

    if not _question_mentions_predicate(
        question,
        answer_proposition,
    ):
        return False

    return _objects_are_obviously_different(
        answer_proposition,
        evidence_proposition,
    )


def _set_predicate_conflicts(
    answer_propositions: list[Proposition],
    evidence_propositions: list[Proposition],
) -> bool:
    """Compare complete extracted sets for set-valued predicates."""

    set_predicates = {
        "operates_in",
    }

    def groups(items: list[Proposition]):
        result: dict[tuple[str, str], set[str]] = {}
        for proposition in items:
            key = (
                proposition.subject.strip().lower(),
                proposition.predicate.strip().lower(),
            )
            if proposition.predicate.strip().lower() in set_predicates:
                result.setdefault(key, set()).add(
                    proposition.object.strip().lower()
                )
        return result

    answer_groups = groups(answer_propositions)
    evidence_groups = groups(evidence_propositions)

    for key, answer_values in answer_groups.items():
        evidence_values = evidence_groups.get(key)
        if evidence_values is None:
            continue
        if answer_values != evidence_values:
            return True

    return False


def _subjects_are_compatible(
    left: str,
    right: str,
) -> bool:
    """Allow conservative entity aliases such as Acme / Acme Technologies."""
    left_tokens = set(re.findall(r"\b[a-z0-9]+\b", left.lower()))
    right_tokens = set(re.findall(r"\b[a-z0-9]+\b", right.lower()))

    if not left_tokens or not right_tokens:
        return False

    generic = {"the", "company", "organization", "business", "firm"}
    if left_tokens <= generic or right_tokens <= generic:
        return False

    return (
        left_tokens == right_tokens
        or left_tokens.issubset(right_tokens)
        or right_tokens.issubset(left_tokens)
    )


def _candidate_proposition_conflicts(
    question: str | None,
    answer_proposition: Proposition,
    evidence_proposition: Proposition,
) -> bool:
    """
    Determine whether two propositions should be treated as
    contradictory.

    Priority:

    1. Explicit structured contradiction.
    2. Question-aware contradiction for additive predicates.
    3. Otherwise, no contradiction.

    This preserves the principle:

        unsupported != contradictory

    while allowing the benchmark's question context to distinguish
    additive facts from answers that fail to answer the requested
    factual dimension.
    """

    if answer_proposition.predicate.strip().lower() in {
        "operates_in",
    }:
        # Set-valued predicates are evaluated as complete sets above.
        # Do not perform pairwise comparison here, because a matching
        # member plus a different member would create a false conflict.
        return False

    comparison = compare_propositions(
        answer_proposition,
        evidence_proposition,
    )

    if comparison == "CONFLICTING":
        return True

    if comparison == "SAME":
        return False

    if not question:
        return False

    if not _subjects_are_compatible(
        answer_proposition.subject,
        evidence_proposition.subject,
    ):
        return False

    # When the only mismatch is an entity alias such as
    # "Acme" vs "Acme Technologies", re-run the structured
    # comparison with a shared subject. This preserves the
    # existing strict subject behavior in compare_propositions
    # while allowing the question-aware evaluation layer to
    # recognize common entity abbreviations.
    if (
        answer_proposition.predicate.strip().lower()
        != evidence_proposition.predicate.strip().lower()
    ):
        return False

    aligned_evidence = replace(
        evidence_proposition,
        subject=answer_proposition.subject,
    )

    aligned_comparison = compare_propositions(
        answer_proposition,
        aligned_evidence,
    )

    if aligned_comparison == "CONFLICTING":
        return True

    if aligned_comparison == "SAME":
        return False

    return _question_aware_additive_conflict(
        question,
        answer_proposition,
        evidence_proposition,
    )


def evaluate_contradiction(
    answer: str,
    evidence: str,
    question: str | None = None,
) -> ContradictionResult:
    """
    Evaluate whether an answer contradicts supplied evidence.

    Backward compatibility:

        evaluate_contradiction(
            answer,
            evidence,
        )

    Question-aware evaluation:

        evaluate_contradiction(
            answer,
            evidence,
            question=question,
        )

    The question is optional so existing callers and regression
    tests continue to work.

    Important design principle:

        unsupported != contradictory
    """

    if (
        not answer.strip()
        or not evidence.strip()
    ):
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

    if (
        not answer_propositions
        or not evidence_propositions
    ):
        return ContradictionResult(
            score=0.0,
            contradictory=False,
            label="NOT_CONTRADICTORY",
            evidence=[],
        )

    if _set_predicate_conflicts(
        answer_propositions,
        evidence_propositions,
    ):
        return ContradictionResult(
            score=1.0,
            contradictory=True,
            label="CONTRADICTORY",
            evidence=[evidence],
        )

    for answer_proposition in answer_propositions:
        for evidence_proposition in evidence_propositions:
            if _candidate_proposition_conflicts(
                question,
                answer_proposition,
                evidence_proposition,
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