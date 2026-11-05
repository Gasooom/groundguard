import copy
import json

import pytest

from groundguard.bench.claims_dataset import (
    AI_DRAFTER,
    assign_split,
    freeze,
    load_split,
    log_test_access,
    parse_record,
    read_records,
    write_records,
)
from groundguard.bench.errors import DatasetError


SOURCE = "Fictional Drug Q is approved for adults. It is not approved for children under 12."
ANSWER = "Drug Q is approved for children under 12."


def record(record_id="r1", group="g1", status="NEEDS_REVIEW", **overrides):
    raw = {
        "schema_version": 1,
        "id": record_id,
        "context_group": group,
        "domain": "health",
        "question": "Who is Drug Q approved for?",
        "sources": [
            {
                "id": "s1",
                "text": SOURCE,
                "url": "https://example.org/drug-q",
                "publisher": "Example Agency",
                "title": "Drug Q",
                "retrieved_at": "2026-11-05",
                "license": "test fixture",
            }
        ],
        "answer": ANSWER,
        "answer_origin": "perturbation",
        "perturbation": {"type": "negation", "note": "dropped 'not'"},
        "claims": [
            {
                "id": "c1",
                "text": ANSWER.rstrip("."),
                "answer_span": [0, len(ANSWER) - 1],
                "label": "CONTRADICTED",
                "evidence": [{"source_id": "s1", "quote": "It is not approved for children under 12."}],
                "phenomena": ["negation"],
            }
        ],
        "relevance": "RELEVANT",
        "completeness": "COMPLETE",
        "annotation": {
            "status": status,
            "drafted_by": AI_DRAFTER,
            "label_basis": "construction",
            "reviewed_by": "gasim" if status == "LABELED" else None,
            "reviewed_at": "2026-11-06" if status == "LABELED" else None,
            "notes": "",
            "uncertain": False,
        },
    }
    raw.update(overrides)
    return raw


def test_valid_record_parses():
    parsed = parse_record(record())
    assert parsed.id == "r1"
    assert parsed.claims[0].label == "CONTRADICTED"
    assert parsed.claims[0].evidence[0].quote in SOURCE
    assert parsed.is_good is False


def _mutated(path, value):
    raw = record()
    target = raw
    for key in path[:-1]:
        target = target[key]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return raw


@pytest.mark.parametrize(
    "path, value, message",
    [
        (("domain",), "law", "not in"),
        (("answer",), "  ", "non-empty"),
        (("schema_version",), 2, "schema_version"),
        (("extra",), "x", "unknown keys"),
        (("sources",), [], "non-empty list"),
        (("claims", 0, "label"), "MAYBE", "not in"),
        (("claims", 0, "answer_span"), [0, 999], "inside the answer"),
        (("claims", 0, "answer_span"), [5, 5], "inside the answer"),
        (("claims", 0, "evidence"), [], "need at least one evidence quote"),
        (("claims", 0, "evidence", 0, "quote"), "approved for teenagers", "not an exact substring"),
        (("claims", 0, "evidence", 0, "source_id"), "s9", "unknown source"),
        (("claims", 0, "phenomena"), ["vibes"], "not in"),
        (("answer_origin",), "imagined", "not in"),
        (("perturbation",), None, "describe the perturbation"),
        (("annotation", "status"), "DONE", "not in"),
        (("annotation", "uncertain"), "no", "true or false"),
        (("annotation", "label_basis"), "guess", "not in"),
    ],
)
def test_invalid_records_are_rejected(path, value, message):
    with pytest.raises(DatasetError, match=message):
        parse_record(_mutated(path, value))


def test_labeled_records_need_a_human_reviewer():
    with pytest.raises(DatasetError, match="reviewed_by"):
        parse_record(record(status="LABELED", annotation={**record()["annotation"], "status": "LABELED"}))
    raw = record(status="LABELED")
    raw["annotation"]["reviewed_by"] = AI_DRAFTER
    with pytest.raises(DatasetError, match="reviews must be by a person"):
        parse_record(raw)
    assert parse_record(record(status="LABELED")).status == "LABELED"


def test_round_trip_and_duplicate_ids(tmp_path):
    path = tmp_path / "records.jsonl"
    write_records(path, [record("a"), record("b")])
    assert [r.id for r in read_records(path)] == ["a", "b"]

    write_records(path, [record("a"), record("a")])
    with pytest.raises(DatasetError, match="duplicate record ids"):
        read_records(path)

    path.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="invalid JSON"):
        read_records(path)


def test_split_assignment_is_by_group_and_deterministic():
    assert assign_split("g1") == assign_split("g1")
    groups = [f"group-{i}" for i in range(400)]
    test_share = sum(assign_split(g) == "test" for g in groups) / len(groups)
    assert 0.3 < test_share < 0.5


def test_freeze_refuses_unreviewed_records(tmp_path):
    path = tmp_path / "records.jsonl"
    write_records(path, [record("a", status="LABELED"), record("b", status="NEEDS_REVIEW")])
    with pytest.raises(DatasetError, match="not reviewed yet"):
        freeze(path, version="1.0.0")


def test_freeze_and_load_split(tmp_path):
    path = tmp_path / "records.jsonl"
    rows = [record(f"r{i}", group=f"g{i // 2}", status="LABELED") for i in range(20)]
    rows.append(record("x", group="gx", status="EXCLUDED"))
    write_records(path, rows)

    manifest = freeze(path, version="1.0.0")
    assert manifest["counts"]["dev"] + manifest["counts"]["test"] == 20
    assert manifest["excluded"] == ["x"]
    dev, test = load_split(path, "dev"), load_split(path, "test")
    assert {r.context_group for r in dev}.isdisjoint({r.context_group for r in test})
    assert len(load_split(path, "all")) == 20

    # Editing records after freezing invalidates the split.
    write_records(path, rows[:-1])
    with pytest.raises(DatasetError, match="changed after freezing"):
        load_split(path, "test")


def test_load_split_requires_freeze(tmp_path):
    path = tmp_path / "records.jsonl"
    write_records(path, [record("a", status="LABELED")])
    with pytest.raises(DatasetError, match="not frozen"):
        load_split(path, "dev")


def test_test_access_log_appends_and_requires_purpose(tmp_path):
    log = tmp_path / "TEST_ACCESS_LOG.jsonl"
    log_test_access(log, dataset="gg-claims-v2", version="1.0.0", purpose="M4 report", run_id="r1")
    log_test_access(log, dataset="gg-claims-v2", version="1.0.0", purpose="M5 report", run_id="r2")
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["purpose"] for e in entries] == ["M4 report", "M5 report"]
    with pytest.raises(DatasetError, match="stated purpose"):
        log_test_access(log, dataset="d", version="v", purpose=" ", run_id="r3")


def test_parse_record_does_not_mutate_input():
    raw = record()
    before = copy.deepcopy(raw)
    parse_record(raw)
    assert raw == before
