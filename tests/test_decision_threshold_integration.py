from groundguard.domain.contradiction import ContradictionResult
from groundguard.domain.decision import evaluate_decision
from groundguard.domain.grounding import GroundingResult
from groundguard.domain.relevance import RelevanceResult


def make_grounding(
    label: str,
    score: float,
) -> GroundingResult:
    return GroundingResult(
        score=score,
        grounded=label != "UNSUPPORTED",
        evidence=[],
        label=label,
    )


def make_relevance(
    label: str,
    score: float,
) -> RelevanceResult:
    return RelevanceResult(
        score=score,
        relevant=label == "RELEVANT",
        label=label,
    )


def make_contradiction(
    label: str,
    score: float,
) -> ContradictionResult:
    return ContradictionResult(
        score=score,
        contradictory=label == "CONTRADICTORY",
        label=label,
        evidence=[],
    )


def test_score_above_threshold_is_accepted():
    result = evaluate_decision(
        grounding=make_grounding("SUPPORTED", 0.9),
        relevance=make_relevance("RELEVANT", 0.9),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
    )

    assert result.reliability_score == 0.9
    assert result.threshold == 0.7
    assert result.system_decision == "ACCEPT"
    assert result.label == "RELIABLE"
    assert result.reliable is True


def test_score_below_threshold_is_flagged():
    result = evaluate_decision(
        grounding=make_grounding("SUPPORTED", 0.65),
        relevance=make_relevance("RELEVANT", 0.8),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
    )

    assert result.reliability_score == 0.65
    assert result.threshold == 0.7
    assert result.system_decision == "FLAG"
    assert result.label == "UNRELIABLE"
    assert result.reliable is False


def test_custom_threshold_is_used():
    result = evaluate_decision(
        grounding=make_grounding("SUPPORTED", 0.65),
        relevance=make_relevance("RELEVANT", 0.8),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
        threshold=0.6,
    )

    assert result.reliability_score == 0.65
    assert result.threshold == 0.6
    assert result.system_decision == "ACCEPT"
    assert result.reliable is True


def test_contradiction_overrides_threshold():
    result = evaluate_decision(
        grounding=make_grounding("SUPPORTED", 1.0),
        relevance=make_relevance("RELEVANT", 1.0),
        contradiction=make_contradiction(
            "CONTRADICTORY",
            1.0,
        ),
    )

    assert result.reliability_score == 0.0
    assert result.system_decision == "REJECT"
    assert result.label == "UNRELIABLE"


def test_unsupported_grounding_overrides_threshold():
    result = evaluate_decision(
        grounding=make_grounding("UNSUPPORTED", 1.0),
        relevance=make_relevance("RELEVANT", 1.0),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
    )

    assert result.system_decision == "REJECT"
    assert result.label == "UNRELIABLE"


def test_partial_grounding_remains_flag():
    result = evaluate_decision(
        grounding=make_grounding(
            "PARTIALLY_SUPPORTED",
            0.9,
        ),
        relevance=make_relevance("RELEVANT", 0.9),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
    )

    assert result.reliability_score == 0.9
    assert result.system_decision == "FLAG"
    assert result.label == "UNRELIABLE"


def test_invalid_threshold_is_rejected():
    try:
        evaluate_decision(
            grounding=make_grounding("SUPPORTED", 1.0),
            relevance=make_relevance("RELEVANT", 1.0),
            contradiction=make_contradiction(
                "NOT_CONTRADICTORY",
                0.0,
            ),
            threshold=1.1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for threshold > 1.0"
        )