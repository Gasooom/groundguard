"""Turn predictions into a metrics report with views and confidence intervals."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from groundguard.bench.datasets import (
    BenchmarkRecord,
    assign_context_groups,
    deduplicate,
)
from groundguard.bench.metrics import (
    Rate,
    accuracy,
    bootstrap_ci,
    confusion_matrix,
    decision_rates,
    macro_f1,
    per_label_scores,
    wilson_interval,
)
from groundguard.bench.runner import Prediction
from groundguard.core.serialization import sha256_json
from groundguard.evaluation.decision_metrics import evaluate_threshold


GROUNDING_LABELS = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED")
RELEVANCE_LABELS = ("RELEVANT", "IRRELEVANT")
CONTRADICTION_LABELS = ("CONTRADICTORY", "NOT_CONTRADICTORY")

DIMENSIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("grounding", "grounding_label", GROUNDING_LABELS),
    ("relevance", "relevance_label", RELEVANCE_LABELS),
    ("contradiction", "contradiction_label", CONTRADICTION_LABELS),
)

# Gold acceptability used by the v0.1.0 decision tests.
ACCEPTABILITY_DEFINITION = (
    "legacy@1: good iff grounding_label == SUPPORTED and "
    "relevance_label == RELEVANT and contradiction_label == NOT_CONTRADICTORY"
)

DECISION_LABELS = ("ACCEPT", "FLAG", "REJECT", "HUMAN_REVIEW")

THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)

BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 0


def is_good(record: BenchmarkRecord) -> bool:
    return (
        record.grounding_label == "SUPPORTED"
        and record.relevance_label == "RELEVANT"
        and record.contradiction_label == "NOT_CONTRADICTORY"
    )


def predictions_hash(predictions: Sequence[Any]) -> str:
    return sha256_json([prediction.to_dict() for prediction in predictions])


def _rounded(interval: tuple[float, float] | None) -> list[float] | None:
    if interval is None:
        return None
    return [round(interval[0], 6), round(interval[1], 6)]


def _rate_with_intervals(
    rate: Rate,
    groups: Sequence[str],
    statistic: Callable[[Sequence[int]], float | None],
) -> dict[str, object]:
    data = rate.to_dict()
    data["wilson_95"] = _rounded(wilson_interval(rate.numerator, rate.denominator))
    data["group_bootstrap_95"] = _rounded(
        bootstrap_ci(
            groups,
            statistic,
            n_resamples=BOOTSTRAP_RESAMPLES,
            seed=BOOTSTRAP_SEED,
        )
    )
    return data


def _view_metrics(
    records: Sequence[BenchmarkRecord],
    predictions: Sequence[Prediction],
) -> dict[str, Any]:
    groups_by_id = assign_context_groups(records)
    groups = [groups_by_id[record.id] for record in records]

    view: dict[str, Any] = {
        "records": len(records),
        "context_groups": len(set(groups)),
    }

    for name, field, labels in DIMENSIONS:
        gold = [getattr(record, field) for record in records]
        predicted = [getattr(prediction, field) for prediction in predictions]

        def accuracy_on(indices: Sequence[int], gold: list[str] = gold, predicted: list[str] = predicted) -> float | None:
            if not indices:
                return None
            return sum(gold[i] == predicted[i] for i in indices) / len(indices)

        scores = per_label_scores(gold, predicted, labels)
        f1 = macro_f1(scores)
        view[name] = {
            "accuracy": _rate_with_intervals(accuracy(gold, predicted), groups, accuracy_on),
            "macro_f1": None if f1 is None else round(f1, 6),
            "per_label": {label: score.to_dict() for label, score in scores.items()},
            "confusion_matrix": confusion_matrix(gold, predicted, labels),
        }

    gold_good = [is_good(record) for record in records]
    decisions = [prediction.system_decision for prediction in predictions]
    rates = decision_rates(gold_good, decisions)

    def far_on(indices: Sequence[int]) -> float | None:
        bad = [i for i in indices if not gold_good[i]]
        if not bad:
            return None
        return sum(decisions[i] == "ACCEPT" for i in bad) / len(bad)

    def frr_on(indices: Sequence[int]) -> float | None:
        good = [i for i in indices if gold_good[i]]
        if not good:
            return None
        return sum(decisions[i] != "ACCEPT" for i in good) / len(good)

    def review_on(indices: Sequence[int]) -> float | None:
        if not indices:
            return None
        return sum(decisions[i] == "HUMAN_REVIEW" for i in indices) / len(indices)

    def far_auto_on(indices: Sequence[int]) -> float | None:
        bad = [i for i in indices if not gold_good[i] and decisions[i] != "HUMAN_REVIEW"]
        if not bad:
            return None
        return sum(decisions[i] == "ACCEPT" for i in bad) / len(bad)

    decision_counts = {label: decisions.count(label) for label in DECISION_LABELS}
    reviewed = decision_counts["HUMAN_REVIEW"]
    bad_auto = [i for i in range(len(records)) if not gold_good[i] and decisions[i] != "HUMAN_REVIEW"]
    view["decision"] = {
        "acceptability": ACCEPTABILITY_DEFINITION,
        "distribution": decision_counts,
        "false_accept": _rate_with_intervals(rates.false_accept, groups, far_on),
        "false_reject": _rate_with_intervals(rates.false_reject, groups, frr_on),
        # Share of all answers routed to a person.
        "review_rate": _rate_with_intervals(Rate(reviewed, len(records)), groups, review_on),
        # FAR over bad answers the system decided itself (excludes HUMAN_REVIEW).
        "false_accept_among_auto_decided": _rate_with_intervals(
            Rate(sum(decisions[i] == "ACCEPT" for i in bad_auto), len(bad_auto)), groups, far_auto_on
        ),
        "true_accepts": rates.true_accepts,
        "true_rejects": rates.true_rejects,
        "false_accepts": rates.false_accepts,
        "false_rejects": rates.false_rejects,
    }

    scores_list = [prediction.reliability_score for prediction in predictions]
    sweep = []
    for threshold in THRESHOLDS:
        metrics = evaluate_threshold(scores_list, gold_good, threshold)
        sweep.append(
            {
                "threshold": threshold,
                "false_accept_rate": metrics.false_accept_rate,
                "false_reject_rate": metrics.false_reject_rate,
                "false_accepts": metrics.false_accepts,
                "false_rejects": metrics.false_rejects,
            }
        )
    view["reliability_score_threshold_sweep"] = sweep
    return view


def build_metrics(
    records: Sequence[BenchmarkRecord],
    predictions: Sequence[Prediction],
) -> dict[str, Any]:
    """Metrics for the full dataset, the deduplicated view and each source."""

    if len(records) != len(predictions):
        raise ValueError("records and predictions must align")
    for record, prediction in zip(records, predictions):
        if record.id != prediction.id:
            raise ValueError(f"misaligned record {record.id} / {prediction.id}")

    by_id = {prediction.id: prediction for prediction in predictions}

    def subset(selected: Sequence[BenchmarkRecord]) -> dict[str, Any]:
        return _view_metrics(selected, [by_id[record.id] for record in selected])

    views: dict[str, Any] = {
        "all": subset(records),
        "dedup": subset(deduplicate(records)),
    }
    for source in sorted({record.source for record in records}):
        views[f"source={source}"] = subset(
            [record for record in records if record.source == source]
        )
    return views
