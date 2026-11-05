"""Regression gate: the v1 engine must reproduce the committed baselines.

The deterministic v1 engine has to produce the committed predictions and
metrics exactly. If a change is *meant* to alter results, regenerate the
baseline from a clean tree with ``groundguard bench run ... --out`` and
explain the change in the commit. Do not loosen this test.
"""

import copy
import json
from pathlib import Path

import pytest

from groundguard.bench import read_run, run_benchmark, write_run
from groundguard.bench.compare import compare_runs, parse_tolerances
from groundguard.bench.errors import RunFileError
from groundguard.cli import main


RESULTS = Path(__file__).resolve().parents[1] / "benchmark" / "results"
MODES = ("context", "oracle", "oracle_no_question")


@pytest.fixture(scope="module")
def runs():
    return {mode: run_benchmark("gg-legacy-v1", input_mode=mode) for mode in MODES}


@pytest.mark.parametrize("mode", MODES)
def test_v1_engine_reproduces_committed_baseline(runs, mode):
    baseline = read_run(RESULTS / f"v0.1.0-baseline.{mode}.json")
    run = runs[mode]

    assert run["manifest"]["dataset"]["sha256"] == baseline["manifest"]["dataset"]["sha256"]
    assert run["manifest"]["config"] == baseline["manifest"]["config"]
    assert run["predictions_hash"] == baseline["predictions_hash"]
    assert run["predictions"] == baseline["predictions"]
    assert run["metrics"] == baseline["metrics"]


def test_headline_numbers_are_the_documented_ones(runs):
    def counts(mode, view, dimension):
        rate = runs[mode]["metrics"][view][dimension]["accuracy"]
        return rate["numerator"], rate["denominator"]

    assert counts("context", "all", "grounding") == (161, 250)
    assert counts("context", "all", "relevance") == (243, 250)
    assert counts("context", "all", "contradiction") == (245, 250)
    assert counts("oracle", "all", "contradiction") == (248, 250)

    assert counts("context", "dedup", "grounding") == (59, 99)
    assert counts("context", "dedup", "contradiction") == (94, 99)

    far = runs["context"]["metrics"]["all"]["decision"]["false_accept"]
    frr = runs["context"]["metrics"]["all"]["decision"]["false_reject"]
    assert (far["numerator"], far["denominator"]) == (8, 168)
    assert (frr["numerator"], frr["denominator"]) == (50, 82)


def test_runs_are_deterministic():
    first = run_benchmark("gg-legacy-v1", input_mode="context")
    second = run_benchmark("gg-legacy-v1", input_mode="context")
    assert first["predictions_hash"] == second["predictions_hash"]
    assert first["metrics"] == second["metrics"]


def test_compare_identical_runs_has_no_regressions(runs):
    comparison = compare_runs(runs["context"], runs["context"])
    assert comparison.comparable
    assert comparison.regressions == ()
    assert comparison.flips == ()


def _worsen_far(run):
    candidate = copy.deepcopy(run)
    far = candidate["metrics"]["all"]["decision"]["false_accept"]
    far["value"] = far["value"] + 0.05
    first = candidate["predictions"][0]
    first["system_decision"] = "REJECT" if first["system_decision"] == "ACCEPT" else "ACCEPT"
    return candidate


def test_compare_detects_regression_and_flips(runs):
    baseline = runs["context"]
    candidate = _worsen_far(baseline)

    comparison = compare_runs(baseline, candidate)
    regressed = {(delta.view, delta.metric) for delta in comparison.regressions}
    assert regressed == {("all", "decision.false_accept")}

    tolerant = compare_runs(
        baseline,
        candidate,
        tolerances=parse_tolerances(["decision.false_accept=0.1"]),
    )
    assert tolerant.regressions == ()

    assert [(flip.id, flip.field) for flip in comparison.flips] == [
        (baseline["predictions"][0]["id"], "system_decision")
    ]


def test_compare_flags_different_datasets_as_not_comparable(runs):
    other = copy.deepcopy(runs["context"])
    other["manifest"]["dataset"]["version"] = "9.9.9"
    assert not compare_runs(runs["context"], other).comparable


def test_parse_tolerances_rejects_bad_specs():
    with pytest.raises(ValueError):
        parse_tolerances(["unknown.metric=0.1"])
    with pytest.raises(ValueError):
        parse_tolerances(["decision.false_accept"])
    with pytest.raises(ValueError):
        parse_tolerances(["decision.false_accept=-1"])


def test_cli_exit_codes(runs, tmp_path, capsys):
    base_path = tmp_path / "base.json"
    worse_path = tmp_path / "worse.json"
    write_run(runs["context"], base_path)
    write_run(_worsen_far(runs["context"]), worse_path)

    assert main(["bench", "compare", str(base_path), str(base_path), "--fail-on-regression"]) == 0
    assert main(["bench", "compare", str(base_path), str(worse_path), "--fail-on-regression"]) == 1
    assert main(["bench", "compare", str(base_path), str(worse_path)]) == 0
    assert main(["bench", "compare", str(base_path), str(tmp_path / "missing.json")]) == 2
    capsys.readouterr()


def test_read_run_rejects_malformed_files(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(RunFileError):
        read_run(bad)

    wrong_version = tmp_path / "wrong.json"
    wrong_version.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")
    with pytest.raises(RunFileError):
        read_run(wrong_version)
