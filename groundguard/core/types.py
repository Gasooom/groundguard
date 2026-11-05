"""Typed domain model for claim-level evaluation (engine v2).

All types are frozen dataclasses with a ``to_dict()`` that returns
JSON-compatible data. Offsets are character offsets into the original text,
half-open ``[start, end)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


VerdictLabel = Literal["SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_INFO"]
VERDICT_LABELS: tuple[VerdictLabel, ...] = ("SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_INFO")

ClaimOrigin = Literal["sentence", "clause", "conjunct"]
Granularity = Literal["sentence", "clause", "conjunct"]
GRANULARITIES: tuple[Granularity, ...] = ("sentence", "clause", "conjunct")

SourceKind = Literal["context", "tool_output", "reference"]

DecisionLabel = Literal["ACCEPT", "FLAG", "REJECT", "HUMAN_REVIEW"]


@dataclass(frozen=True)
class Span:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span [{self.start}, {self.end})")

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}


@dataclass(frozen=True)
class SourceDocument:
    id: str
    text: str
    kind: SourceKind = "context"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "text": self.text}


@dataclass(frozen=True)
class Claim:
    """A checkable statement extracted from the answer.

    ``text`` is what verifiers check. For conjunct claims it may include a
    subject or verb prefix copied from elsewhere in the sentence, so it is not
    always a substring of the answer. ``answer_span`` always points at the
    answer text the claim was derived from.
    """

    id: str
    text: str
    answer_span: Span
    origin: ClaimOrigin
    assertive: bool = True
    non_assertive_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "answer_span": self.answer_span.to_dict(),
            "origin": self.origin,
            "assertive": self.assertive,
            "non_assertive_reason": self.non_assertive_reason,
        }


@dataclass(frozen=True)
class EvidenceSpan:
    source_id: str
    span: Span
    text: str
    retrieval_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "span": self.span.to_dict(),
            "text": self.text,
            "retrieval_score": round(self.retrieval_score, 6),
        }


@dataclass(frozen=True)
class ClaimVerdict:
    """The verdict for one claim and why it was reached.

    ``raw_score`` is verifier-native and is never a probability.
    ``confidence`` stays ``None`` until a calibrator exists for this verifier
    version (docs/EVALUATION_METHODOLOGY.md §7).
    """

    claim_id: str
    label: VerdictLabel
    raw_score: float
    evidence: tuple[EvidenceSpan, ...]
    verifier: str
    rationale: str
    signals: Mapping[str, Any] = field(default_factory=dict)
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "label": self.label,
            "raw_score": round(self.raw_score, 6),
            "confidence": self.confidence,
            "verifier": self.verifier,
            "rationale": self.rationale,
            "signals": dict(self.signals),
            "evidence": [item.to_dict() for item in self.evidence],
        }
