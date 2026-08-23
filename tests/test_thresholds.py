import pytest

from groundguard.evaluation.thresholds import (
    DEFAULT_THRESHOLD_POLICY,
    ThresholdPolicy,
)


def test_default_threshold_policy():
    assert DEFAULT_THRESHOLD_POLICY.candidate_threshold == 0.70


def test_threshold_policy_accepts_valid_threshold():
    policy = ThresholdPolicy(
        candidate_threshold=0.75,
    )

    assert policy.candidate_threshold == 0.75


def test_threshold_policy_rejects_threshold_above_one():
    with pytest.raises(ValueError):
        ThresholdPolicy(
            candidate_threshold=1.1,
        )


def test_threshold_policy_rejects_threshold_below_zero():
    with pytest.raises(ValueError):
        ThresholdPolicy(
            candidate_threshold=-0.1,
        )