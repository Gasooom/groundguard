import json
from pathlib import Path

from jsonschema import validate


def test_benchmark_record_matches_schema():
    schema_path = Path("benchmark/schema.json")
    record_path = Path("benchmark/examples/benchmark_001.json")

    with schema_path.open(encoding="utf-8") as file:
        schema = json.load(file)

    with record_path.open(encoding="utf-8") as file:
        record = json.load(file)

    validate(instance=record, schema=schema)