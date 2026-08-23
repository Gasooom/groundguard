import json
from pathlib import Path

from groundguard.domain.contradiction import evaluate_contradiction
from groundguard.domain.grounding import evaluate_grounding
from groundguard.domain.relevance import evaluate_relevance
from groundguard.evaluation.decision_metrics import (
    evaluate_threshold,
    reliability_score,
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


def load_records():
    records = []

    for path in BENCHMARK_FILES:
        if path.exists():
            with path.open(encoding="utf-8") as file:
                records.extend(json.load(file))

    return records


def test_threshold_analysis():
    records = load_records()

    assert len(records) == 250

    scores = []
    expected = []

    for record in records:
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

        scores.append(
            reliability_score(
                grounding_score=grounding.score,
                relevance_score=relevance.score,
                contradiction_score=contradiction.score,
            )
        )

        expected.append(
            record["grounding_label"] == "SUPPORTED"
            and record["relevance_label"] == "RELEVANT"
            and record["contradiction_label"]
            == "NOT_CONTRADICTORY"
        )

    print("\n=== Threshold Analysis ===")
    print(
        "Threshold | FAR    | FRR    | "
        "False Accepts | False Rejects"
    )
    print("-" * 65)

    for threshold in [
        0.50,
        0.55,
        0.60,
        0.65,
        0.70,
        0.75,
        0.80,
        0.85,
        0.90,
    ]:
        metrics = evaluate_threshold(
            scores,
            expected,
            threshold,
        )

        print(
            f"{threshold:9.2f} | "
            f"{metrics.false_accept_rate:6.2%} | "
            f"{metrics.false_reject_rate:6.2%} | "
            f"{metrics.false_accepts:13} | "
            f"{metrics.false_rejects:13}"
        )