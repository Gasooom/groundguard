"""Lexical coverage backend. Never abstains.

Two scoring modes:

``content`` (default)
    Fraction of the claim's content tokens (stop words, negation words
    removed; light stemming; numbers canonicalized) found in the candidate.
``v1``
    The v0.1.0 scorer, ``groundguard.domain.claims.similarity``, which counts
    every token including stop words, plus the v1 rule that candidates whose
    numbers are disjoint from the claim's are skipped. Kept for comparison.

The threshold is a configuration value. Its default is chosen by ablation on
development data and recorded in the M2 report, not assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from groundguard.core.text import content_tokens
from groundguard.core.types import Claim, ClaimVerdict, EvidenceSpan
from groundguard.domain.claims import factual_values, similarity


LexicalMode = Literal["content", "v1"]


def _content_coverage(claim: str, evidence: str) -> tuple[float, list[str]]:
    claim_tokens = list(dict.fromkeys(content_tokens(claim)))
    if not claim_tokens:
        return 0.0, []
    evidence_tokens = set(content_tokens(evidence))
    missing = [token for token in claim_tokens if token not in evidence_tokens]
    return 1.0 - len(missing) / len(claim_tokens), missing


@dataclass(frozen=True)
class LexicalVerifier:
    threshold: float = 1.0
    mode: LexicalMode = "content"
    name: str = "lexical"

    def __post_init__(self) -> None:
        if not 0.0 < self.threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        if self.mode not in ("content", "v1"):
            raise ValueError(f"unknown mode {self.mode!r}")

    @property
    def version(self) -> str:
        return f"1-{self.mode}-{self.threshold:g}"

    def _score(self, claim: str, evidence: str) -> tuple[float, list[str]]:
        if self.mode == "content":
            return _content_coverage(claim, evidence)
        claim_values, evidence_values = factual_values(claim), factual_values(evidence)
        if claim_values and evidence_values and claim_values.isdisjoint(evidence_values):
            return 0.0, sorted(claim_values)
        return similarity(claim, evidence), []

    def verify(self, claim: Claim, candidates: Sequence[EvidenceSpan]) -> ClaimVerdict:
        best: EvidenceSpan | None = None
        best_score, best_missing = 0.0, list[str]()
        for candidate in candidates:
            score, missing = self._score(claim.text, candidate.text)
            # Prefer higher coverage, then the shorter (single-sentence) window.
            if best is None or score > best_score or (
                score == best_score and len(candidate.text) < len(best.text)
            ):
                best, best_score, best_missing = candidate, score, missing

        identifier = f"{self.name}@{self.version}"
        if best is not None and best_score >= self.threshold:
            return ClaimVerdict(
                claim_id=claim.id,
                label="SUPPORTED",
                raw_score=best_score,
                evidence=(best,),
                verifier=identifier,
                rationale=f"{best_score:.0%} of the claim's content is covered by the cited evidence.",
                signals={"coverage": round(best_score, 6)},
            )
        return ClaimVerdict(
            claim_id=claim.id,
            label="NOT_ENOUGH_INFO",
            raw_score=best_score,
            evidence=(best,) if best is not None else (),
            verifier=identifier,
            rationale=(
                "No candidate evidence covers the claim."
                if best is None
                else f"Best evidence covers {best_score:.0%} of the claim's content "
                f"(threshold {self.threshold:.0%})."
            ),
            signals={"coverage": round(best_score, 6), "uncovered": best_missing},
        )
