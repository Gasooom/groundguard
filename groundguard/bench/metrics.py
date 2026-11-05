"""Classification and decision metrics with uncertainty estimates.

Pure standard library. Every rate is returned with its numerator and
denominator so reports never show a percentage without its basis.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from typing import Callable, Hashable, Sequence


@dataclass(frozen=True)
class Rate:
    numerator: int
    denominator: int

    @property
    def value(self) -> float | None:
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    def to_dict(self) -> dict[str, object]:
        value = self.value
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": None if value is None else round(value, 6),
        }


@dataclass(frozen=True)
class LabelScores:
    precision: Rate
    recall: Rate
    support: int

    @property
    def f1(self) -> float | None:
        precision = self.precision.value
        recall = self.recall.value
        if precision is None or recall is None:
            return None
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def to_dict(self) -> dict[str, object]:
        f1 = self.f1
        return {
            "precision": self.precision.to_dict(),
            "recall": self.recall.to_dict(),
            "f1": None if f1 is None else round(f1, 6),
            "support": self.support,
        }


@dataclass(frozen=True)
class DecisionRates:
    """Decision-level error rates. Only ``ACCEPT`` counts as acceptance."""

    false_accept: Rate   # bad answers accepted / bad answers
    false_reject: Rate   # good answers not accepted / good answers
    true_accepts: int
    true_rejects: int
    false_accepts: int
    false_rejects: int

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["false_accept"] = self.false_accept.to_dict()
        data["false_reject"] = self.false_reject.to_dict()
        return data


def _check_lengths(gold: Sequence[object], predicted: Sequence[object]) -> None:
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted must have the same length")
    if not gold:
        raise ValueError("gold and predicted cannot be empty")


def accuracy(gold: Sequence[Hashable], predicted: Sequence[Hashable]) -> Rate:
    _check_lengths(gold, predicted)
    return Rate(sum(g == p for g, p in zip(gold, predicted)), len(gold))


def confusion_matrix(
    gold: Sequence[str],
    predicted: Sequence[str],
    labels: Sequence[str],
) -> dict[str, dict[str, int]]:
    """Return ``matrix[gold_label][predicted_label] = count``.

    Labels outside ``labels`` raise, rather than being silently dropped.
    """

    _check_lengths(gold, predicted)
    known = set(labels)
    unknown = (set(gold) | set(predicted)) - known
    if unknown:
        raise ValueError(f"labels not in label set: {sorted(unknown)}")

    matrix = {g: {p: 0 for p in labels} for g in labels}
    for g, p in zip(gold, predicted):
        matrix[g][p] += 1
    return matrix


def per_label_scores(
    gold: Sequence[str],
    predicted: Sequence[str],
    labels: Sequence[str],
) -> dict[str, LabelScores]:
    matrix = confusion_matrix(gold, predicted, labels)
    scores: dict[str, LabelScores] = {}
    for label in labels:
        true_positive = matrix[label][label]
        predicted_positive = sum(matrix[g][label] for g in labels)
        actual_positive = sum(matrix[label].values())
        scores[label] = LabelScores(
            precision=Rate(true_positive, predicted_positive),
            recall=Rate(true_positive, actual_positive),
            support=actual_positive,
        )
    return scores


def macro_f1(scores: dict[str, LabelScores]) -> float | None:
    """Mean F1 over labels with support > 0 and a defined F1."""

    values = [
        f1
        for label_scores in scores.values()
        if label_scores.support > 0 and (f1 := label_scores.f1) is not None
    ]
    if not values:
        return None
    return sum(values) / len(values)


def decision_rates(
    gold_good: Sequence[bool],
    decisions: Sequence[str],
) -> DecisionRates:
    """FAR/FRR where a decision counts as acceptance only if it is ``ACCEPT``.

    For binary score thresholds this matches
    ``groundguard.evaluation.decision_metrics.evaluate_threshold``.
    """

    _check_lengths(gold_good, decisions)
    true_accepts = true_rejects = false_accepts = false_rejects = 0
    for good, decision in zip(gold_good, decisions):
        accepted = decision == "ACCEPT"
        if accepted and good:
            true_accepts += 1
        elif accepted and not good:
            false_accepts += 1
        elif good:
            false_rejects += 1
        else:
            true_rejects += 1

    return DecisionRates(
        false_accept=Rate(false_accepts, false_accepts + true_rejects),
        false_reject=Rate(false_rejects, false_rejects + true_accepts),
        true_accepts=true_accepts,
        true_rejects=true_rejects,
        false_accepts=false_accepts,
        false_rejects=false_rejects,
    )


def wilson_interval(
    successes: int,
    total: int,
    *,
    z: float = 1.959963984540054,
) -> tuple[float, float] | None:
    """Wilson score interval for a binomial proportion (95% by default)."""

    if total < 0 or successes < 0 or successes > total:
        raise ValueError("require 0 <= successes <= total")
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half_width = (
        z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    ) / denominator
    low = 0.0 if successes == 0 else max(0.0, centre - half_width)
    high = 1.0 if successes == total else min(1.0, centre + half_width)
    return (low, high)


def bootstrap_ci(
    groups: Sequence[str],
    statistic: Callable[[Sequence[int]], float | None],
    *,
    n_resamples: int = 2000,
    seed: int = 0,
    confidence: float = 0.95,
) -> tuple[float, float] | None:
    """Percentile bootstrap CI that resamples *groups*, not records.

    ``groups[i]`` is the group id of record ``i``. Each resample draws group
    ids with replacement and passes the indices of all their records to
    ``statistic``. Resamples where the statistic is undefined (``None``) are
    skipped. Returns ``None`` if fewer than half the resamples are defined.
    """

    if n_resamples < 1:
        raise ValueError("n_resamples must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")

    members: dict[str, list[int]] = {}
    for index, group in enumerate(groups):
        members.setdefault(group, []).append(index)
    group_ids = sorted(members)
    if not group_ids:
        return None

    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(n_resamples):
        indices: list[int] = []
        for _ in group_ids:
            indices.extend(members[group_ids[rng.randrange(len(group_ids))]])
        value = statistic(indices)
        if value is not None:
            values.append(value)

    if len(values) < n_resamples / 2:
        return None

    values.sort()
    alpha = (1.0 - confidence) / 2
    low_index = int(math.floor(alpha * (len(values) - 1)))
    high_index = int(math.ceil((1.0 - alpha) * (len(values) - 1)))
    return (values[low_index], values[high_index])
