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


def test_contradiction_error_analysis():
    records = load_benchmark_records()

    assert len(records) == 250

    errors = []

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

        expected = record[
            "contradiction_label"
        ]

        if result.label != expected:
            errors.append(
                {
                    "id": record.get(
                        "id",
                        "unknown",
                    ),
                    "expected": expected,
                    "predicted": result.label,
                    "score": result.score,
                    "question": record.get(
                        "question",
                        "",
                    ),
                    "answer": record[
                        "answer"
                    ],
                    "evidence": record[
                        "evidence"
                    ],
                }
            )

    print(
        "\n=== Contradiction Error Analysis ==="
    )

    print(
        f"Total records: {len(records)}"
    )

    print(
        f"Total errors: {len(errors)}"
    )

    print(
        f"Error rate: "
        f"{len(errors) / len(records):.2%}"
    )

    print(
        "\nErrors by expected label:"
    )

    print(
        Counter(
            error["expected"]
            for error in errors
        )
    )

    print(
        "\nErrors by predicted label:"
    )

    print(
        Counter(
            error["predicted"]
            for error in errors
        )
    )

    print(
        "\nFirst 20 errors:"
    )

    for error in errors[:20]:
        print(
            f"\n{error['id']}"
        )

        print(
            f"Expected: "
            f"{error['expected']}"
        )

        print(
            f"Predicted: "
            f"{error['predicted']}"
        )

        print(
            f"Score: "
            f"{error['score']}"
        )

        print(
            f"Question: "
            f"{error['question']}"
        )

        print(
            f"Answer: "
            f"{error['answer']}"
        )

        print(
            f"Evidence: "
            f"{error['evidence']}"
        )

    assert len(errors) >= 0