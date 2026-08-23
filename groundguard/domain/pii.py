from __future__ import annotations

import re

from groundguard.domain.safety import (
    PIICategory,
    PIIDetection,
)


_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+"
    r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

_PHONE_PATTERN = re.compile(
    r"(?<!\w)"
    r"(?:\+?\d{1,3}[\s.-]?)?"
    r"(?:\d{3}[\s.-]?){2}\d{3,4}"
    r"(?!\w)"
)

_IP_ADDRESS_PATTERN = re.compile(
    r"\b"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|"
    r"[1-9]?\d)"
    r"(?:\."
    r"(?:25[0-5]|2[0-4]\d|1\d\d|"
    r"[1-9]?\d)){3}"
    r"\b"
)

_CREDIT_CARD_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\d{4}[- ]?){3}\d{4}"
    r"(?!\d)"
)


def _find_matches(
    pattern: re.Pattern[str],
    text: str,
) -> list[str]:
    return [
        match.group(0)
        for match in pattern.finditer(text)
    ]


def detect_pii(
    text: str,
) -> PIIDetection:
    """
    Detect obvious PII patterns using deterministic
    regular-expression rules.
    """

    if not text.strip():
        return PIIDetection(
            detected=False,
            categories=[],
            evidence=[],
        )

    rules: list[
        tuple[
            PIICategory,
            re.Pattern[str],
        ]
    ] = [
        ("EMAIL", _EMAIL_PATTERN),
        ("PHONE", _PHONE_PATTERN),
        ("IP_ADDRESS", _IP_ADDRESS_PATTERN),
        ("CREDIT_CARD", _CREDIT_CARD_PATTERN),
    ]

    categories: list[PIICategory] = []
    evidence: list[str] = []

    for category, pattern in rules:
        matches = _find_matches(
            pattern,
            text,
        )

        if not matches:
            continue

        categories.append(category)
        evidence.extend(matches)

    return PIIDetection(
        detected=bool(categories),
        categories=categories,
        evidence=evidence,
    )