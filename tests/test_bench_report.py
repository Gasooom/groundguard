from groundguard.bench.datasets import BenchmarkRecord
from groundguard.bench.report import build_metrics
from groundguard.bench.runner import Prediction


def _record(record_id, good, context):
    return BenchmarkRecord(
        id=record_id,
        question="q?",
        context=context,
        answer=f"answer {record_id}",
        grounding_label="SUPPORTED" if good else "UNSUPPORTED",
        relevance_label="RELEVANT",
        contradiction_label="NOT_CONTRADICTORY",
        evidence=(),
        source="synthetic",
        annotation_status="LABELED",
    )


def _prediction(record_id, decision):
    return Prediction(
        id=record_id,
        grounding_label="SUPPORTED",
        grounding_score=1.0,
        relevance_label="RELEVANT",
        relevance_score=1.0,
        contradiction_label="NOT_CONTRADICTORY",
        contradiction_score=0.0,
        reliability_score=1.0,
        system_decision=decision,
    )


def test_human_review_metrics_hand_computed():
    # bad answers: b1 ACCEPT, b2 HUMAN_REVIEW, b3 REJECT, b4 HUMAN_REVIEW
    # good answers: g1 ACCEPT, g2 HUMAN_REVIEW
    rows = [
        ("b1", False, "ACCEPT"), ("b2", False, "HUMAN_REVIEW"), ("b3", False, "REJECT"),
        ("b4", False, "HUMAN_REVIEW"), ("g1", True, "ACCEPT"), ("g2", True, "HUMAN_REVIEW"),
    ]
    records = [_record(rid, good, f"context {i}") for i, (rid, good, _) in enumerate(rows)]
    predictions = [_prediction(rid, decision) for rid, _, decision in rows]

    decision = build_metrics(records, predictions)["all"]["decision"]

    assert decision["distribution"] == {"ACCEPT": 2, "FLAG": 0, "REJECT": 1, "HUMAN_REVIEW": 3}
    assert (decision["review_rate"]["numerator"], decision["review_rate"]["denominator"]) == (3, 6)
    # FAR counts HUMAN_REVIEW as "not accepted": 1 of 4 bad answers accepted.
    assert (decision["false_accept"]["numerator"], decision["false_accept"]["denominator"]) == (1, 4)
    # Among bad answers the system decided itself (b1, b3): 1 of 2 accepted.
    auto = decision["false_accept_among_auto_decided"]
    assert (auto["numerator"], auto["denominator"]) == (1, 2)
    # A good answer sent to review is a false reject from the automation's view.
    assert (decision["false_reject"]["numerator"], decision["false_reject"]["denominator"]) == (1, 2)
