from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PIICategory = Literal[
    "EMAIL",
    "PHONE",
    "IP_ADDRESS",
    "CREDIT_CARD",
]


SafetyCategory = Literal[
    "PII",
    "PROMPT_INJECTION",
]


@dataclass(frozen=True)
class PIIDetection:
    detected: bool
    categories: list[PIICategory]
    evidence: list[str]


@dataclass(frozen=True)
class PromptInjectionDetection:
    detected: bool
    evidence: list[str]


@dataclass(frozen=True)
class SafetyResult:
    safe: bool

    pii_detected: bool
    prompt_injection_detected: bool

    pii_categories: list[PIICategory]
    evidence: list[str]


def build_safety_result(
    *,
    pii: PIIDetection,
    prompt_injection: PromptInjectionDetection,
) -> SafetyResult:
    """
    Combine PII and prompt-injection results into
    one deterministic safety result.
    """

    detected = (
        pii.detected
        or prompt_injection.detected
    )

    evidence = [
        *pii.evidence,
        *prompt_injection.evidence,
    ]

    return SafetyResult(
        safe=not detected,
        pii_detected=pii.detected,
        prompt_injection_detected=(
            prompt_injection.detected
        ),
        pii_categories=list(pii.categories),
        evidence=evidence,
    )