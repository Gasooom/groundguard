"""Reproducible benchmark harness for GroundGuard.

Typical use::

    from groundguard.bench import run_benchmark
    run = run_benchmark("gg-legacy-v1", input_mode="context")
    run["metrics"]["dedup"]["grounding"]["accuracy"]["value"]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from groundguard.bench.datasets import load_dataset
from groundguard.bench.errors import RunFileError
from groundguard.bench.manifest import RUN_FILE_SCHEMA_VERSION, build_manifest
from groundguard.bench.report import build_metrics, predictions_hash
from groundguard.bench.runner import INPUT_MODES, InputMode, run_v1, run_v2
from groundguard.pipeline import ENGINE_VERSION, PipelineConfig
from groundguard.policy import DEFAULT_POLICY, Policy, load_builtin


def run_benchmark(
    dataset_id: str,
    *,
    input_mode: InputMode,
    engine: Literal["v1", "v2"] = "v1",
    pipeline_config: PipelineConfig | None = None,
    policy: Policy | None = None,
) -> dict[str, Any]:
    """Run an engine over a dataset and return a self-describing run.

    v2 only supports the ``context`` input mode: it evaluates against the
    sources the caller supplies, which is the production path.
    """

    if input_mode not in INPUT_MODES:
        raise ValueError(f"unknown input_mode {input_mode!r}")

    dataset = load_dataset(dataset_id)
    config: dict[str, Any]
    if engine == "v1":
        if pipeline_config is not None or policy is not None:
            raise ValueError("pipeline_config and policy only apply to engine v2")
        predictions = run_v1(dataset.records, input_mode)
        config = {"engine": "v1", "input_mode": input_mode, "threshold": None}
    elif engine == "v2":
        if input_mode != "context":
            raise ValueError("engine v2 only supports input_mode 'context'")
        pipeline_config = pipeline_config or PipelineConfig()
        policy = policy or load_builtin(DEFAULT_POLICY)
        predictions = run_v2(dataset.records, pipeline_config, policy)
        config = {
            "engine": "v2",
            "engine_version": ENGINE_VERSION,
            "input_mode": input_mode,
            "pipeline": pipeline_config.to_dict(),
            "verifier_chain": list(pipeline_config.chain().ids),
            "policy": {"id": policy.id, "version": policy.version, "hash": policy.hash},
        }
    else:
        raise ValueError(f"unknown engine {engine!r}")

    return {
        "schema_version": RUN_FILE_SCHEMA_VERSION,
        "manifest": build_manifest(dataset, config),
        "metrics": build_metrics(dataset.records, predictions),
        "predictions_hash": predictions_hash(predictions),
        "predictions": [prediction.to_dict() for prediction in predictions],
    }


def write_run(run: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(run, file, indent=2, sort_keys=True, ensure_ascii=False)
        file.write("\n")


def read_run(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as file:
            run: dict[str, Any] = json.load(file)
    except FileNotFoundError:
        raise RunFileError(f"run file not found: {path}") from None
    except json.JSONDecodeError as error:
        raise RunFileError(f"run file is not valid JSON: {path}: {error}") from None

    if run.get("schema_version") != RUN_FILE_SCHEMA_VERSION:
        raise RunFileError(
            f"{path}: unsupported schema_version {run.get('schema_version')!r}"
        )
    for key in ("manifest", "metrics", "predictions", "predictions_hash"):
        if key not in run:
            raise RunFileError(f"{path}: missing key {key!r}")
    return run


__all__ = ["run_benchmark", "write_run", "read_run"]
