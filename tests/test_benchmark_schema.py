import json
from pathlib import Path


def test_benchmark_schema_is_valid_json():
    schema_path = Path("benchmark/schema.json")

    with schema_path.open(encoding="utf-8") as file:
        schema = json.load(file)

    assert schema["title"] == "GroundGuard Benchmark Example"
    assert schema["type"] == "object"

    required = set(schema["required"])

    assert {
        "id",
        "question",
        "context",
        "answer",
        "grounding_label",
        "relevance_label",
        "contradiction_label",
        "evidence",
        "source",
    }.issubset(required)