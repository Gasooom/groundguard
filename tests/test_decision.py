from groundguard.domain.decision import (
    DecisionLabel,
    DecisionResult,
    evaluate_decision,
)
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


def test_supported_relevant_non_contradictory_is_reliable():
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

    assert isinstance(result, DecisionResult)
    assert result.label == "RELIABLE"
    assert result.reliable is True


def test_unsupported_grounding_is_unreliable():
    result = evaluate_decision(
        grounding=make_grounding(
            "UNSUPPORTED",
            0.0,
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


def test_irrelevant_answer_is_unreliable():
    result = evaluate_decision(
        grounding=make_grounding(
            "SUPPORTED",
            1.0,
        ),
        relevance=make_relevance(
            "IRRELEVANT",
            0.0,
        ),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
    )

    assert result.label == "UNRELIABLE"
    assert result.reliable is False


def test_contradictory_answer_is_unreliable():
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
            "CONTRADICTORY",
            1.0,
        ),
    )

    assert result.label == "UNRELIABLE"
    assert result.reliable is False


def test_partial_grounding_is_not_automatically_reliable():
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


def test_all_negative_signals_are_unreliable():
    result = evaluate_decision(
        grounding=make_grounding(
            "UNSUPPORTED",
            0.0,
        ),
        relevance=make_relevance(
            "IRRELEVANT",
            0.0,
        ),
        contradiction=make_contradiction(
            "CONTRADICTORY",
            1.0,
        ),
    )

    assert result.label == "UNRELIABLE"
    assert result.reliable is False


def test_decision_result_contains_component_scores():
    result = evaluate_decision(
        grounding=make_grounding(
            "SUPPORTED",
            0.9,
        ),
        relevance=make_relevance(
            "RELEVANT",
            0.8,
        ),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.1,
        ),
    )

    assert result.grounding_score == 0.9
    assert result.relevance_score == 0.8
    assert result.contradiction_score == 0.1


def test_decision_result_has_reason():
    result = evaluate_decision(
        grounding=make_grounding(
            "UNSUPPORTED",
            0.1,
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

    assert result.reason
    assert "grounding" in result.reason.lower()


def test_decision_label_is_strict():
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

    assert result.label in {
        "RELIABLE",
        "UNRELIABLE",
    }

    assert isinstance(
        result.reliable,
        bool,
    )