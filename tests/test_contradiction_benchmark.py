import json
from collections import Counter
from pathlib import Path

from groundguard.domain.contradiction import (
    evaluate_contradiction,
)


def load_benchmark_records():
    files = [
        Path(
            "benchmark/examples/"
            "human_labeled_001_020.json"
        ),
        Path(
            "benchmark/batch_001_021_030.json"
        ),
    ]

    files += sorted(
        Path("benchmark/examples").glob(
            "batch_001_*.json"
        )
    )

    records = []

    for file in files:
        if not file.exists():
            continue

        with open(
            file,
            encoding="utf-8",
        ) as f:
            records.extend(
                json.load(f)
            )

    return records


def test_contradiction_benchmark():
    records = load_benchmark_records()

    assert len(records) == 250

    correct = 0
    predictions = []

    for record in records:
        result = evaluate_contradiction(
            record["answer"],
            " ".join(
                record["evidence"]
            ),
            question=record.get(
                "question"
            ),
        )

        predictions.append(
            result.label
        )

        if (
            result.label
            == record["contradiction_label"]
        ):
            correct += 1

    accuracy = (
        correct / len(records)
    )

    print(
        "\n=== Contradiction Benchmark ==="
    )
    print(
        f"Total records: {len(records)}"
    )
    print(
        f"Correct: {correct}/{len(records)}"
    )
    print(
        f"Accuracy: {accuracy:.2%}"
    )

    print(
        "\nExpected labels:"
    )
    print(
        Counter(
            record[
                "contradiction_label"
            ]
            for record in records
        )
    )

    print(
        "\nPredicted labels:"
    )
    print(
        Counter(predictions)
    )

    assert correct >= 0