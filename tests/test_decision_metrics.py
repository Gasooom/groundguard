import pytest

from groundguard.evaluation.decision_metrics import (
    evaluate_threshold,
    reliability_score,
    tune_threshold,
)


def test_reliability_score_uses_conservative_component():
    score = reliability_score(
        grounding_score=0.9,
        relevance_score=0.8,
        contradiction_score=0.1,
    )

    assert score == 0.8


def test_reliability_score_penalizes_contradiction():
    score = reliability_score(
        grounding_score=0.95,
        relevance_score=0.95,
        contradiction_score=0.8,
    )

    assert score == 0.2


def test_threshold_counts_are_correct():
    metrics = evaluate_threshold(
        scores=[
            0.9,
            0.8,
            0.2,
            0.1,
        ],
        expected_reliable=[
            True,
            True,
            False,
            False,
        ],
        threshold=0.5,
    )

    assert metrics.true_accepts == 2
    assert metrics.true_rejects == 2
    assert metrics.false_accepts == 0
    assert metrics.false_rejects == 0

    assert metrics.false_accept_rate == 0.0
    assert metrics.false_reject_rate == 0.0


def test_false_accept_rate():
    metrics = evaluate_threshold(
        scores=[
            0.9,
            0.8,
            0.4,
            0.2,
        ],
        expected_reliable=[
            True,
            False,
            False,
            False,
        ],
        threshold=0.5,
    )

    assert metrics.false_accepts == 1
    assert metrics.false_rejects == 0
    assert metrics.false_accept_rate == 0.3333
    assert metrics.false_reject_rate == 0.0


def test_false_reject_rate():
    metrics = evaluate_threshold(
        scores=[
            0.9,
            0.4,
            0.2,
        ],
        expected_reliable=[
            True,
            True,
            False,
        ],
        threshold=0.5,
    )

    assert metrics.false_accepts == 0
    assert metrics.false_rejects == 1
    assert metrics.false_accept_rate == 0.0
    assert metrics.false_reject_rate == 0.5


def test_threshold_tuning_finds_perfect_threshold():
    result = tune_threshold(
        scores=[
            0.95,
            0.9,
            0.2,
            0.1,
        ],
        expected_reliable=[
            True,
            True,
            False,
            False,
        ],
    )

    assert result.metrics.false_accept_rate == 0.0
    assert result.metrics.false_reject_rate == 0.0
    assert 0.2 < result.threshold <= 0.95


def test_threshold_tuning_is_deterministic():
    scores = [
        0.95,
        0.9,
        0.2,
        0.1,
    ]

    expected = [
        True,
        True,
        False,
        False,
    ]

    first = tune_threshold(
        scores,
        expected,
    )

    second = tune_threshold(
        scores,
        expected,
    )

    assert first == second


def test_invalid_threshold_is_rejected():
    with pytest.raises(ValueError):
        evaluate_threshold(
            [0.5],
            [True],
            threshold=1.5,
        )


def test_mismatched_lengths_are_rejected():
    with pytest.raises(ValueError):
        evaluate_threshold(
            [0.5, 0.6],
            [True],
            threshold=0.5,
        )


def test_invalid_score_is_rejected():
    with pytest.raises(ValueError):
        evaluate_threshold(
            [1.2],
            [True],
            threshold=0.5,
        )


def test_invalid_component_score_is_rejected():
    with pytest.raises(ValueError):
        reliability_score(
            grounding_score=1.2,
            relevance_score=0.5,
            contradiction_score=0.0,
        )


def test_empty_threshold_data_is_rejected():
    with pytest.raises(ValueError):
        tune_threshold(
            [],
            [],
        )