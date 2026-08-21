import json
from pathlib import Path

from jsonschema import validate


def test_generated_examples_match_schema():
    schema_path = Path("benchmark/schema.json")
    examples_path = Path("benchmark/examples/generated_examples.json")

    with schema_path.open(encoding="utf-8") as file:
        schema = json.load(file)

    with examples_path.open(encoding="utf-8") as file:
        examples = json.load(file)

    assert isinstance(examples, list)
    assert len(examples) > 0

    for example in examples:
        validate(instance=example, schema=schema)