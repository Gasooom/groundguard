import copy
import json

import pytest

from groundguard.bench.datasets import (
    LEGACY_V1_FILES,
    BenchmarkRecord,
    _load_schema,
    assign_context_groups,
    deduplicate,
    group_split,
    load_dataset,
    load_legacy_v1,
    validate_record,
)
from groundguard.bench.errors import DatasetError


def _record(record_id, question="Q?", context="Some context.", answer="An answer."):
    return BenchmarkRecord(
        id=record_id,
        question=question,
        context=context,
        answer=answer,
        grounding_label="SUPPORTED",
        relevance_label="RELEVANT",
        contradiction_label="NOT_CONTRADICTORY",
        evidence=(),
        source="synthetic",
        annotation_status="LABELED",
    )


def test_legacy_dataset_shape():
    dataset = load_legacy_v1()

    assert dataset.id == "gg-legacy-v1"
    assert len(dataset) == 250
    assert len({record.id for record in dataset.records}) == 250
    assert len(dataset.files) == len(LEGACY_V1_FILES)
    assert len(dataset.sha256) == 64


def test_legacy_dataset_hash_is_stable():
    assert load_legacy_v1().sha256 == load_legacy_v1().sha256


def test_legacy_dataset_has_99_unique_triples():
    # Documented in docs/GROUNDGUARD_V2.md §5.2: 29 templates repeat 6-7x.
    assert len(deduplicate(load_legacy_v1().records)) == 99


def test_load_dataset_rejects_unknown_id():
    with pytest.raises(DatasetError, match="unknown dataset"):
        load_dataset("does-not-exist")


def test_validate_record_accepts_existing_records():
    schema = _load_schema()
    with LEGACY_V1_FILES[0].open(encoding="utf-8") as file:
        for raw in json.load(file):
            validate_record(raw, schema)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda raw: raw.pop("answer"), "missing required"),
        (lambda raw: raw.update(grounding_label="MOSTLY"), "not in"),
        (lambda raw: raw.update(extra_field="x"), "unknown keys"),
        (lambda raw: raw.update(answer="   "), "non-empty"),
        (lambda raw: raw.update(evidence="not a list"), "list of strings"),
        (lambda raw: raw.update(source="public_text"), "source_metadata"),
    ],
)
def test_validate_record_rejects_malformed_records(mutate, message):
    schema = _load_schema()
    with LEGACY_V1_FILES[0].open(encoding="utf-8") as file:
        raw = copy.deepcopy(json.load(file)[0])
    mutate(raw)
    with pytest.raises(DatasetError, match=message):
        validate_record(raw, schema)


def test_deduplicate_keeps_first_occurrence_in_order():
    records = [_record("a"), _record("b"), _record("c", answer="Other.")]
    assert [record.id for record in deduplicate(records)] == ["a", "c"]


def test_context_groups_merge_exact_and_near_duplicates():
    records = [
        _record("r1", context="Acme was founded in 2018 in Kigali, Rwanda."),
        _record("r2", context="Acme was founded in 2018 in Kigali, Rwanda!"),
        _record("r3", context="Acme was founded in 2018 in Kigali Rwanda"),
        _record("r4", context="The Pacific is the largest ocean on Earth."),
    ]
    groups = assign_context_groups(records)

    assert groups["r1"] == groups["r2"] == groups["r3"] == "r1"
    assert groups["r4"] == "r4"


def test_group_split_is_deterministic_and_never_splits_a_group():
    records = load_legacy_v1().records
    groups = assign_context_groups(records)

    first = group_split(records, groups)
    second = group_split(list(reversed(records)), groups)
    assert first == second

    split_by_group = {}
    for record in records:
        split_by_group.setdefault(groups[record.id], set()).add(first[record.id])
    assert all(len(splits) == 1 for splits in split_by_group.values())
    assert set(first.values()) == {"dev", "test"}


def test_group_split_validates_fraction():
    with pytest.raises(ValueError):
        group_split([], {}, test_fraction=1.0)
