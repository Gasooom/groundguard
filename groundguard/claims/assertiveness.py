"""Separate factual assertions from questions, hedges and meta-text.

Non-assertive text is kept in the output (so the user can see it) but is
not checked for grounding. Meta prefixes such as "Based on the context," are
stripped so the factual remainder is still checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_META_PREFIX = re.compile(
    r"^\s*(?:(?:based on|according to|from|per)\s+(?:the\s+)?"
    r"(?:provided\s+|supplied\s+|given\s+)?(?:context|information|documents?|sources?|text|passage)"
    r"|as\s+(?:stated|mentioned|described)\s+in\s+the\s+(?:context|documents?|sources?|text))"
    r"\s*,?\s*",
    re.IGNORECASE,
)

_HEDGES = (
    re.compile(r"^\s*i(?:\s+am|'m)\s+not\s+sure\b", re.IGNORECASE),
    re.compile(r"^\s*i\s+(?:do\s+not|don't)\s+know\b", re.IGNORECASE),
    re.compile(r"^\s*(?:the\s+)?(?:context|documents?|sources?)\s+(?:does|do)\s+not\s+(?:say|mention|specify|state)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:there\s+is\s+)?no\s+information\s+(?:is\s+)?(?:available|provided)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class Assessment:
    assertive: bool
    reason: str | None = None
    strip_prefix: int = 0


def classify(text: str, *, question: bool = False) -> Assessment:
    stripped = text.strip()
    if not stripped:
        return Assessment(False, "empty")
    if question or stripped.endswith("?"):
        return Assessment(False, "question")
    for pattern in _HEDGES:
        if pattern.search(stripped):
            return Assessment(False, "hedge_or_abstention")

    match = _META_PREFIX.match(text)
    if match and match.end() < len(text):
        return Assessment(True, None, strip_prefix=match.end())
    return Assessment(True)
