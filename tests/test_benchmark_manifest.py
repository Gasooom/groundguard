import json
from pathlib import Path


MANIFEST_PATH = Path("benchmark/manifest.json")


def test_benchmark_manifest_is_valid():
    with MANIFEST_PATH.open(encoding="utf-8") as file:
        manifest = json.load(file)

    benchmark = manifest["benchmark"]

    assert benchmark["name"] == "GroundGuard V1"
    assert benchmark["target_size"] == 250
    assert benchmark["status"] == "CONSTRUCTION"

    grounding = manifest["construction_targets"]["grounding"]

    assert grounding["SUPPORTED"] == 50
    assert grounding["PARTIALLY_SUPPORTED"] == 35
    assert grounding["UNSUPPORTED"] == 35

    coverage = manifest["construction_targets"]["coverage"]

    assert coverage["RELEVANT_BUT_UNSUPPORTED"] == 25
    assert coverage["IRRELEVANT"] == 25
    assert coverage["MULTI_CLAIM_OR_EDGE_CASE"] == 25
    assert coverage["NUMERICAL_TEMPORAL_OR_PARAPHRASE"] == 20

    sources = manifest["data_sources"]

    assert sources["synthetic"]["target"] == 125
    assert sources["public_text"]["target"] == 125

    assert manifest["construction_rules"]["targets_are_overlapping"] is True
    assert (
        manifest["construction_rules"][
            "grounding_and_relevance_are_independent"
        ]
        is True
    )

    assert manifest["quality_gates"]["schema_validation"] is True
    assert manifest["quality_gates"]["unique_ids"] is True
    assert manifest["quality_gates"]["coverage_validation"] is True
    assert manifest["quality_gates"]["duplicate_detection"] is True