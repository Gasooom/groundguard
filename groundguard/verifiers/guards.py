"""Deterministic guards that veto support on explicit mismatches.

A guard only fires against the candidate sentence that is most clearly
*about the same thing* as the claim (the "anchor"), and only with a recorded
signal. Guards never return SUPPORTED: when nothing fires they abstain and
the next verifier decides.

Anchor selection
    Among single-sentence candidates, pick the highest Dice overlap of
    *topic tokens* (content tokens minus numbers, units, qualifier words and
    exclusivity markers, so the very words being compared do not decide
    whether the sentences are comparable). The anchor must reach
    ``min_topic_dice``. Ties prefer a candidate with the claim's polarity,
    so ambiguity never manufactures a contradiction.

Checks against the anchor, in order
    1. polarity: claim negated vs anchor not (or the reverse) → CONTRADICTED
    2. quantities: same dimension, different value after unit conversion → CONTRADICTED
    3. years: the year attached to the same event word differs, or the claim's
       years are disjoint from the anchor's → CONTRADICTED
    4. qualifiers from a closed exclusive set (adults/children, before/after,
       all/some, …) differ → CONTRADICTED if the anchor marks the restriction
       as exclusive ("only", "exclusively", …), else NOT_ENOUGH_INFO

``min_topic_dice`` (default 0.5: the sentences share most of their topic
words) is an untuned default; calibration is M4 work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from groundguard.core.text import (
    STOP_WORDS,
    UNIT_ALIASES,
    content_tokens,
    is_negated,
    quantities,
    stem,
    words,
)
from groundguard.core.types import Claim, ClaimVerdict, EvidenceSpan, VerdictLabel


# Mutually exclusive qualifier groups. Each word maps to (group, canonical value).
_QUALIFIER_GROUPS: dict[str, tuple[str, ...]] = {
    "population": ("adult", "child", "adolescent", "infant", "elderly", "pregnant"),
    "order": ("before", "after"),
    "relative_time": ("earlier", "later"),
    "direction": ("increase", "decrease"),
    "comparison_high": ("higher", "lower"),
    "comparison_more": ("more", "less"),
    "position": ("above", "below"),
    "extreme": ("maximum", "minimum"),
    "scope_geo": ("domestic", "international"),
    "sex": ("male", "female"),
    "sector": ("public", "private"),
    "rank": ("first", "last"),
    "frequency": ("daily", "weekly", "monthly", "annual"),
    "quantifier": ("all", "some", "none", "most"),
}
_QUALIFIER_FORMS: dict[str, str] = {
    "adults": "adult", "children": "child", "kids": "child", "child": "child",
    "adolescents": "adolescent", "teenagers": "adolescent", "teens": "adolescent",
    "infants": "infant", "babies": "infant", "baby": "infant",
    "seniors": "elderly", "older": "elderly",
    "increases": "increase", "increased": "increase", "rises": "increase", "rose": "increase",
    "decreases": "decrease", "decreased": "decrease", "falls": "decrease", "fell": "decrease",
    "max": "maximum", "min": "minimum", "yearly": "annual", "annually": "annual",
    "every": "all", "each": "all",
}
_QUALIFIER_LOOKUP: dict[str, tuple[str, str]] = {}
for _group, _values in _QUALIFIER_GROUPS.items():
    for _value in _values:
        _QUALIFIER_LOOKUP[_value] = (_group, _value)
for _form, _value in _QUALIFIER_FORMS.items():
    _QUALIFIER_LOOKUP[_form] = next(
        (group, _value) for group, values in _QUALIFIER_GROUPS.items() if _value in values
    )

# Entailment within the quantifier group: evidence "all" supports claim "some".
_ENTAILED_BY = {("quantifier", "some"): {"all", "most"}, ("quantifier", "most"): {"all"}}

_EXCLUSIVE_MARKERS = re.compile(
    r"\b(?:only|exclusively|solely|restricted to|limited to|reserved for|except|excluding)\b",
    re.IGNORECASE,
)

_UNIT_DIMENSION: dict[str, tuple[str, float]] = {
    "ms": ("time", 0.001), "s": ("time", 1.0), "min": ("time", 60.0), "h": ("time", 3600.0),
    "day": ("time", 86400.0), "week": ("time", 604800.0), "month": ("time", 2629800.0),
    "year_unit": ("time", 31557600.0),
    "kb": ("storage", 1e3), "mb": ("storage", 1e6), "gb": ("storage", 1e9), "tb": ("storage", 1e12),
    "g": ("mass", 1.0), "kg": ("mass", 1000.0),
    "m": ("length", 1.0), "km": ("length", 1000.0),
    "percent": ("percent", 1.0), "usd": ("usd", 1.0), "eur": ("eur", 1.0),
}

_MONTHS = frozenset(
    "january february march april may june july august september october november december "
    "jan feb mar apr jun jul aug sep sept oct nov dec".split()
)
_UNIT_WORDS = frozenset(UNIT_ALIASES)


def _qualifiers(text: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for token in words(text):
        if token in _QUALIFIER_LOOKUP:
            group, value = _QUALIFIER_LOOKUP[token]
            found.setdefault(group, set()).add(value)
    return found


def _topic_tokens(text: str) -> set[str]:
    """Content tokens minus the words the guards compare (numbers, units,
    qualifiers, exclusivity markers), so those words cannot decide whether
    two sentences are about the same thing."""

    qualifier_stems = {stem(form) for form in _QUALIFIER_LOOKUP}
    excluded = {"only", "exclusively", "solely"}
    return {
        token
        for token in content_tokens(text)
        if not token[0].isdigit()
        and token not in _UNIT_WORDS
        and token not in excluded
        and token not in _QUALIFIER_LOOKUP
        and token not in qualifier_stems
    }


def _dice(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return 2 * len(left & right) / (len(left) + len(right))


def _event_years(text: str) -> dict[str, set[int]]:
    """Map the nearest preceding event word to the years attached to it.

    "opened in 2015 and moved to Nairobi in 2019" → {"open": {2015}, "nairobi": {2019}}
    Months, day numbers and stop words are skipped when looking back.
    """

    tokens = words(text)
    result: dict[str, set[int]] = {}
    for index, token in enumerate(tokens):
        if not (token.isdigit() and len(token) == 4 and 1800 <= int(token) <= 2100):
            continue
        for back in range(index - 1, max(-1, index - 6), -1):
            previous = tokens[back]
            if previous in STOP_WORDS or previous in _MONTHS or previous.isdigit() or previous in {"on", "in", "since"}:
                continue
            result.setdefault(stem(previous), set()).add(int(token))
            break
    return result


@dataclass(frozen=True)
class _Finding:
    label: VerdictLabel
    check: str
    rationale: str
    signal: dict[str, Any]


def _polarity(claim: str, anchor: str) -> _Finding | None:
    claim_negated, anchor_negated = is_negated(claim), is_negated(anchor)
    if claim_negated == anchor_negated:
        return None
    return _Finding(
        "CONTRADICTED",
        "negation",
        "The claim and the evidence make the same statement with opposite polarity.",
        {"claim_negated": claim_negated, "evidence_negated": anchor_negated},
    )


def _quantity_mismatch(claim: str, anchor: str) -> _Finding | None:
    claim_quantities = [q for q in quantities(claim) if q.kind == "quantity"]
    anchor_quantities = [q for q in quantities(anchor) if q.kind == "quantity"]
    for quantity in claim_quantities:
        dimension = _UNIT_DIMENSION.get(quantity.unit or "")
        if dimension is None:
            continue
        comparable = [
            other for other in anchor_quantities
            if _UNIT_DIMENSION.get(other.unit or "", ("?", 0.0))[0] == dimension[0]
        ]
        if not comparable:
            continue
        value = quantity.value * dimension[1]
        if any(abs(value - other.value * _UNIT_DIMENSION[other.unit or ""][1]) <= 1e-9 * max(1.0, abs(value)) for other in comparable):
            continue
        return _Finding(
            "CONTRADICTED",
            "quantity",
            f"The claim states {quantity.raw}; the evidence states "
            f"{', '.join(other.raw for other in comparable)} for the same kind of measure.",
            {"claim": quantity.raw, "evidence": [other.raw for other in comparable], "dimension": dimension[0]},
        )

    # Bare numbers attached to the same noun ("120 employees" vs "150 employees").
    claim_counts = _counted_nouns(claim)
    anchor_counts = _counted_nouns(anchor)
    for noun, values in claim_counts.items():
        if noun in anchor_counts and values.isdisjoint(anchor_counts[noun]):
            return _Finding(
                "CONTRADICTED",
                "quantity",
                f"The claim and the evidence give different counts of '{noun}'.",
                {"noun": noun, "claim": sorted(values), "evidence": sorted(anchor_counts[noun])},
            )
    return None


def _counted_nouns(text: str) -> dict[str, set[float]]:
    result: dict[str, set[float]] = {}
    for quantity in quantities(text):
        if quantity.kind != "number":
            continue
        following = words(text[quantity.end :])
        noun = next((token for token in following if token not in STOP_WORDS), None)
        if noun and not noun[0].isdigit() and noun not in _MONTHS:
            result.setdefault(stem(noun), set()).add(quantity.value)
    return result


def _year_mismatch(claim: str, anchor: str) -> _Finding | None:
    claim_years = {int(q.value) for q in quantities(claim) if q.kind == "year"}
    anchor_years = {int(q.value) for q in quantities(anchor) if q.kind == "year"}
    if not claim_years or not anchor_years:
        return None
    if claim_years.isdisjoint(anchor_years):
        return _Finding(
            "CONTRADICTED",
            "date",
            "The claim's year does not match the year in the evidence.",
            {"claim_years": sorted(claim_years), "evidence_years": sorted(anchor_years)},
        )
    claim_events = _event_years(claim)
    anchor_events = _event_years(anchor)
    for event, years in claim_events.items():
        if event in anchor_events and years.isdisjoint(anchor_events[event]):
            return _Finding(
                "CONTRADICTED",
                "date",
                f"The evidence attaches a different year to '{event}'.",
                {"event": event, "claim_years": sorted(years), "evidence_years": sorted(anchor_events[event])},
            )
    return None


def _qualifier_mismatch(claim: str, anchor: str) -> _Finding | None:
    claim_qualifiers = _qualifiers(claim)
    anchor_qualifiers = _qualifiers(anchor)
    for group, claim_values in claim_qualifiers.items():
        anchor_values = anchor_qualifiers.get(group)
        if not anchor_values or claim_values & anchor_values:
            continue
        if all(anchor_values & _ENTAILED_BY.get((group, value), set()) for value in claim_values):
            continue  # e.g. evidence "all" entails claim "some"
        exclusive = bool(_EXCLUSIVE_MARKERS.search(anchor))
        return _Finding(
            "CONTRADICTED" if exclusive else "NOT_ENOUGH_INFO",
            "qualifier",
            (
                f"The evidence restricts this to {', '.join(sorted(anchor_values))} exclusively; "
                f"the claim says {', '.join(sorted(claim_values))}."
                if exclusive
                else f"The evidence is about {', '.join(sorted(anchor_values))}; the claim is about "
                f"{', '.join(sorted(claim_values))}, which the evidence does not cover."
            ),
            {"group": group, "claim": sorted(claim_values), "evidence": sorted(anchor_values), "exclusive": exclusive},
        )
    return None


@dataclass(frozen=True)
class GuardVerifier:
    min_topic_dice: float = 0.5
    name: str = "guards"
    version: str = "1"

    def anchor(self, claim: Claim, candidates: Sequence[EvidenceSpan]) -> tuple[EvidenceSpan, float] | None:
        claim_topic = _topic_tokens(claim.text)
        claim_negated = is_negated(claim.text)
        best: tuple[float, bool, EvidenceSpan] | None = None
        for candidate in candidates:
            if re.search(r"[.!?]\s", candidate.text):
                continue  # guards compare against single sentences only
            score = _dice(claim_topic, _topic_tokens(candidate.text))
            same_polarity = is_negated(candidate.text) == claim_negated
            key = (score, same_polarity)
            if best is None or key > (best[0], best[1]):
                best = (score, same_polarity, candidate)
        if best is None or best[0] < self.min_topic_dice:
            return None
        return best[2], best[0]

    def verify(self, claim: Claim, candidates: Sequence[EvidenceSpan]) -> ClaimVerdict | None:
        anchored = self.anchor(claim, candidates)
        if anchored is None:
            return None
        anchor, topic_dice = anchored

        findings = [
            finding
            for check in (_polarity, _quantity_mismatch, _year_mismatch, _qualifier_mismatch)
            if (finding := check(claim.text, anchor.text)) is not None
        ]
        if not findings:
            return None

        contradicted = [finding for finding in findings if finding.label == "CONTRADICTED"]
        decisive = contradicted[0] if contradicted else findings[0]
        return ClaimVerdict(
            claim_id=claim.id,
            label=decisive.label,
            raw_score=topic_dice,
            evidence=(anchor,),
            verifier=f"{self.name}@{self.version}",
            rationale=decisive.rationale,
            signals={
                "fired": [finding.check for finding in findings],
                "topic_dice": round(topic_dice, 6),
                **{finding.check: finding.signal for finding in findings},
            },
        )
