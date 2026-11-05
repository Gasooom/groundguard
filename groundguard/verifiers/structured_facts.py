"""Adapter over the v0.1.0 proposition engine (narrow domain, ADR-005).

The v1 extractor understands a fixed set of predicates (``founded``,
``sells``, ``operates_in``, ``has_employees``, ...). This verifier is
**contradiction-only**: it answers CONTRADICTED when the v1 comparator calls
a claim/evidence proposition pair ``CONFLICTING`` on a single-valued
predicate, and abstains otherwise. It never returns SUPPORTED, because a
matching proposition does not cover content the extractor ignored
("founded in 2018 by Jane Doe" matches "founded in 2018"); support is left to
the coverage backend.

Not carried over: the v1 question-aware rule that treats different values of
an additive predicate as a contradiction when the question asks about it.
That rule inferred exhaustiveness from question wording; the methodology
(§3.1) requires the source itself to claim exhaustiveness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from groundguard.core.types import Claim, ClaimVerdict, EvidenceSpan
from groundguard.domain.proposition_comparison import compare_propositions
from groundguard.domain.propositions import extract_propositions


# Predicates where several values can be true at once. A different value is
# additional information, not a conflict, so CONFLICTING is not trusted.
ADDITIVE_PREDICATES = frozenset(
    {"sells", "provides", "offers", "manufactures", "operates_in", "expanded_into", "composition"}
)


@dataclass(frozen=True)
class StructuredFactsVerifier:
    name: str = "structured_facts"
    version: str = "1"

    def verify(self, claim: Claim, candidates: Sequence[EvidenceSpan]) -> ClaimVerdict | None:
        claim_propositions = extract_propositions(claim.text)
        if not claim_propositions:
            return None

        conflict: tuple[EvidenceSpan, str] | None = None
        for candidate in candidates:
            for evidence_proposition in extract_propositions(candidate.text):
                for claim_proposition in claim_propositions:
                    comparison = compare_propositions(claim_proposition, evidence_proposition)
                    described = (
                        f"{claim_proposition.subject} | {claim_proposition.predicate} | "
                        f"{claim_proposition.object}  vs  {evidence_proposition.subject} | "
                        f"{evidence_proposition.predicate} | {evidence_proposition.object}"
                    )
                    if (
                        comparison == "CONFLICTING"
                        and claim_proposition.predicate not in ADDITIVE_PREDICATES
                        and conflict is None
                    ):
                        conflict = (candidate, described)

        if conflict is not None:
            candidate, described = conflict
            return ClaimVerdict(
                claim_id=claim.id,
                label="CONTRADICTED",
                raw_score=1.0,
                evidence=(candidate,),
                verifier=f"{self.name}@{self.version}",
                rationale="The claim states a different value for the same structured fact.",
                signals={"propositions": described},
            )
        return None
