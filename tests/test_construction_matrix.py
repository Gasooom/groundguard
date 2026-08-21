import json
from pathlib import Path


MATRIX_PATH = Path("benchmark/construction_matrix.json")


def test_construction_matrix_is_valid():
    with MATRIX_PATH.open(encoding="utf-8") as file:
        matrix = json.load(file)

    assert matrix["benchmark"] == "GroundGuard V1"
    assert matrix["version"] == "1.0.0"

    record_range = matrix["record_range"]

    assert record_range["start"] == 21
    assert record_range["end"] == 250
    assert record_range["count"] == 230

    source_targets = matrix["source_targets"]

    assert source_targets["synthetic"] == 115
    assert source_targets["public_text"] == 115
    assert sum(source_targets.values()) == 230

    batches = matrix["construction_batches"]

    assert len(batches) == 5

    expected_start = 21

    for batch in batches:
        assert batch["record_start"] == expected_start

        expected_count = (
            batch["record_end"]
            - batch["record_start"]
            + 1
        )

        assert batch["count"] == expected_count

        source_total = (
            batch["source_distribution"]["synthetic"]
            + batch["source_distribution"]["public_text"]
        )

        assert source_total == batch["count"]

        grounding_total = sum(
            batch["grounding_distribution"].values()
        )

        assert grounding_total == batch["count"]

        expected_start = batch["record_end"] + 1

    assert expected_start == 251


def test_grounding_targets_match_matrix():
    with MATRIX_PATH.open(encoding="utf-8") as file:
        matrix = json.load(file)

    totals = {
        "SUPPORTED": 0,
        "PARTIALLY_SUPPORTED": 0,
        "UNSUPPORTED": 0,
    }

    for batch in matrix["construction_batches"]:
        for label, count in batch["grounding_distribution"].items():
            totals[label] += count

    assert totals == matrix["grounding_targets"]


def test_source_targets_match_matrix():
    with MATRIX_PATH.open(encoding="utf-8") as file:
        matrix = json.load(file)

    totals = {
        "synthetic": 0,
        "public_text": 0,
    }

    for batch in matrix["construction_batches"]:
        for source, count in batch["source_distribution"].items():
            totals[source] += count

    assert totals == matrix["source_targets"]


def test_quality_constraints_are_enabled():
    with MATRIX_PATH.open(encoding="utf-8") as file:
        matrix = json.load(file)

    constraints = matrix["quality_constraints"]

    assert constraints["unique_ids"] is True
    assert constraints["sequential_ids"] is True
    assert constraints["schema_valid"] is True
    assert constraints["no_empty_required_fields"] is True
    assert constraints["supported_claims_require_evidence"] is True
    assert constraints["contradictory_claims_require_evidence"] is True
    assert (
        constraints[
            "unsupported_does_not_automatically_mean_contradictory"
        ]
        is True
    )
    assert constraints["grounding_is_independent_of_relevance"] is True
    assert constraints["relevance_is_independent_of_contradiction"] is True
    assert constraints["coverage_categories_may_overlap"] is True