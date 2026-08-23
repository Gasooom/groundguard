from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class DecisionMetrics:
    threshold: float
    false_accept_rate: float
    false_reject_rate: float
    true_accepts: int
    true_rejects: int
    false_accepts: int
    false_rejects: int
    total: int


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    metrics: DecisionMetrics


def reliability_score(
    *,
    grounding_score: float,
    relevance_score: float,
    contradiction_score: float,
) -> float:
    """
    Convert the three component scores into one conservative
    reliability score.

    Higher is better.
    """

    for name, value in {
        "grounding_score": grounding_score,
        "relevance_score": relevance_score,
        "contradiction_score": contradiction_score,
    }.items():
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"{name} must be between 0.0 and 1.0"
            )

    score = min(
        grounding_score,
        relevance_score,
        1.0 - contradiction_score,
    )

    return round(score, 4)


def evaluate_threshold(
    scores: Sequence[float],
    expected_reliable: Sequence[bool],
    threshold: float,
) -> DecisionMetrics:
    """
    Evaluate a reliability threshold.

    score >= threshold -> predicted reliable
    score < threshold  -> predicted unreliable
    """

    if not 0.0 <= threshold <= 1.0:
        raise ValueError(
            "threshold must be between 0.0 and 1.0"
        )

    if len(scores) != len(expected_reliable):
        raise ValueError(
            "scores and expected_reliable must have "
            "the same length"
        )

    if not scores:
        raise ValueError(
            "scores and expected_reliable cannot be empty"
        )

    true_accepts = 0
    true_rejects = 0
    false_accepts = 0
    false_rejects = 0

    for score, expected in zip(
        scores,
        expected_reliable,
    ):
        if not 0.0 <= score <= 1.0:
            raise ValueError(
                "all scores must be between 0.0 and 1.0"
            )

        predicted_reliable = score >= threshold

        if predicted_reliable and expected:
            true_accepts += 1

        elif not predicted_reliable and not expected:
            true_rejects += 1

        elif predicted_reliable and not expected:
            false_accepts += 1

        else:
            false_rejects += 1

    total = len(scores)

    false_accept_rate = (
        false_accepts
        / (false_accepts + true_rejects)
        if false_accepts + true_rejects
        else 0.0
    )

    false_reject_rate = (
        false_rejects
        / (false_rejects + true_accepts)
        if false_rejects + true_accepts
        else 0.0
    )

    return DecisionMetrics(
        threshold=round(threshold, 4),
        false_accept_rate=round(
            false_accept_rate,
            4,
        ),
        false_reject_rate=round(
            false_reject_rate,
            4,
        ),
        true_accepts=true_accepts,
        true_rejects=true_rejects,
        false_accepts=false_accepts,
        false_rejects=false_rejects,
        total=total,
    )


def tune_threshold(
    scores: Sequence[float],
    expected_reliable: Sequence[bool],
    *,
    step: float = 0.01,
) -> ThresholdResult:
    """
    Search thresholds from 0.0 through 1.0.

    Select the threshold minimizing:

        false_accept_rate + false_reject_rate

    Ties are resolved toward the higher threshold to favor
    safer decisions.
    """

    if step <= 0.0 or step > 1.0:
        raise ValueError(
            "step must be greater than 0.0 and at most 1.0"
        )

    if not scores:
        raise ValueError(
            "scores and expected_reliable cannot be empty"
        )

    if len(scores) != len(expected_reliable):
        raise ValueError(
            "scores and expected_reliable must have "
            "the same length"
        )

    thresholds: list[float] = []

    current = 0.0

    while current <= 1.0 + 1e-9:
        thresholds.append(
            round(min(current, 1.0), 4)
        )
        current += step

    best: DecisionMetrics | None = None

    for threshold in thresholds:
        metrics = evaluate_threshold(
            scores,
            expected_reliable,
            threshold,
        )

        if best is None:
            best = metrics
            continue

        current_error = (
            metrics.false_accept_rate
            + metrics.false_reject_rate
        )

        best_error = (
            best.false_accept_rate
            + best.false_reject_rate
        )

        if current_error < best_error:
            best = metrics

        elif (
            current_error == best_error
            and metrics.threshold > best.threshold
        ):
            best = metrics

    assert best is not None

    return ThresholdResult(
        threshold=best.threshold,
        metrics=best,
    )