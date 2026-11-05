"""Run manifests: everything needed to reproduce or audit a benchmark run."""

from __future__ import annotations

import platform
import subprocess
from datetime import datetime, timezone
from importlib import metadata
from typing import Any

from groundguard.bench.datasets import REPO_ROOT, Dataset
from groundguard.core.serialization import sha256_json


# 2: decision metrics include HUMAN_REVIEW, review_rate and
#    false_accept_among_auto_decided (M3). Predictions are unchanged.
RUN_FILE_SCHEMA_VERSION = 2


def _git(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def groundguard_version() -> str:
    try:
        return metadata.version("groundguard")
    except metadata.PackageNotFoundError:
        return "unknown"


def config_hash(config: dict[str, Any]) -> str:
    return sha256_json(config)


def build_manifest(dataset: Dataset, config: dict[str, Any]) -> dict[str, Any]:
    """Describe the run environment.

    Volatile fields (``created_at``, ``git``, ``python``) are informational;
    reproducibility is judged on ``predictions_hash`` and metrics, never on
    these fields.
    """

    status = _git("status", "--porcelain")
    return {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "groundguard_version": groundguard_version(),
        "engine": config.get("engine", "v1"),
        "git": {
            "commit": _git("rev-parse", "HEAD"),
            "dirty": None if status is None else bool(status),
        },
        "python": platform.python_version(),
        "dataset": {
            "id": dataset.id,
            "version": dataset.version,
            "sha256": dataset.sha256,
            "records": len(dataset),
            "files": list(dataset.files),
        },
        "config": config,
        "config_hash": config_hash(config),
    }
