import json
from collections import Counter
from pathlib import Path

from groundguard.domain.grounding import evaluate_grounding


ROOT = Path(__file__).resolve().parents[1]

BENCHMARK_FILES = [
    ROOT / "benchmark" / "examples" / "human_labeled_001_020.json",
    ROOT / "benchmark" / "batch_001_021_030.json",
    *sorted(
        (ROOT / "benchmark" / "examples").glob("batch_001_*.json")
    ),
]


def load_records():
    records = []

    for path in BENCHMARK_FILES:
        if path.exists():
            with path.open(encoding="utf-8") as file:
                records.extend(json.load(file))

    return records


def test_grounding_error_analysis():
    records = load_records()

    errors = []
    error_by_expected = Counter()

    for record in records:
        result = evaluate_grounding(
            record["context"],
            record["answer"],
        )

        expected = record["grounding_label"]

        if result.label != expected:
            errors.append(
                {
                    "id": record["id"],
                    "expected": expected,
                    "predicted": result.label,
                    "score": result.score,
                    "question": record["question"],
                    "answer": record["answer"],
                }
            )

            error_by_expected[expected] += 1

    print("\n=== Grounding Error Analysis ===")
    print(f"Total records: {len(records)}")
    print(f"Total errors: {len(errors)}")
    print(f"Error rate: {len(errors) / len(records):.2%}")

    print("\nErrors by expected label:")
    for label, count in error_by_expected.items():
        print(f"  {label}: {count}")

    print("\nFirst 20 errors:")

    for error in errors[:20]:
        print(
            f"\n{error['id']}"
            f"\nExpected: {error['expected']}"
            f"\nPredicted: {error['predicted']}"
            f"\nScore: {error['score']}"
            f"\nQuestion: {error['question']}"
            f"\nAnswer: {error['answer']}"
        )

    assert len(records) == 250