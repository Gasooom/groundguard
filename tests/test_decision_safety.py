from groundguard.domain.contradiction import ContradictionResult
from groundguard.domain.decision import (
    DecisionResult,
    evaluate_decision,
)
from groundguard.domain.grounding import GroundingResult
from groundguard.domain.relevance import RelevanceResult
from groundguard.domain.safety import SafetyResult


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


def make_safety(
    *,
    pii_detected: bool = False,
    prompt_injection_detected: bool = False,
) -> SafetyResult:
    return SafetyResult(
        safe=not (
            pii_detected
            or prompt_injection_detected
        ),
        pii_detected=pii_detected,
        prompt_injection_detected=(
            prompt_injection_detected
        ),
        pii_categories=(
            ["EMAIL"]
            if pii_detected
            else []
        ),
        evidence=(
            ["user@example.com"]
            if pii_detected
            else (
                ["ignore previous instructions"]
                if prompt_injection_detected
                else []
            )
        ),
    )


def test_safe_reliable_answer_is_accepted():
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
        safety=make_safety(),
    )

    assert isinstance(result, DecisionResult)
    assert result.system_decision == "ACCEPT"
    assert result.label == "RELIABLE"
    assert result.reliable is True


def test_pii_detection_rejects_answer():
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
        safety=make_safety(
            pii_detected=True,
        ),
    )

    assert result.system_decision == "REJECT"
    assert result.label == "UNRELIABLE"
    assert result.reliable is False
    assert "PII" in result.reason


def test_prompt_injection_rejects_answer():
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
        safety=make_safety(
            prompt_injection_detected=True,
        ),
    )

    assert result.system_decision == "REJECT"
    assert result.label == "UNRELIABLE"
    assert result.reliable is False
    assert "prompt injection" in result.reason.lower()


def test_multiple_safety_threats_reject_answer():
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
        safety=make_safety(
            pii_detected=True,
            prompt_injection_detected=True,
        ),
    )

    assert result.system_decision == "REJECT"
    assert result.label == "UNRELIABLE"
    assert result.reliable is False
    assert "PII" in result.reason
    assert "prompt injection" in result.reason.lower()


def test_safety_overrides_high_reliability_score():
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
        safety=make_safety(
            pii_detected=True,
        ),
        threshold=0.70,
    )

    assert result.reliability_score == 1.0
    assert result.threshold == 0.70
    assert result.system_decision == "REJECT"
    assert result.reliable is False


def test_safe_result_preserves_threshold_behavior():
    result = evaluate_decision(
        grounding=make_grounding(
            "SUPPORTED",
            0.60,
        ),
        relevance=make_relevance(
            "RELEVANT",
            0.60,
        ),
        contradiction=make_contradiction(
            "NOT_CONTRADICTORY",
            0.0,
        ),
        safety=make_safety(),
        threshold=0.70,
    )

    assert result.reliability_score == 0.60
    assert result.threshold == 0.70
    assert result.system_decision == "FLAG"
    assert result.label == "UNRELIABLE"
    assert result.reliable is False


def test_contradiction_still_rejects_when_safe():
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
        safety=make_safety(),
    )

    assert result.system_decision == "REJECT"
    assert result.label == "UNRELIABLE"
    assert result.reliable is False