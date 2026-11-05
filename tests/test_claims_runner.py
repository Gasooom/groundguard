import json

import pytest

from groundguard.bench.claims_dataset import freeze, write_records
from groundguard.bench.claims_runner import run_claims_benchmark
from groundguard.bench.errors import DatasetError
from groundguard.cli import main
from tests.test_claims_dataset import record


# No pronouns on purpose: this fixture tests the runner's metrics. Pronoun
# subjects are a known engine limitation (probes coref_01, coref_02).
SOURCE = "Fictional Drug Q is approved for adults. Drug Q is not approved for children under 12. Drug Q is taken once daily."


def _record(record_id, group, answer, claim_text, label, quote, phenomena, status="LABELED"):
    start = answer.index(claim_text)
    raw = record(record_id, group=group, status=status)
    raw["sources"][0]["text"] = SOURCE
    raw["answer"] = answer
    raw["answer_origin"] = "ai_drafted"
    raw["perturbation"] = None
    raw["claims"] = [
        {
            "id": "c1",
            "text": claim_text,
            "answer_span": [start, start + len(claim_text)],
            "label": label,
            "evidence": [] if quote is None else [{"source_id": "s1", "quote": quote}],
            "phenomena": phenomena,
        }
    ]
    return raw


ROWS = [
    # negation: gold CONTRADICTED, engine finds it via the guards
    ("neg", "g1", "Drug Q is approved for children under 12.", "Drug Q is approved for children under 12",
     "CONTRADICTED", "Drug Q is not approved for children under 12.", ["negation"]),
    # supported
    ("sup", "g2", "Drug Q is taken once daily.", "Drug Q is taken once daily",
     "SUPPORTED", "Drug Q is taken once daily.", ["none"]),
    # not enough info
    ("nei", "g3", "Drug Q is sold in 40 countries.", "Drug Q is sold in 40 countries",
     "NOT_ENOUGH_INFO", None, ["none"]),
]


@pytest.fixture
def records_path(tmp_path):
    path = tmp_path / "records.jsonl"
    write_records(path, [_record(*row) for row in ROWS])
    return path


def test_unreviewed_run_on_hand_checked_fixture(records_path):
    run = run_claims_benchmark(records_path, split="unreviewed", dataset_id="fixture")

    assert run["manifest"]["config"]["label_status"] == "unreviewed"
    claim = run["metrics"]["all"]["claim_level"]
    assert (claim["accuracy"]["numerator"], claim["accuracy"]["denominator"]) == (3, 3)
    assert claim["confusion_matrix"]["CONTRADICTED"]["CONTRADICTED"] == 1
    # neg and sup are localizable; both cite the annotator's quote
    assert (claim["evidence_localization"]["numerator"], claim["evidence_localization"]["denominator"]) == (2, 2)
    assert claim["by_phenomenon"]["negation"]["contradicted_recall"]["numerator"] == 1

    answer = run["metrics"]["all"]["answer_level"]
    # only 'sup' is a good answer; it is accepted; the other two are rejected
    assert answer["distribution"]["ACCEPT"] == 1
    assert (answer["false_accept"]["numerator"], answer["false_accept"]["denominator"]) == (0, 2)
    assert (answer["false_reject"]["numerator"], answer["false_reject"]["denominator"]) == (0, 1)
    assert [p["decision"] for p in run["predictions"]] == ["REJECT", "ACCEPT", "REJECT"]
    assert "domain=health" in run["metrics"]


def test_runs_are_deterministic(records_path):
    first = run_claims_benchmark(records_path, split="unreviewed", dataset_id="fixture")
    second = run_claims_benchmark(records_path, split="unreviewed", dataset_id="fixture")
    assert first["predictions_hash"] == second["predictions_hash"]
    assert first["metrics"] == second["metrics"]


def test_reviewed_splits_need_a_frozen_dataset(records_path):
    with pytest.raises(DatasetError, match="not frozen"):
        run_claims_benchmark(records_path, split="dev", dataset_id="fixture")


def test_test_split_requires_purpose_and_is_logged(records_path, tmp_path):
    freeze(records_path, version="0.0.1-test")
    log = tmp_path / "TEST_ACCESS_LOG.jsonl"
    with pytest.raises(DatasetError, match="needs --purpose"):
        run_claims_benchmark(records_path, split="test", dataset_id="fixture", test_access_log=log)

    splits = json.loads((records_path.parent / "splits.json").read_text())
    if not splits["splits"]["test"]:
        pytest.fail("fixture groups should put at least one record in test")  # pragma: no cover
    run = run_claims_benchmark(
        records_path, split="test", dataset_id="fixture", purpose="unit test", test_access_log=log
    )
    assert run["manifest"]["dataset"]["version"] == "0.0.1-test"
    (entry,) = [json.loads(line) for line in log.read_text().splitlines()]
    assert entry["purpose"] == "unit test"
    assert entry["run_id"] == run["predictions_hash"][:16]


def test_cli_warns_on_unreviewed_runs(records_path, capsys, tmp_path):
    out = tmp_path / "run.json"
    assert main(["bench", "claims", "--records", str(records_path), "--split", "unreviewed", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "unreviewed labels" in printed
    assert json.loads(out.read_text())["kind"] == "claims"
