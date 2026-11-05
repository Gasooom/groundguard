import json

import pytest

from groundguard.annotate import review, status
from groundguard.bench.claims_dataset import AI_DRAFTER, read_records, write_records
from groundguard.bench.errors import DatasetError
from groundguard.cli import main
from tests.test_claims_dataset import record


def scripted(*answers):
    iterator = iter(answers)
    return lambda prompt: next(iterator)


def _raw(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_accepting_without_changes_marks_labeled_and_keeps_construction_basis(tmp_path):
    path = tmp_path / "records.jsonl"
    write_records(path, [record("a")])

    outcomes = review(path, "gasim", input_fn=scripted("", "", "", "a"), output=lambda line: None)

    (raw,) = _raw(path)
    assert outcomes == {"LABELED": 1}
    assert raw["annotation"]["status"] == "LABELED"
    assert raw["annotation"]["reviewed_by"] == "gasim"
    assert raw["annotation"]["label_basis"] == "construction"
    assert "no changes" in raw["annotation"]["notes"]
    assert read_records(path)[0].status == "LABELED"


def test_changing_a_label_records_the_change_and_marks_judgment(tmp_path):
    path = tmp_path / "records.jsonl"
    write_records(path, [record("a")])

    review(path, "gasim", input_fn=scripted("n", "", "i", "a"), output=lambda line: None)

    (raw,) = _raw(path)
    assert raw["claims"][0]["label"] == "NOT_ENOUGH_INFO"
    assert raw["completeness"] == "INCOMPLETE"
    assert raw["annotation"]["label_basis"] == "judgment"
    assert "c1 CONTRADICTED -> NOT_ENOUGH_INFO" in raw["annotation"]["notes"]
    assert "completeness COMPLETE -> INCOMPLETE" in raw["annotation"]["notes"]


def test_excluding_requires_a_reason(tmp_path):
    path = tmp_path / "records.jsonl"
    write_records(path, [record("a")])
    review(path, "gasim", input_fn=scripted("", "", "", "x", "", "ambiguous source"), output=lambda line: None)
    (raw,) = _raw(path)
    assert raw["annotation"]["status"] == "EXCLUDED"
    assert raw["annotation"]["notes"].endswith("ambiguous source")


def test_editing_evidence_must_be_an_exact_quote(tmp_path):
    path = tmp_path / "records.jsonl"
    write_records(path, [record("a")])
    lines = []
    review(
        path,
        "gasim",
        input_fn=scripted("e", "s1", "approved for teens", "", "", "", "a"),
        output=lines.append,
    )
    assert any("not an exact substring" in line for line in lines)
    (raw,) = _raw(path)
    assert raw["claims"][0]["evidence"][0]["quote"] == "It is not approved for children under 12."

    write_records(path, [record("b")])
    review(path, "gasim", input_fn=scripted("e", "s1", "Drug Q is approved for adults.", "", "", "", "a"), output=lambda line: None)
    (raw,) = _raw(path)
    assert raw["claims"][0]["evidence"] == [{"source_id": "s1", "quote": "Drug Q is approved for adults."}]


def test_quitting_saves_previous_records_only(tmp_path):
    path = tmp_path / "records.jsonl"
    write_records(path, [record("a"), record("b")])
    review(path, "gasim", input_fn=scripted("", "", "", "a", "q"), output=lambda line: None)
    statuses = [raw["annotation"]["status"] for raw in _raw(path)]
    assert statuses == ["LABELED", "NEEDS_REVIEW"]


def test_invalid_change_is_not_saved(tmp_path):
    # Changing a NOT_ENOUGH_INFO claim without evidence to SUPPORTED fails validation.
    raw = record("a")
    raw["claims"][0]["label"] = "NOT_ENOUGH_INFO"
    raw["claims"][0]["evidence"] = []
    path = tmp_path / "records.jsonl"
    write_records(path, [raw])
    outcomes = review(path, "gasim", input_fn=scripted("s", "", "", "a"), output=lambda line: None)
    assert outcomes == {"invalid": 1}
    assert _raw(path)[0]["annotation"]["status"] == "NEEDS_REVIEW"


def test_ai_cannot_review(tmp_path):
    path = tmp_path / "records.jsonl"
    write_records(path, [record("a")])
    with pytest.raises(DatasetError, match="person"):
        review(path, AI_DRAFTER, input_fn=scripted(), output=lambda line: None)


def test_status_and_cli(tmp_path, capsys):
    path = tmp_path / "records.jsonl"
    write_records(path, [record("a"), record("b", status="LABELED")])
    summary = status(path)
    assert summary["by_status"] == {"NEEDS_REVIEW": 1, "LABELED": 1}
    assert summary["claim_labels"] == {"CONTRADICTED": 2}

    assert main(["annotate", "status", str(path)]) == 0
    assert '"records": 2' in capsys.readouterr().out
    assert main(["annotate", "freeze", str(path), "--version", "1.0.0"]) == 2  # unreviewed record
