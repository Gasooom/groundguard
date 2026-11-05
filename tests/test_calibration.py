import math
import random

import pytest

from groundguard.calibration import (
    CalibrationSet,
    calibration_report,
    fit_calibration,
    load_calibration,
)
from groundguard.calibration.fit import calibrator_from_dict, fit_isotonic, fit_platt
from groundguard.calibration.metrics import brier_score, equal_mass_bins, expected_calibration_error
from groundguard.core.types import ClaimVerdict
from groundguard.pipeline import evaluate_v2
from groundguard.policy import decide, load_policy_text
from groundguard.policy.facts import facts_from_v2


def test_isotonic_pav_hand_computed():
    # scores 1..5, outcomes 1,0,1,0,1 -> PAV pools (2,3) and (4,5)? Work it out:
    # blocks: 1:1, 2:0 -> violation -> pool {1,2}=0.5; 3:1 ok; 4:0 -> pool {3,4}=0.5,
    # then 0.5 vs 0.5 is not a violation; 5:1 ok.
    calibrator = fit_isotonic([1, 2, 3, 4, 5], [1, 0, 1, 0, 1], direction="increasing")
    assert calibrator.thresholds == (1, 3, 5)
    assert calibrator.values == (0.5, 0.5, 1.0)
    assert calibrator.predict(0.0) == 0.5      # clipped below the first block
    assert calibrator.predict(4.5) == 0.5
    assert calibrator.predict(9.0) == 1.0


def test_isotonic_is_monotone_and_auto_detects_direction():
    rng = random.Random(3)
    scores = [rng.random() for _ in range(300)]
    increasing = [int(rng.random() < s) for s in scores]
    calibrator = fit_isotonic(scores, increasing)
    assert calibrator.direction == "increasing"
    assert list(calibrator.values) == sorted(calibrator.values)

    decreasing = [1 - o for o in increasing]
    calibrator = fit_isotonic(scores, decreasing)
    assert calibrator.direction == "decreasing"
    assert list(calibrator.values) == sorted(calibrator.values, reverse=True)


def test_isotonic_groups_tied_scores():
    calibrator = fit_isotonic([1.0, 1.0, 1.0, 1.0], [1, 1, 0, 0])
    assert calibrator.thresholds == (1.0,)
    assert calibrator.values == (0.5,)


def test_platt_learns_an_increasing_sigmoid():
    rng = random.Random(7)
    scores = [rng.uniform(-3, 3) for _ in range(400)]
    outcomes = [int(rng.random() < 1 / (1 + math.exp(-2 * s))) for s in scores]
    calibrator = fit_platt(scores, outcomes)
    assert calibrator.a < 0  # p = 1 / (1 + exp(a*s + b)) increases with s when a < 0
    assert calibrator.predict(-3) < 0.1 < 0.9 < calibrator.predict(3)
    assert 0.0 < calibrator.predict(1e6) <= 1.0 and 0.0 <= calibrator.predict(-1e6) < 1.0


@pytest.mark.parametrize(
    "scores, outcomes",
    [([], []), ([1.0], [1, 0]), ([1.0], [2]), ([float("nan")], [1])],
)
def test_fit_validation(scores, outcomes):
    with pytest.raises(ValueError):
        fit_isotonic(scores, outcomes)


def test_ece_and_brier_hand_computed():
    # Perfectly calibrated: two bins with confidence equal to accuracy.
    probabilities = [0.25] * 4 + [0.75] * 4
    outcomes = [1, 0, 0, 0, 1, 1, 1, 0]
    assert expected_calibration_error(probabilities, outcomes, bins=2) == pytest.approx(0.0)
    # Always-confident and half wrong: ECE 0.5
    assert expected_calibration_error([1.0] * 4, [1, 1, 0, 0], bins=1) == pytest.approx(0.5)
    assert brier_score([1.0, 0.0, 0.5], [1, 1, 0]) == pytest.approx((0 + 1 + 0.25) / 3)
    bins = equal_mass_bins([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1], bins=2)
    assert [b["count"] for b in bins] == [2, 2]


def test_calibrator_from_dict_validation():
    assert calibrator_from_dict({"kind": "platt", "a": -1, "b": 0}).predict(0) == 0.5
    with pytest.raises(ValueError):
        calibrator_from_dict({"kind": "isotonic", "direction": "increasing", "thresholds": [2, 1], "values": [0.1, 0.2]})
    with pytest.raises(ValueError):
        calibrator_from_dict({"kind": "isotonic", "direction": "increasing", "thresholds": [1], "values": [1.5]})
    with pytest.raises(ValueError):
        calibrator_from_dict({"kind": "magic"})


