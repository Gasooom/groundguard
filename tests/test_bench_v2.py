import pytest

from groundguard.bench import run_benchmark
from groundguard.cli import main
from groundguard.pipeline import PipelineConfig


def test_v2_requires_the_production_input_mode():
    with pytest.raises(ValueError, match="only supports input_mode 'context'"):
        run_benchmark("gg-legacy-v1", input_mode="oracle", engine="v2")


def test_pipeline_config_only_applies_to_v2():
    with pytest.raises(ValueError, match="only applies to engine v2"):
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
