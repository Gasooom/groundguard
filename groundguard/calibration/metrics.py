"""Calibration quality: expected calibration error, Brier score, reliability bins."""

from __future__ import annotations

from typing import Any, Sequence


def _check(probabilities: Sequence[float], outcomes: Sequence[int]) -> None:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("need equal-length, non-empty probabilities and outcomes")
    if any(not 0.0 <= p <= 1.0 for p in probabilities):
        raise ValueError("probabilities must be in [0, 1]")


def equal_mass_bins(probabilities: Sequence[float], outcomes: Sequence[int], bins: int = 10) -> list[dict[str, Any]]:
    """Sort by probability and cut into ``bins`` groups of (nearly) equal size."""

    _check(probabilities, outcomes)
    if bins < 1:
        raise ValueError("bins must be positive")
    order = sorted(range(len(probabilities)), key=lambda i: probabilities[i])
    n = len(order)
    result = []
    for b in range(bins):
        members = order[b * n // bins : (b + 1) * n // bins]
        if not members:
            continue
        result.append(
            {
                "count": len(members),
                "mean_confidence": sum(probabilities[i] for i in members) / len(members),
                "accuracy": sum(outcomes[i] for i in members) / len(members),
            }
        )
    return result


def expected_calibration_error(probabilities: Sequence[float], outcomes: Sequence[int], bins: int = 10) -> float:
    """ECE = sum over bins of (n_b / N) * |accuracy_b - confidence_b|, equal-mass bins."""

    total = len(probabilities)
    return float(
        sum(
            item["count"] / total * abs(item["accuracy"] - item["mean_confidence"])
            for item in equal_mass_bins(probabilities, outcomes, bins)
        )
    )


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    _check(probabilities, outcomes)
    return sum((p - o) ** 2 for p, o in zip(probabilities, outcomes)) / len(probabilities)
