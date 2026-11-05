"""Citation markers in answers, and whether the cited source supports the claim.

Recognized markers: ``[1]``, ``[1, 3]``, ``[doc-a]``, ``[source: doc-a]``.
Numbers refer to sources by 1-based position unless a source has that id.
A bracketed token counts as a citation only if every reference in it
resolves to a source, so text such as ``[REDACTED]`` or ``[sic]`` is left alone.

Markers are masked with spaces of the same length before segmentation, so
claim spans stay valid offsets into the original answer and marker digits
never reach the verifiers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from groundguard.core.types import Claim, ClaimVerdict, SourceDocument


_MARKER = re.compile(r"\[(?:source:\s*)?([A-Za-z0-9_.\-]+(?:\s*,\s*[A-Za-z0-9_.\-]+)*)\]", re.IGNORECASE)


@dataclass(frozen=True)
class CitationMarker:
    start: int
    end: int
    text: str
    source_ids: tuple[str, ...]


def _resolve(reference: str, sources: Sequence[SourceDocument]) -> str | None:
    by_id = {source.id: source.id for source in sources}
    if reference in by_id:
        return reference
    if reference.isdigit() and 1 <= int(reference) <= len(sources):
        return sources[int(reference) - 1].id
    return None


def find_citations(answer: str, sources: Sequence[SourceDocument]) -> tuple[CitationMarker, ...]:
    markers: list[CitationMarker] = []
    for match in _MARKER.finditer(answer):
        references = [part.strip() for part in match.group(1).split(",")]
        resolved = [_resolve(reference, sources) for reference in references]
        if any(item is None for item in resolved):
            continue
        markers.append(
            CitationMarker(
                match.start(), match.end(), match.group(0),
                tuple(dict.fromkeys(item for item in resolved if item is not None)),
            )
        )
    return tuple(markers)


def mask_citations(answer: str, markers: Sequence[CitationMarker]) -> str:
    masked = list(answer)
    for marker in markers:
        masked[marker.start : marker.end] = " " * (marker.end - marker.start)
    return "".join(masked)


def assign_citations(claims: Sequence[Claim], markers: Sequence[CitationMarker]) -> dict[str, list[CitationMarker]]:
    """A marker belongs to the last claim that starts before it."""

    ordered = sorted((claim for claim in claims if claim.assertive), key=lambda claim: claim.answer_span.start)
    assignment: dict[str, list[CitationMarker]] = {}
    for marker in markers:
        owner = None
        for claim in ordered:
            if claim.answer_span.start <= marker.start:
                owner = claim
        if owner is not None:
            assignment.setdefault(owner.id, []).append(marker)
    return assignment


Verify = Callable[[Claim, Sequence[SourceDocument]], ClaimVerdict]


def check_citations(
    claims: Sequence[Claim],
    markers: Sequence[CitationMarker],
    sources: Sequence[SourceDocument],
    verify_against: Verify,
) -> dict[str, Any]:
    """Verify each cited claim against its cited sources only."""

    by_id = {source.id: source for source in sources}
    assignment = assign_citations(claims, markers)
    claims_by_id = {claim.id: claim for claim in claims}
    items: list[dict[str, Any]] = []
    for claim_id, claim_markers in assignment.items():
        cited_ids = tuple(dict.fromkeys(i for marker in claim_markers for i in marker.source_ids))
        verdict = verify_against(claims_by_id[claim_id], [by_id[i] for i in cited_ids])
        items.append(
            {
                "claim_id": claim_id,
                "markers": [marker.text for marker in claim_markers],
                "cited_sources": list(cited_ids),
                "label_against_cited": verdict.label,
                "supported": verdict.label == "SUPPORTED",
                "evidence": [item.to_dict() for item in verdict.evidence],
            }
        )
    assertive = [claim for claim in claims if claim.assertive]
    supported = sum(item["supported"] for item in items)
    return {
        "markers": len(markers),
        "cited_claims": len(items),
        "assertive_claims": len(assertive),
        "supported_citations": supported,
        "citation_precision": None if not items else round(supported / len(items), 6),
        "failed": any(not item["supported"] for item in items),
        "items": items,
    }
