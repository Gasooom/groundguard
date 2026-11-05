"""Calibrated confidence for claim verdicts.

A ``CalibrationSet`` maps (verifier id, predicted label) to a calibrator
that turns the verifier's raw score into P(the verdict is correct). Verdicts
from a verifier/label pair without a calibrator keep ``confidence = None``
("uncalibrated"). A calibrator belongs to an exact verifier version, so a
changed verifier is uncalibrated until it is refitted.

Fitting uses claim-level benchmark runs (``groundguard bench claims``) on
the dev split only. Test-split runs are refused.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from groundguard.calibration.fit import (
    IsotonicCalibrator,
    PlattCalibrator,
    calibrator_from_dict,
    fit_isotonic,
    fit_platt,
)
from groundguard.calibration.metrics import brier_score, equal_mass_bins, expected_calibration_error
from groundguard.core.serialization import sha256_json
from groundguard.core.types import ClaimVerdict


Method = Literal["isotonic", "platt"]
Calibrator = IsotonicCalibrator | PlattCalibrator
CALIBRATION_FILE_VERSION = 1


@dataclass(frozen=True)
class CalibrationSet:
    calibrators: Mapping[tuple[str, str], Calibrator]
    fitted_on: Mapping[str, Any]
    counts: Mapping[tuple[str, str], int]

    @property
    def hash(self) -> str:
        return sha256_json(self.to_dict())

    def confidence(self, verdict: ClaimVerdict) -> float | None:
        calibrator = self.calibrators.get((verdict.verifier, verdict.label))
        return None if calibrator is None else round(calibrator.predict(verdict.raw_score), 6)

    def apply(self, verdict: ClaimVerdict) -> ClaimVerdict:
        return replace(verdict, confidence=self.confidence(verdict))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CALIBRATION_FILE_VERSION,
            "fitted_on": dict(self.fitted_on),
            "entries": [
                {"verifier": verifier, "label": label, "samples": self.counts[(verifier, label)],
                 "calibrator": calibrator.to_dict()}
                for (verifier, label), calibrator in sorted(self.calibrators.items())
            ],
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_calibration(path: Path) -> CalibrationSet:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != CALIBRATION_FILE_VERSION:
        raise ValueError(f"{path}: unsupported calibration file version {data.get('version')!r}")
    calibrators: dict[tuple[str, str], Calibrator] = {}
    counts: dict[tuple[str, str], int] = {}
    for entry in data["entries"]:
        key = (entry["verifier"], entry["label"])
        calibrators[key] = calibrator_from_dict(entry["calibrator"])
        counts[key] = int(entry["samples"])
    return CalibrationSet(calibrators, data["fitted_on"], counts)


def _claim_rows(run: Mapping[str, Any]) -> list[dict[str, Any]]:
    if run.get("kind") != "claims":
        raise ValueError("calibration needs a claim-level run (groundguard bench claims)")
    return [claim for record in run["predictions"] for claim in record["claims"]]


def fit_calibration(
    run: Mapping[str, Any],
    *,
    method: Method = "isotonic",
    min_samples: int = 30,
    allow_unreviewed: bool = False,
) -> CalibrationSet:
    """Fit one calibrator per (verifier, predicted label) with enough samples."""

    config = run["manifest"]["config"]
    if config.get("split") == "test":
        raise ValueError("refusing to fit calibration on a test-split run")
    if config.get("label_status") != "reviewed" and not allow_unreviewed:
        raise ValueError("run uses unreviewed labels; pass allow_unreviewed=True for development only")
    if min_samples < 2:
        raise ValueError("min_samples must be at least 2")

    grouped: dict[tuple[str, str], list[tuple[float, int]]] = defaultdict(list)
    for row in _claim_rows(run):
        grouped[(row["verifier"], row["label"])].append((float(row["raw_score"]), int(row["label"] == row["gold"])))

    calibrators: dict[tuple[str, str], Calibrator] = {}
    counts: dict[tuple[str, str], int] = {}
    for key, samples in sorted(grouped.items()):
        if len(samples) < min_samples:
            continue
        scores = [score for score, _ in samples]
        outcomes = [outcome for _, outcome in samples]
        calibrators[key] = fit_isotonic(scores, outcomes) if method == "isotonic" else fit_platt(scores, outcomes)
        counts[key] = len(samples)

    fitted_on = {
        "dataset": run["manifest"]["dataset"]["id"],
        "dataset_version": run["manifest"]["dataset"]["version"],
        "dataset_sha256": run["manifest"]["dataset"]["sha256"],
        "split": config.get("split"),
        "label_status": config.get("label_status"),
        "run_predictions_hash": run["predictions_hash"],
        "method": method,
        "min_samples": min_samples,
        "skipped": {f"{v}|{l}": len(s) for (v, l), s in sorted(grouped.items()) if len(s) < min_samples},
    }
    return CalibrationSet(calibrators, fitted_on, counts)


def calibration_report(run: Mapping[str, Any], calibration: CalibrationSet, *, bins: int = 10) -> dict[str, Any]:
    """ECE, Brier and reliability bins of calibrated confidence on ``run``'s claims.

    Claims whose verifier/label pair has no calibrator are counted, not scored.
    """

    probabilities: list[float] = []
    outcomes: list[int] = []
    uncalibrated = 0
    for row in _claim_rows(run):
        calibrator = calibration.calibrators.get((row["verifier"], row["label"]))
        if calibrator is None:
            uncalibrated += 1
            continue
        probabilities.append(calibrator.predict(float(row["raw_score"])))
        outcomes.append(int(row["label"] == row["gold"]))

    report: dict[str, Any] = {
        "claims_scored": len(probabilities),
        "claims_uncalibrated": uncalibrated,
        "evaluated_on": {
            "dataset_version": run["manifest"]["dataset"]["version"],
            "split": run["manifest"]["config"].get("split"),
            "label_status": run["manifest"]["config"].get("label_status"),
        },
        "fitted_on": dict(calibration.fitted_on),
    }
    if probabilities:
        report.update(
            ece=round(expected_calibration_error(probabilities, outcomes, bins), 6),
            brier=round(brier_score(probabilities, outcomes), 6),
            reliability=[{k: round(v, 6) if isinstance(v, float) else v for k, v in item.items()}
                         for item in equal_mass_bins(probabilities, outcomes, bins)],
        )
    return report


def apply_to_verdicts(verdicts: Sequence[ClaimVerdict], calibration: CalibrationSet | None) -> tuple[ClaimVerdict, ...]:
    if calibration is None:
        return tuple(verdicts)
    return tuple(calibration.apply(verdict) for verdict in verdicts)


__all__ = [
    "CalibrationSet",
    "apply_to_verdicts",
    "calibration_report",
    "fit_calibration",
    "load_calibration",
]
