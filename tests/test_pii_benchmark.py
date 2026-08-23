import json
from collections import Counter
from pathlib import Path

import pytest

from groundguard.domain.pii import detect_pii


ROOT = Path(__file__).resolve().parents[1]

BENCHMARK_PATH = (
    ROOT
    / "benchmark"
    / "safety"
    / "pii_examples.json"
)


def load_records():
    with BENCHMARK_PATH.open(
        encoding="utf-8",
    ) as file:
        return json.load(file)


def test_pii_benchmark_exists():
    assert BENCHMARK_PATH.exists()


def test_pii_benchmark_has_expected_size():
    records = load_records()

    assert len(records) == 20


def test_pii_benchmark_ids_are_unique():
    records = load_records()

    ids = [
        record["id"]
        for record in records
    ]

    assert len(ids) == len(set(ids))


def test_pii_benchmark_has_required_fields():
    records = load_records()

    for record in records:
        assert set(record) == {
            "id",
            "text",
            "expected_detected",
            "expected_categories",
        }

        assert isinstance(
            record["text"],
            str,
        )

        assert isinstance(
            record["expected_detected"],
            bool,
        )

        assert isinstance(
            record["expected_categories"],
            list,
        )


def test_pii_benchmark():
    records = load_records()

    true_positive = 0
    true_negative = 0
    false_positive = 0
    false_negative = 0

    category_correct = 0
    category_total = 0

    for record in records:
        result = detect_pii(
            record["text"],
        )

        expected = record[
            "expected_detected"
        ]

        if result.detected and expected:
            true_positive += 1

        elif not result.detected and not expected:
            true_negative += 1

        elif result.detected and not expected:
            false_positive += 1

        else:
            false_negative += 1

        expected_categories = set(
            record["expected_categories"]
        )

        predicted_categories = set(
            result.categories
        )

        category_correct += len(
            expected_categories
            & predicted_categories
        )

        category_total += len(
            expected_categories
        )

    total_positive = (
        true_positive + false_negative
    )

    predicted_positive = (
        true_positive + false_positive
    )

    precision = (
        true_positive / predicted_positive
        if predicted_positive
        else 0.0
    )

    recall = (
        true_positive / total_positive
        if total_positive
        else 0.0
    )

    print("\n=== Sprint 7 PII Benchmark ===")
    print(f"Records: {len(records)}")
    print(f"True positives: {true_positive}")
    print(f"True negatives: {true_negative}")
    print(f"False positives: {false_positive}")
    print(f"False negatives: {false_negative}")
    print(f"Precision: {precision:.2%}")
    print(f"Recall: {recall:.2%}")

    print("\nExpected categories:")
    print(
        Counter(
            category
            for record in records
            for category in record[
                "expected_categories"
            ]
        )
    )

    print("\nPredicted categories:")
    print(
        Counter(
            category
            for record in records
            for category in detect_pii(
                record["text"]
            ).categories
        )
    )

    assert true_positive + false_negative > 0
    assert true_negative > 0

    assert precision >= 0.80
    assert recall >= 0.80


def test_pii_category_predictions_are_valid():
    records = load_records()

    valid_categories = {
        "EMAIL",
        "PHONE",
        "IP_ADDRESS",
        "CREDIT_CARD",
    }

    for record in records:
        result = detect_pii(
            record["text"],
        )

        assert set(
            result.categories
        ).issubset(valid_categories)


@pytest.mark.parametrize(
    "text",
    [
        "GroundGuard is an evaluation system.",
        "The benchmark contains 250 records.",
        "Accuracy improved from 70% to 80%.",
        "The model returned a reliable answer.",
    ],
)
def test_common_non_pii_text_has_no_false_positive(
    text,
):
    result = detect_pii(text)

    assert result.detected is False