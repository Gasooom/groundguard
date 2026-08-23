import json
from collections import Counter
from pathlib import Path

from groundguard.domain.prompt_injection import (
    detect_prompt_injection,
)


ROOT = Path(__file__).resolve().parents[1]

BENCHMARK_PATH = (
    ROOT
    / "benchmark"
    / "safety"
    / "prompt_injection_examples.json"
)


def load_records():
    with BENCHMARK_PATH.open(
        encoding="utf-8",
    ) as file:
        return json.load(file)


def test_prompt_injection_benchmark_exists():
    assert BENCHMARK_PATH.exists()


def test_prompt_injection_benchmark_has_expected_size():
    records = load_records()

    assert len(records) == 16


def test_prompt_injection_ids_are_unique():
    records = load_records()

    ids = [
        record["id"]
        for record in records
    ]

    assert len(ids) == len(set(ids))


def test_prompt_injection_benchmark_has_required_fields():
    records = load_records()

    for record in records:
        assert set(record) == {
            "id",
            "text",
            "expected_detected",
            "expected_categories",
        }

        assert isinstance(record["text"], str)
        assert isinstance(record["expected_detected"], bool)
        assert isinstance(record["expected_categories"], list)


def test_prompt_injection_benchmark():
    records = load_records()

    true_positive = 0
    true_negative = 0
    false_positive = 0
    false_negative = 0

    for record in records:
        result = detect_prompt_injection(
            record["text"],
        )

        expected = record["expected_detected"]

        if result.detected and expected:
            true_positive += 1

        elif not result.detected and not expected:
            true_negative += 1

        elif result.detected and not expected:
            false_positive += 1

        else:
            false_negative += 1

    precision = (
        true_positive
        / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )

    recall = (
        true_positive
        / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0
    )

    print("\n=== Sprint 7 Prompt Injection Benchmark ===")
    print(f"Records: {len(records)}")
    print(f"True positives: {true_positive}")
    print(f"True negatives: {true_negative}")
    print(f"False positives: {false_positive}")
    print(f"False negatives: {false_negative}")
    print(f"Precision: {precision:.2%}")
    print(f"Recall: {recall:.2%}")

    assert true_positive + false_negative > 0
    assert true_negative > 0

    assert precision >= 0.80
    assert recall >= 0.80


def test_prompt_injection_categories_are_valid():
    records = load_records()

    valid_categories = {
        "IGNORE_INSTRUCTIONS",
        "SYSTEM_OVERRIDE",
        "ROLE_HIJACKING",
        "PROMPT_EXTRACTION",
    }

    for record in records:
        result = detect_prompt_injection(
            record["text"],
        )

        assert set(
            result.categories
        ).issubset(valid_categories)


def test_expected_categories_are_detected():
    records = load_records()

    for record in records:
        result = detect_prompt_injection(
            record["text"],
        )

        expected_categories = set(
            record["expected_categories"]
        )

        predicted_categories = set(
            result.categories
        )

        assert expected_categories.issubset(
            predicted_categories
        )


def test_clean_examples_have_no_detection():
    records = load_records()

    clean_records = [
        record
        for record in records
        if not record["expected_detected"]
    ]

    assert clean_records

    for record in clean_records:
        result = detect_prompt_injection(
            record["text"],
        )

        assert result.detected is False
        assert result.categories == ()
        assert result.evidence == ()


def test_category_distribution():
    records = load_records()

    expected = Counter(
        category
        for record in records
        for category in record["expected_categories"]
    )

    assert expected["IGNORE_INSTRUCTIONS"] >= 3
    assert expected["SYSTEM_OVERRIDE"] >= 2
    assert expected["ROLE_HIJACKING"] >= 2
    assert expected["PROMPT_EXTRACTION"] >= 3