from dataclasses import dataclass


@dataclass(frozen=True)
class GroundingResult:
    score: float
    grounded: bool
    evidence: list[str]