def _claims_run(rows, *, split="dev", label_status="reviewed"):
    return {
        "kind": "claims",
        "predictions_hash": "h",
        "manifest": {
            "dataset": {"id": "fixture", "version": "1.0.0", "sha256": "s"},
            "config": {"split": split, "label_status": label_status},
        },
        "predictions": [{"id": "r", "claims": rows}],
    }


def _rows(n=60):
    rng = random.Random(11)
    rows = []
    for i in range(n):
        score = rng.random()
        correct = rng.random() < score
        rows.append({"id": f"c{i}", "gold": "SUPPORTED" if correct else "NOT_ENOUGH_INFO",
                     "label": "SUPPORTED", "verifier": "lexical@test", "raw_score": score})
    rows.append({"id": "rare", "gold": "CONTRADICTED", "label": "CONTRADICTED",
                 "verifier": "guards@test", "raw_score": 0.9})
    return rows


def test_fit_calibration_per_verifier_and_label_with_min_samples(tmp_path):
    calibration = fit_calibration(_claims_run(_rows()), min_samples=30)
    assert set(calibration.calibrators) == {("lexical@test", "SUPPORTED")}
    assert calibration.fitted_on["skipped"] == {"guards@test|CONTRADICTED": 1}

    path = tmp_path / "calibration.json"
    calibration.save(path)
    loaded = load_calibration(path)
    assert loaded.hash == calibration.hash

    verdict = ClaimVerdict("c", "SUPPORTED", 0.95, (), "lexical@test", "")
    assert 0.0 <= loaded.apply(verdict).confidence <= 1.0
    unknown = ClaimVerdict("c", "SUPPORTED", 0.95, (), "other@1", "")
    assert loaded.apply(unknown).confidence is None


def test_fit_calibration_refuses_test_and_unreviewed_runs():
    with pytest.raises(ValueError, match="test-split"):
        fit_calibration(_claims_run(_rows(), split="test"))
    with pytest.raises(ValueError, match="unreviewed"):
        fit_calibration(_claims_run(_rows(), split="unreviewed", label_status="unreviewed"))
    assert fit_calibration(
        _claims_run(_rows(), split="unreviewed", label_status="unreviewed"), allow_unreviewed=True
    ).calibrators
    with pytest.raises(ValueError, match="claim-level run"):
        fit_calibration({"kind": "legacy", "manifest": {"config": {"split": "dev", "label_status": "reviewed"}}})


def test_calibration_report_counts_uncalibrated_claims():
    calibration = fit_calibration(_claims_run(_rows()), min_samples=30)
    report = calibration_report(_claims_run(_rows(), split="test"), calibration, bins=5)
    assert report["claims_scored"] == 60
    assert report["claims_uncalibrated"] == 1
    assert 0.0 <= report["ece"] <= 1.0 and 0.0 <= report["brier"] <= 1.0
    assert report["evaluated_on"]["split"] == "test"


def test_pipeline_applies_calibration_and_policy_can_route_low_confidence():
    base = evaluate_v2(question="When was Acme founded?", context="Acme was founded in 2010.",
                       answer="Acme was founded in 2010.")
    (verdict,) = base.verdicts
    assert verdict.confidence is None
    assert base.manifest["calibration"] is None

    low = CalibrationSet(
        calibrators={(verdict.verifier, "SUPPORTED"): calibrator_from_dict(
            {"kind": "isotonic", "direction": "increasing", "thresholds": [0.0], "values": [0.4]})},
        fitted_on={"split": "dev"},
        counts={(verdict.verifier, "SUPPORTED"): 30},
    )
    calibrated = evaluate_v2(question="When was Acme founded?", context="Acme was founded in 2010.",
                             answer="Acme was founded in 2010.", calibration=low)
    assert calibrated.verdicts[0].confidence == 0.4
    assert calibrated.manifest["calibration"]["hash"] == low.hash
    assert calibrated.manifest["config_hash"] != base.manifest["config_hash"]

    policy = load_policy_text('''
[policy]
id = "review-low-confidence"
version = "1.0.0"
description = "test"

[[rule]]
id = "low_confidence"
when = { min_confidence_below = 0.6 }
decision = "HUMAN_REVIEW"
description = "low confidence"

[default]
id = "default.accept"
decision = "ACCEPT"
description = "accept"
''')
    facts = facts_from_v2(calibrated.verdicts, relevant=True, pii_detected=False, injection_detected=False)
    assert decide(policy, facts).decision == "HUMAN_REVIEW"
    facts = facts_from_v2(base.verdicts, relevant=True, pii_detected=False, injection_detected=False)
    assert decide(policy, facts).decision == "ACCEPT"
