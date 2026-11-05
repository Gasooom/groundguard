"""Shared text utilities for the v2 engine.

The v1 modules keep their own copies of similar helpers and are left
untouched (ADR-004). New code uses this module only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


NUMBER_WORDS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000,
}

# Function words that carry little content. Negation words, quantifiers
# and scope words are deliberately NOT stop words: the guards depend on them.
STOP_WORDS: frozenset[str] = frozenset(
    """
    a an the of in on at to for from by with as and or but if then than that
    this these those it its it's their there here is are was were be been
    being am do does did has have had having can could may might will would
    shall should must which who whom whose what when where why how about into
    over under per via up out also just very so such too i you he she we they
    me him her us them my your his our based according context provided
    """.split()
)

NEGATION_WORDS: frozenset[str] = frozenset(
    {"not", "no", "never", "none", "nor", "neither", "without", "cannot", "nothing", "nobody"}
)

_WORD = re.compile(r"\d+(?:[.,]\d+)*|[a-z]+(?:'[a-z]+)?")


def words(text: str) -> list[str]:
    """Lower-cased word tokens. Numbers keep decimal points and separators."""

    return _WORD.findall(text.lower())


def stem(token: str) -> str:
    """Very light suffix stripping, enough to match simple inflections."""

    if len(token) <= 3 or token[0].isdigit():
        return token
    for suffix, replacement in (
        ("ies", "y"),
        ("ing", ""),
        ("ed", ""),
        ("es", ""),
        ("s", ""),
    ):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            if suffix == "s" and token.endswith(("ss", "us", "is")):
                return token
            return token[: -len(suffix)] + replacement
    return token


def _canonical_number(token: str) -> str:
    if token in NUMBER_WORDS:
        return str(NUMBER_WORDS[token])
    if token[0].isdigit():
        cleaned = token.replace(",", "")
        try:
            value = float(cleaned)
        except ValueError:
            return token
        return str(int(value)) if value.is_integer() else str(value)
    return token


def content_tokens(text: str) -> list[str]:
    """Stemmed non-stop-word tokens, with numbers canonicalized.

    Negation words are excluded here too: polarity is compared separately
    by the guards, so it must not inflate or deflate lexical overlap.
    """

    result = []
    for token in words(text):
        if token.endswith("'s"):
            token = token[:-2]  # possessive: "kenya's" -> "kenya"
        if token in STOP_WORDS or token in NEGATION_WORDS or token.endswith("n't"):
            continue
        result.append(_canonical_number(stem(token)))
    return result


def is_negated(text: str) -> bool:
    for token in words(text):
        if token in NEGATION_WORDS or token.endswith("n't"):
            return True
    return False


def overlap(claim: str, evidence: str) -> float:
    """Fraction of the claim's content tokens that appear in the evidence."""

    claim_tokens = set(content_tokens(claim))
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & set(content_tokens(evidence))) / len(claim_tokens)


# ---------------------------------------------------------------- quantities

UNIT_ALIASES: dict[str, str] = {
    "ms": "ms", "millisecond": "ms", "milliseconds": "ms",
    "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s",
    "min": "min", "mins": "min", "minute": "min", "minutes": "min",
    "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
    "day": "day", "days": "day", "week": "week", "weeks": "week",
    "month": "month", "months": "month", "year": "year_unit", "years": "year_unit",
    "kb": "kb", "mb": "mb", "gb": "gb", "tb": "tb",
    "g": "g", "gram": "g", "grams": "g", "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "m": "m", "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "km": "km", "kilometer": "km", "kilometers": "km", "kilometre": "km", "kilometres": "km",
    "%": "percent", "percent": "percent", "per cent": "percent",
    "usd": "usd", "dollar": "usd", "dollars": "usd", "$": "usd",
    "eur": "eur", "euro": "eur", "euros": "eur",
}

_NUMBER_WORD_PATTERN = "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))
_QUANTITY = re.compile(
    r"(?P<currency>\$)?"
    r"(?<![\w.])(?P<number>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|"
    rf"(?:{_NUMBER_WORD_PATTERN})\b)"
    r"(?:\s*(?P<unit>%|per cent|[a-z]+))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str | None        # canonical unit, or None for a bare number
    kind: str               # "year", "quantity", or "number"
    raw: str
    start: int
    end: int


def _version_like(text: str, start: int, end: int) -> bool:
    """True for tokens such as 'v2', '2.0' after 'version', or '1.2.3'."""

    before = text[max(0, start - 9) : start].lower()
    after = text[end : end + 2]
    return before.rstrip().endswith(("version", "v", "release")) or after.startswith(".") and after[1:2].isdigit()


def quantities(text: str) -> list[Quantity]:
    """Extract numbers with optional units. Years are kept as their own kind.

    Version numbers ("version 2.0") are skipped, because they are names rather
    than measurements.
    """

    found: list[Quantity] = []
    for match in _QUANTITY.finditer(text):
        raw_number = match.group("number")
        start, number_end = match.start("number"), match.end("number")
        if _version_like(text, start, number_end):
            continue

        lowered = raw_number.lower()
        if lowered in NUMBER_WORDS:
            value = float(NUMBER_WORDS[lowered])
        else:
            value = float(raw_number.replace(",", ""))

        unit_raw = (match.group("unit") or "").lower()
        unit = UNIT_ALIASES.get(unit_raw)
        end = match.end("unit") if unit is not None else number_end
        if match.group("currency"):
            unit = "usd"
            start = match.start("currency")

        is_year = (
            unit is None
            and raw_number.isdigit()
            and len(raw_number) == 4
            and 1800 <= value <= 2100
        )
        kind = "year" if is_year else ("quantity" if unit else "number")
        found.append(Quantity(value, unit, kind, text[start:end], start, end))
    return found
