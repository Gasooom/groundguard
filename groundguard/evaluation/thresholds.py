from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdPolicy:
    """
    GroundGuard threshold policy.

    The current benchmark identifies 0.70 as the initial
    safety-oriented candidate threshold.
    """

    candidate_threshold: float = 0.70

    def __post_init__(self) -> None:
        if not 0.0 <= self.candidate_threshold <= 1.0:
            raise ValueError(
                "candidate_threshold must be between 0.0 and 1.0"
            )


DEFAULT_THRESHOLD_POLICY = ThresholdPolicy()