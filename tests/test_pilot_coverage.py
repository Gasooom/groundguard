import json
from collections import Counter
from pathlib import Path


BENCHMARK_PATH = Path(
    "benchmark/examples/human_labeled_001_020.json"
)


def test_pilot_has_required_label_coverage():
    with BENCHMARK_PATH.open(encoding="utf-8") as file:
        records = json.load(file)

    grounding = Counter(
        record["grounding_label"]
        for record in records
    )

    relevance = Counter(
        record["relevance_label"]
        for record in records
    )

    contradiction = Counter(
        record["contradiction_label"]
        for record in records
    )

    assert grounding["SUPPORTED"] >= 5
    assert grounding["PARTIALLY_SUPPORTED"] >= 2
    assert grounding["UNSUPPORTED"] >= 5

    assert relevance["RELEVANT"] >= 10
    assert relevance["IRRELEVANT"] >= 1

    assert contradiction["CONTRADICTORY"] >= 3
    assert contradiction["NOT_CONTRADICTORY"] >= 10