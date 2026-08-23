import json
from pathlib import Path

from groundguard.domain.contradiction import evaluate_contradiction
from groundguard.domain.decision import evaluate_decision
from groundguard.domain.grounding import evaluate_grounding
from groundguard.domain.relevance import evaluate_relevance
from groundguard.evaluation.decision_metrics import (
    evaluate_threshold,
    reliability_score,
    tune_threshold,
)


ROOT = Path(__file__).resolve().parents[1]


BENCHMARK_FILES = [
    ROOT / "benchmark" / "examples" / "human_labeled_001_020.json",
    ROOT / "benchmark" / "batch_001_021_030.json",
    *sorted(
        (ROOT / "benchmark" / "examples").glob(
            "batch_001_*.json"
        )
    ),
]


def load_benchmark_records():
    records = []

    for path in BENCHMARK_FILES:
        if not path.exists():
            continue

        with path.open(encoding="utf-8") as file:
            records.extend(json.load(file))

    return records


def evaluate_record(record):
    grounding = evaluate_grounding(
        record["context"],
        record["answer"],
        question=record["question"],
    )

    relevance = evaluate_relevance(
        record["question"],
        record["answer"],
    )

    contradiction = evaluate_contradiction(
        record["answer"],
        " ".join(record["evidence"]),
    )

    decision = evaluate_decision(
        grounding=grounding,
        relevance=relevance,
        contradiction=contradiction,
    )

    score = reliability_score(
        grounding_score=grounding.score,
        relevance_score=relevance.score,
        contradiction_score=contradiction.score,
    )

    return decision, score


def expected_reliable(record):
    return (
        record["grounding_label"] == "SUPPORTED"
        and record["relevance_label"] == "RELEVANT"
        and record["contradiction_label"]
        == "NOT_CONTRADICTORY"
    )


def test_decision_metrics_on_benchmark():
    records = load_benchmark_records()

    assert len(records) == 250

    scores = []
    expected = []

    for record in records:
        _, score = evaluate_record(record)

        scores.append(score)
        expected.append(
            expected_reliable(record)
        )

    result = tune_threshold(
        scores,
        expected,
    )

    print("\n=== Sprint 6 Decision Metrics ===")
    print(f"Records: {len(records)}")
    print(f"Best threshold: {result.threshold:.4f}")
    print(
        f"False Accept Rate: "
        f"{result.metrics.false_accept_rate:.2%}"
    )
    print(
        f"False Reject Rate: "
        f"{result.metrics.false_reject_rate:.2%}"
    )
    print(
        f"True accepts: "
        f"{result.metrics.true_accepts}"
    )
    print(
        f"True rejects: "
        f"{result.metrics.true_rejects}"
    )
    print(
        f"False accepts: "
        f"{result.metrics.false_accepts}"
    )
    print(
        f"False rejects: "
        f"{result.metrics.false_rejects}"
    )

    assert result.metrics.total == 250


def test_default_threshold_metrics_on_benchmark():
    records = load_benchmark_records()

    assert len(records) == 250

    scores = []
    expected = []

    for record in records:
        _, score = evaluate_record(record)

        scores.append(score)
        expected.append(
            expected_reliable(record)
        )

    metrics = evaluate_threshold(
        scores,
        expected,
        threshold=0.5,
    )

    print("\n=== Sprint 6 Default Threshold ===")
    print(
        f"Threshold: "
        f"{metrics.threshold:.4f}"
    )
    print(
        f"False Accept Rate: "
        f"{metrics.false_accept_rate:.2%}"
    )
    print(
        f"False Reject Rate: "
        f"{metrics.false_reject_rate:.2%}"
    )

    assert metrics.total == 250