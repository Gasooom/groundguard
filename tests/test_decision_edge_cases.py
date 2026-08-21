from groundguard.domain.decision import evaluate_decision
from groundguard.domain.grounding import GroundingResult
from groundguard.domain.relevance import RelevanceResult
from groundguard.domain.contradiction import ContradictionResult


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


def test_contradiction_has_highest_priority():
    result = evaluate_decision(
        grounding=make_grounding("UNSUPPORTED", 0.0),
        relevance=make_relevance("IRRELEVANT", 0.0),
        contradiction=make_contradiction(
            "CONTRADICTORY",
            1.0,
        ),
    )

    assert result.label == "UNRELIABLE"
    assert result.reliable is False
    assert result.system_decision == "REJECT"
    assert "contradiction" in result.reason.lower()


def test_unsupported_grounding_is_rejected():
    result = evaluate_decision(
        grounding=make_grounding("UNSUPPORTED", 0.2),
        relevance=make_relevance("IRRELEVANT", 0.0),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
    )

    assert result.label == "UNRELIABLE"
    assert result.reliable is False
    assert result.system_decision == "REJECT"
    assert "grounding" in result.reason.lower()


def test_irrelevant_answer_is_rejected():
    result = evaluate_decision(
        grounding=make_grounding("SUPPORTED", 1.0),
        relevance=make_relevance("IRRELEVANT", 0.0),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
    )

    assert result.label == "UNRELIABLE"
    assert result.reliable is False
    assert result.system_decision == "REJECT"
    assert "relevance" in result.reason.lower()


def test_partial_grounding_is_flagged():
    result = evaluate_decision(
        grounding=make_grounding(
            "PARTIALLY_SUPPORTED",
            0.5,
        ),
        relevance=make_relevance(
            "RELEVANT",
            1.0,
        ),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
    )

    assert result.label == "UNRELIABLE"
    assert result.reliable is False
    assert result.system_decision == "FLAG"
    assert "grounding" in result.reason.lower()


def test_relevant_supported_non_contradictory_is_accepted():
    result = evaluate_decision(
        grounding=make_grounding(
            "SUPPORTED",
            0.99,
        ),
        relevance=make_relevance(
            "RELEVANT",
            0.99,
        ),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.01,
        ),
    )

    assert result.label == "RELIABLE"
    assert result.reliable is True
    assert result.system_decision == "ACCEPT"


def test_scores_are_rounded_to_four_decimal_places():
    result = evaluate_decision(
        grounding=make_grounding(
            "SUPPORTED",
            0.123456789,
        ),
        relevance=make_relevance(
            "RELEVANT",
            0.987654321,
        ),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.000009,
        ),
    )

    assert result.grounding_score == 0.1235
    assert result.relevance_score == 0.9877
    assert result.contradiction_score == 0.0


def test_reliable_reason_mentions_all_components():
    result = evaluate_decision(
        grounding=make_grounding(
            "SUPPORTED",
            1.0,
        ),
        relevance=make_relevance(
            "RELEVANT",
            1.0,
        ),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
    )

    reason = result.reason.lower()

    assert "grounding" in reason
    assert "relevance" in reason
    assert "contradiction" in reason