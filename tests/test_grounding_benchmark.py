import json
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


def test_grounding_baseline_on_benchmark():
    records = load_records()

    assert len(records) == 250

    evaluated = 0
    correct = 0

    for record in records:
        result = evaluate_grounding(
            record["context"],
            record["answer"],
            question=record["question"],
        )

        assert result.label in {
            "SUPPORTED",
            "PARTIALLY_SUPPORTED",
            "UNSUPPORTED",
        }

        evaluated += 1

        if result.label == record["grounding_label"]:
            correct += 1

    accuracy = correct / evaluated

    print(f"\nGrounding baseline accuracy: {accuracy:.2%}")
    print(f"Correct: {correct}/{evaluated}")

    assert evaluated == 250