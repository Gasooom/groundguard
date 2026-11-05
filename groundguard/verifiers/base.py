"""Verifier protocol and ordered verifier chain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from groundguard.core.types import Claim, ClaimVerdict, EvidenceSpan


class Verifier(Protocol):
    """Decides a claim's verdict from candidate evidence, or abstains.

    Returning ``None`` means "no opinion": the next verifier in the chain
    decides. Verifiers must be deterministic for a given input and version.
    """

    name: str
    version: str

    def verify(self, claim: Claim, candidates: Sequence[EvidenceSpan]) -> ClaimVerdict | None: ...


def verifier_id(verifier: Verifier) -> str:
    return f"{verifier.name}@{verifier.version}"


@dataclass(frozen=True)
class VerifierChain:
    """Runs verifiers in order; the first non-abstaining verdict wins."""

    verifiers: tuple[Verifier, ...]

    def __post_init__(self) -> None:
        if not self.verifiers:
            raise ValueError("a verifier chain needs at least one verifier")

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(verifier_id(verifier) for verifier in self.verifiers)

    def verify(self, claim: Claim, candidates: Sequence[EvidenceSpan]) -> ClaimVerdict:
        for verifier in self.verifiers:
            verdict = verifier.verify(claim, candidates)
            if verdict is not None:
                return verdict
        return ClaimVerdict(
            claim_id=claim.id,
            label="NOT_ENOUGH_INFO",
            raw_score=0.0,
            evidence=(),
            verifier="chain@1",
            rationale="Every verifier in the chain abstained.",
        )
