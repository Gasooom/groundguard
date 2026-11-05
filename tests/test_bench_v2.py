import pytest

from groundguard.bench import run_benchmark
from groundguard.cli import main
from groundguard.pipeline import PipelineConfig


def test_v2_requires_the_production_input_mode():
    with pytest.raises(ValueError, match="only supports input_mode 'context'"):
        run_benchmark("gg-legacy-v1", input_mode="oracle", engine="v2")


def test_pipeline_config_only_applies_to_v2():
    with pytest.raises(ValueError, match="only apply to engine v2"):
        run_benchmark("gg-legacy-v1", input_mode="context", engine="v1", pipeline_config=PipelineConfig())


def test_v2_run_records_engine_and_pipeline_config():
    run = run_benchmark(
        "gg-legacy-v1",
        input_mode="context",
        engine="v2",
        pipeline_config=PipelineConfig(granularity="sentence"),
    )
    config = run["manifest"]["config"]
    assert run["manifest"]["engine"] == "v2"
    assert config["engine"] == "v2"
    assert config["pipeline"]["granularity"] == "sentence"
    assert {p["system_decision"] for p in run["predictions"]} <= {"ACCEPT", "FLAG", "REJECT"}


def test_cli_rejects_pipeline_options_for_v1(capsys):
    code = main(["bench", "run", "--dataset", "gg-legacy-v1", "--input-mode", "context", "--granularity", "sentence"])
    assert code == 2
    assert "only apply to --engine v2" in capsys.readouterr().err


RESULTS = __import__("pathlib").Path(__file__).resolve().parents[1] / "benchmark" / "results"


@pytest.mark.parametrize("granularity", ["sentence", "clause", "conjunct"])
def test_v2_engine_reproduces_committed_m2_results(granularity):
    from groundguard.bench import read_run

    from groundguard.policy import load_builtin

    committed = read_run(RESULTS / f"v2-m2.{granularity}.context.json")
    run = run_benchmark(
        "gg-legacy-v1",
        input_mode="context",
        engine="v2",
        pipeline_config=PipelineConfig(granularity=granularity),
        policy=load_builtin("provisional-m2"),
    )
    # The M2 decisions now come from the provisional-m2 policy. Until the run
    # files are regenerated with the policy recorded in their config, compare
    # the pipeline config, predictions and metrics exactly.
    assert run["manifest"]["config"]["pipeline"] == committed["manifest"]["config"]["pipeline"]
    assert run["manifest"]["config"]["policy"]["id"] == "provisional-m2"
    assert run["predictions_hash"] == committed["predictions_hash"]
    assert run["metrics"] == committed["metrics"]
