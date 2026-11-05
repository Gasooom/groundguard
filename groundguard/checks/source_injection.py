"""Indirect prompt injection: instruction-like text inside retrieved sources.

Runs the v1 pattern detector on every source document. This is a signal,
not a defence: pattern matching is easy to evade, and documents that merely
discuss prompt injection can trigger it (probe ``src_inj_02``).
"""

from __future__ import annotations

from typing import Any, Sequence

from groundguard.core.types import SourceDocument
from groundguard.domain.prompt_injection import detect_prompt_injection


def check_sources(sources: Sequence[SourceDocument]) -> list[dict[str, Any]]:
    findings = []
    for source in sources:
        result = detect_prompt_injection(source.text)
        if result.detected:
            findings.append(
                {
                    "source_id": source.id,
                    "categories": list(result.categories),
                    "evidence": list(result.evidence),
                }
            )
    return findings
