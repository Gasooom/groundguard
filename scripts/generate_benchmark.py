import json
from pathlib import Path

from jsonschema import validate


SCHEMA_PATH = Path("benchmark/schema.json")
OUTPUT_PATH = Path("benchmark/examples/generated_examples.json")


def load_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def build_examples() -> list[dict]:
    return [
        {
            "id": "synthetic_001",
            "question": "When was the company founded?",
            "context": "The company was founded in 2018.",
            "answer": "The company was founded in 2018.",
            "grounding_label": "SUPPORTED",
            "relevance_label": "RELEVANT",
            "contradiction_label": "NOT_CONTRADICTORY",
            "evidence": [
                "The company was founded in 2018."
            ],
            "source": "synthetic",
            "annotator_id": "synthetic_generator",
            "annotation_status": "LABELED",
            "annotation_notes": ""
        },
        {
            "id": "synthetic_002",
            "question": "When was the company founded?",
            "context": "The company was founded in 2018.",
            "answer": "The company was founded in 2015.",
            "grounding_label": "UNSUPPORTED",
            "relevance_label": "RELEVANT",
            "contradiction_label": "CONTRADICTORY",
            "evidence": [
                "The company was founded in 2018."
            ],
            "source": "synthetic",
            "annotator_id": "synthetic_generator",
            "annotation_status": "LABELED",
            "annotation_notes": ""
        }
    ]


def validate_examples(examples: list[dict], schema: dict) -> None:
    for example in examples:
        validate(instance=example, schema=schema)


def main() -> None:
    schema = load_schema()
    examples = build_examples()

    validate_examples(examples, schema)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            examples,
            file,
            indent=2,
            ensure_ascii=False
        )
        file.write("\n")

    print(f"Validated and generated {len(examples)} examples.")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()