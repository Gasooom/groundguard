"""Score calibration, pure Python: isotonic regression (PAV) and Platt scaling.

Both map a verifier's raw score to P(verdict is correct). They are fitted
on development data only (docs/EVALUATION_METHODOLOGY.md §7).
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from typing import Any, Literal, Sequence


Direction = Literal["increasing", "decreasing"]


def _check(scores: Sequence[float], outcomes: Sequence[int]) -> None:
    if len(scores) != len(outcomes):
        raise ValueError("scores and outcomes must have the same length")
    if not scores:
        raise ValueError("cannot fit on empty data")
    if any(outcome not in (0, 1) for outcome in outcomes):
        raise ValueError("outcomes must be 0 or 1")
    if any(not math.isfinite(score) for score in scores):
        raise ValueError("scores must be finite")


def _correlation_sign(scores: Sequence[float], outcomes: Sequence[int]) -> Direction:
    n = len(scores)
    mean_s = sum(scores) / n
    mean_o = sum(outcomes) / n
    covariance = sum((s - mean_s) * (o - mean_o) for s, o in zip(scores, outcomes))
    return "decreasing" if covariance < 0 else "increasing"


@dataclass(frozen=True)
class IsotonicCalibrator:
    """Piecewise-constant monotone map fitted with pool-adjacent-violators.

    ``thresholds[i]`` is the smallest raw score of block ``i``. A score
    below the first threshold uses the first block (clipping).
    """

    thresholds: tuple[float, ...]
    values: tuple[float, ...]
    direction: Direction
    kind: str = "isotonic"

    def predict(self, score: float) -> float:
        index = max(0, bisect_right(self.thresholds, score) - 1)
        return self.values[index]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "direction": self.direction,
                "thresholds": list(self.thresholds), "values": list(self.values)}


def fit_isotonic(
    scores: Sequence[float],
    outcomes: Sequence[int],
    *,
    direction: Direction | Literal["auto"] = "auto",
) -> IsotonicCalibrator:
    _check(scores, outcomes)
    resolved: Direction = _correlation_sign(scores, outcomes) if direction == "auto" else direction
    sign = 1.0 if resolved == "increasing" else -1.0

    # Group equal scores, then pool adjacent violators on (sum, count) blocks.
    pairs = sorted(zip(scores, outcomes), key=lambda pair: pair[0])
    blocks: list[list[float]] = []  # [min_score, total, count]
    for score, outcome in pairs:
        if blocks and blocks[-1][0] == score:
            blocks[-1][1] += outcome
            blocks[-1][2] += 1
        else:
            blocks.append([score, float(outcome), 1.0])

    stack: list[list[float]] = []
    for block in blocks:
        stack.append(list(block))
        while len(stack) > 1 and sign * (stack[-2][1] / stack[-2][2]) > sign * (stack[-1][1] / stack[-1][2]):
            top = stack.pop()
            stack[-1][1] += top[1]
            stack[-1][2] += top[2]

    return IsotonicCalibrator(
        thresholds=tuple(block[0] for block in stack),
        values=tuple(round(block[1] / block[2], 10) for block in stack),
        direction=resolved,
    )


@dataclass(frozen=True)
class PlattCalibrator:
    """p = 1 / (1 + exp(a * score + b))."""

    a: float
    b: float
    kind: str = "platt"

    def predict(self, score: float) -> float:
        z = self.a * score + self.b
        if z >= 0:
            return math.exp(-z) / (1.0 + math.exp(-z))
        return 1.0 / (1.0 + math.exp(z))

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "a": self.a, "b": self.b}


def fit_platt(scores: Sequence[float], outcomes: Sequence[int], *, iterations: int = 100) -> PlattCalibrator:
    """Platt (1999) with the Lin et al. (2007) target smoothing, Newton steps."""

    _check(scores, outcomes)
    positives = sum(outcomes)
    negatives = len(outcomes) - positives
    high = (positives + 1.0) / (positives + 2.0)
    low = 1.0 / (negatives + 2.0)
    targets = [high if outcome else low for outcome in outcomes]

    a, b = 0.0, math.log((negatives + 1.0) / (positives + 1.0))
    for _ in range(iterations):
        grad_a = grad_b = h_aa = h_ab = h_bb = 0.0
        for score, target in zip(scores, targets):
            p = PlattCalibrator(a, b).predict(score)
            # d(log-likelihood)/dz = p - target for p = 1 / (1 + exp(z)), z = a*s + b
            difference = p - target
            weight = p * (1.0 - p)
            grad_a += difference * score
            grad_b += difference
            h_aa += weight * score * score
            h_ab += weight * score
            h_bb += weight
        h_aa += 1e-12
        h_bb += 1e-12
        determinant = h_aa * h_bb - h_ab * h_ab
        if abs(determinant) < 1e-18:
            break
        step_a = (h_bb * grad_a - h_ab * grad_b) / determinant
        step_b = (-h_ab * grad_a + h_aa * grad_b) / determinant
        a, b = a + step_a, b + step_b
        if abs(step_a) < 1e-10 and abs(step_b) < 1e-10:
            break
    return PlattCalibrator(round(a, 12), round(b, 12))


def calibrator_from_dict(data: dict[str, Any]) -> IsotonicCalibrator | PlattCalibrator:
    if data.get("kind") == "isotonic":
        thresholds, values = data["thresholds"], data["values"]
        if not thresholds or len(thresholds) != len(values) or list(thresholds) != sorted(thresholds):
            raise ValueError("isotonic calibrator needs sorted thresholds matching values")
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("isotonic values must be probabilities")
        if data["direction"] not in ("increasing", "decreasing"):
            raise ValueError("invalid direction")
        return IsotonicCalibrator(tuple(thresholds), tuple(values), data["direction"])
    if data.get("kind") == "platt":
        return PlattCalibrator(float(data["a"]), float(data["b"]))
    raise ValueError(f"unknown calibrator kind {data.get('kind')!r}")
