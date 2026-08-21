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


def test_relevance_error_analysis():
    records = load_benchmark_records()

    assert len(records) == 250

    errors = []

    for record in records:
        result = evaluate_relevance(
            record["question"],
            record["answer"],
        )

        if result.label != record["relevance_label"]:
            errors.append(
                {
                    "id": record["id"],
                    "expected": record["relevance_label"],
                    "predicted": result.label,
                    "score": result.score,
                    "question": record["question"],
                    "answer": record["answer"],
                }
            )

    print("\n=== Relevance Error Analysis ===")
    print(f"Total records: {len(records)}")
    print(f"Total errors: {len(errors)}")
    print(
        f"Error rate: "
        f"{len(errors) / len(records):.2%}"
    )

    print("\nErrors by expected label:")
    print(
        Counter(
            error["expected"]
            for error in errors
        )
    )

    print("\nErrors by predicted label:")
    print(
        Counter(
            error["predicted"]
            for error in errors
        )
    )

    print("\nFirst 20 errors:")

    for error in errors[:20]:
        print(f"\n{error['id']}")
        print(f"Expected: {error['expected']}")
        print(f"Predicted: {error['predicted']}")
        print(f"Score: {error['score']}")
        print(f"Question: {error['question']}")
        print(f"Answer: {error['answer']}")

    assert len(errors) < len(records)