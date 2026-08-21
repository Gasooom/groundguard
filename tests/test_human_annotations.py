import json
from pathlib import Path

from jsonschema import validate


BENCHMARK_PATH = Path(
    "benchmark/examples/human_labeled_001_020.json"
)

SCHEMA_PATH = Path("benchmark/schema.json")


def test_human_labeled_records_are_valid():
    with SCHEMA_PATH.open(encoding="utf-8") as file:
        schema = json.load(file)

    with BENCHMARK_PATH.open(encoding="utf-8") as file:
        records = json.load(file)

    assert isinstance(records, list)
    assert len(records) == 20

    record_ids = [record["id"] for record in records]

    assert len(record_ids) == len(set(record_ids))
    assert record_ids == [
        f"human_{index:03d}"
        for index in range(1, 21)
    ]

    for record in records:
        validate(instance=record, schema=schema)

        assert record["annotation_status"] in {
            "LABELED",
            "NEEDS_REVIEW",
        }

        if record["annotation_status"] == "LABELED":
            assert record["grounding_label"]
            assert record["relevance_label"]
            assert record["contradiction_label"]
            assert record["annotator_id"]

            if record["grounding_label"] == "SUPPORTED":
                assert record["evidence"]

            if record["contradiction_label"] == "CONTRADICTORY":
                assert record["evidence"]