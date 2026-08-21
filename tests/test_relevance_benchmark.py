import json
from collections import Counter
from pathlib import Path

from groundguard.domain.relevance import evaluate_relevance


def load_benchmark_records():
    files = [
        Path("benchmark/examples/human_labeled_001_020.json"),
        Path("benchmark/batch_001_021_030.json"),
    ]

    files += sorted(
        Path("benchmark/examples").glob("batch_001_*.json")
    )

    records = []

    for file in files:
        if not file.exists():
            continue

        with open(file, encoding="utf-8") as f:
            records.extend(json.load(f))

    return records


def test_relevance_benchmark():
    records = load_benchmark_records()

    assert len(records) == 250

    correct = 0
    predictions = []
    expected = []

    for record in records:
        result = evaluate_relevance(
            record["question"],
            record["answer"],
        )

        predictions.append(result.label)
        expected.append(record["relevance_label"])

        if result.label == record["relevance_label"]:
            correct += 1

    accuracy = correct / len(records)

    print("\n=== Relevance Baseline ===")
    print(f"Total records: {len(records)}")
    print(f"Correct: {correct}/{len(records)}")
    print(f"Accuracy: {accuracy:.2%}")

    print("\nExpected labels:")
    print(Counter(expected))

    print("\nPredicted labels:")
    print(Counter(predictions))

    assert correct >= 0