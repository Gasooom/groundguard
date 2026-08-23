from __future__ import annotations

from dataclasses import dataclass
import re


PromptInjectionCategory = str


@dataclass(frozen=True)
class PromptInjectionResult:
    detected: bool
    categories: tuple[PromptInjectionCategory, ...]
    evidence: tuple[str, ...]


_PATTERNS: tuple[
    tuple[PromptInjectionCategory, tuple[str, ...]],
    ...
] = (
    (
        "IGNORE_INSTRUCTIONS",
        (
            r"\bignore\s+(?:all\s+)?previous\s+instructions\b",
            r"\bignore\s+(?:all\s+)?prior\s+instructions\b",
            r"\bdisregard\s+(?:all\s+)?previous\s+instructions\b",
        ),
    ),
    (
        "SYSTEM_OVERRIDE",
        (
            r"\boverride\s+(?:the\s+)?system\s+(?:prompt|instructions)\b",
            r"\bnew\s+system\s+(?:prompt|instructions)\b",
            r"\byou\s+are\s+now\s+the\s+system\b",
        ),
    ),
    (
        "ROLE_HIJACKING",
        (
            r"\byou\s+are\s+now\s+(?:a|an)\b",
            r"\bact\s+as\s+(?:a|an)\s+unrestricted\b",
        ),
    ),
    (
        "PROMPT_EXTRACTION",
        (
            r"\breveal\s+(?:your|the)\s+(?:system\s+)?prompt\b",
            r"\bshow\s+(?:me\s+)?(?:your|the)\s+(?:system\s+)?prompt\b",
            r"\bshow\s+(?:me\s+)?(?:your|the)\s+system\s+instructions\b",
            r"\bprint\s+(?:your|the)\s+(?:system\s+)?instructions\b",
            r"\breveal\s+(?:your|the)\s+(?:system\s+)?instructions\b",
        ),
    ),
)


def detect_prompt_injection(
    text: str,
) -> PromptInjectionResult:
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    if not text.strip():
        return PromptInjectionResult(
            detected=False,
            categories=(),
            evidence=(),
        )

    categories: list[str] = []
    evidence: list[str] = []

    for category, patterns in _PATTERNS:
        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                categories.append(category)
                evidence.append(match.group(0))
                break

    return PromptInjectionResult(
        detected=bool(categories),
        categories=tuple(categories),
        evidence=tuple(evidence),
    )