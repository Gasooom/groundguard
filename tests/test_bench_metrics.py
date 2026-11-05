import math

import pytest

from groundguard.bench.metrics import (
    Rate,
    accuracy,
    bootstrap_ci,
    confusion_matrix,
    decision_rates,
    macro_f1,
    per_label_scores,
    wilson_interval,
)
from groundguard.evaluation.decision_metrics import evaluate_threshold


GOLD = ["A", "A", "A", "B", "B", "C"]
PRED = ["A", "A", "B", "B", "C", "C"]
LABELS = ("A", "B", "C")


def test_accuracy_counts():
    rate = accuracy(GOLD, PRED)
    assert (rate.numerator, rate.denominator) == (4, 6)
    assert rate.value == pytest.approx(4 / 6)


def test_rate_with_zero_denominator_is_undefined():
    assert Rate(0, 0).value is None
    assert Rate(0, 0).to_dict()["value"] is None


def test_confusion_matrix_hand_computed():
    assert confusion_matrix(GOLD, PRED, LABELS) == {
        "A": {"A": 2, "B": 1, "C": 0},
        "B": {"A": 0, "B": 1, "C": 1},
        "C": {"A": 0, "B": 0, "C": 1},
    }


def test_confusion_matrix_rejects_unknown_labels():
    with pytest.raises(ValueError, match="not in label set"):
        confusion_matrix(["A"], ["Z"], ("A", "B"))


def test_length_mismatch_and_empty_inputs_raise():
    with pytest.raises(ValueError):
        accuracy(["A"], ["A", "B"])
    with pytest.raises(ValueError):
        accuracy([], [])


def test_per_label_scores_and_macro_f1_hand_computed():
    scores = per_label_scores(GOLD, PRED, LABELS)

    # A: TP=2, predicted A=2, actual A=3
    assert scores["A"].precision.value == pytest.approx(1.0)
    assert scores["A"].recall.value == pytest.approx(2 / 3)
    assert scores["A"].f1 == pytest.approx(0.8)
    # B: TP=1, predicted B=2, actual B=2
    assert scores["B"].f1 == pytest.approx(0.5)
    # C: TP=1, predicted C=2, actual C=1 -> P=0.5, R=1.0
    assert scores["C"].f1 == pytest.approx(2 / 3)

    assert macro_f1(scores) == pytest.approx((0.8 + 0.5 + 2 / 3) / 3)


def test_macro_f1_ignores_labels_without_support():
    scores = per_label_scores(["A", "A"], ["A", "A"], ("A", "B"))
    assert scores["B"].support == 0
    assert macro_f1(scores) == pytest.approx(1.0)


def test_decision_rates_only_accept_counts_as_acceptance():
    gold_good = [True, True, False, False, False]
    decisions = ["ACCEPT", "FLAG", "ACCEPT", "REJECT", "FLAG"]
    rates = decision_rates(gold_good, decisions)

    assert rates.false_accept.numerator == 1
    assert rates.false_accept.denominator == 3
    assert rates.false_reject.numerator == 1
    assert rates.false_reject.denominator == 2


def test_decision_rates_match_v1_evaluate_threshold():
    scores = [0.95, 0.72, 0.4, 0.81, 0.69, 0.1, 0.7]
    expected = [True, True, False, False, True, False, True]
    threshold = 0.7

    v1 = evaluate_threshold(scores, expected, threshold)
    decisions = ["ACCEPT" if score >= threshold else "REJECT" for score in scores]
    rates = decision_rates(expected, decisions)

    assert rates.false_accepts == v1.false_accepts
    assert rates.false_rejects == v1.false_rejects
    assert rates.true_accepts == v1.true_accepts
    assert rates.true_rejects == v1.true_rejects
    assert round(rates.false_accept.value, 4) == v1.false_accept_rate
    assert round(rates.false_reject.value, 4) == v1.false_reject_rate


def test_wilson_interval_known_value():
    # 8/168 at 95%: reference values computed with the closed-form formula.
    low, high = wilson_interval(8, 168)
    p, n, z = 8 / 168, 168, 1.959963984540054
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    assert low == pytest.approx(centre - half)
    assert high == pytest.approx(centre + half)
    assert low < p < high


def test_wilson_interval_edges():
    assert wilson_interval(0, 0) is None
    low, high = wilson_interval(0, 10)
    assert low == 0.0 and 0.0 < high < 0.35
    low, high = wilson_interval(10, 10)
    assert high == 1.0 and 0.65 < low < 1.0
    with pytest.raises(ValueError):
        wilson_interval(5, 4)


def test_bootstrap_is_deterministic_and_resamples_groups():
    groups = ["g1", "g1", "g2", "g3", "g3", "g3"]
    values = [1, 1, 0, 1, 0, 0]

    def mean(indices):
        return sum(values[i] for i in indices) / len(indices)

    first = bootstrap_ci(groups, mean, n_resamples=500, seed=7)
    second = bootstrap_ci(groups, mean, n_resamples=500, seed=7)
    assert first == second
    low, high = first
    assert 0.0 <= low <= mean(range(6)) <= high <= 1.0


def test_bootstrap_constant_statistic_has_zero_width():
    groups = ["a", "b", "c"]
    assert bootstrap_ci(groups, lambda indices: 0.5, n_resamples=100) == (0.5, 0.5)


def test_bootstrap_returns_none_when_statistic_mostly_undefined():
    groups = ["a", "b"]
    assert bootstrap_ci(groups, lambda indices: None, n_resamples=50) is None


def test_bootstrap_validates_arguments():
    with pytest.raises(ValueError):
        bootstrap_ci(["a"], lambda indices: 1.0, n_resamples=0)
    with pytest.raises(ValueError):
        bootstrap_ci(["a"], lambda indices: 1.0, confidence=1.0)
