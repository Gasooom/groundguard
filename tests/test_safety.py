from groundguard.domain.safety import (
    PIIDetection,
    PromptInjectionDetection,
    SafetyResult,
    build_safety_result,
)


def test_pii_detection_contract():
    result = PIIDetection(
        detected=True,
        categories=["EMAIL"],
        evidence=["user@example.com"],
    )

    assert result.detected is True
    assert result.categories == ["EMAIL"]
    assert result.evidence == ["user@example.com"]


def test_prompt_injection_detection_contract():
    result = PromptInjectionDetection(
        detected=True,
        evidence=["ignore previous instructions"],
    )

    assert result.detected is True
    assert result.evidence == [
        "ignore previous instructions"
    ]


def test_safe_result_when_no_threats():
    result = build_safety_result(
        pii=PIIDetection(
            detected=False,
            categories=[],
            evidence=[],
        ),
        prompt_injection=PromptInjectionDetection(
            detected=False,
            evidence=[],
        ),
    )

    assert isinstance(result, SafetyResult)
    assert result.safe is True
    assert result.pii_detected is False
    assert result.prompt_injection_detected is False
    assert result.pii_categories == []
    assert result.evidence == []


def test_pii_makes_result_unsafe():
    result = build_safety_result(
        pii=PIIDetection(
            detected=True,
            categories=["EMAIL"],
            evidence=["user@example.com"],
        ),
        prompt_injection=PromptInjectionDetection(
            detected=False,
            evidence=[],
        ),
    )

    assert result.safe is False
    assert result.pii_detected is True
    assert result.prompt_injection_detected is False
    assert result.pii_categories == ["EMAIL"]
    assert result.evidence == ["user@example.com"]


def test_prompt_injection_makes_result_unsafe():
    result = build_safety_result(
        pii=PIIDetection(
            detected=False,
            categories=[],
            evidence=[],
        ),
        prompt_injection=PromptInjectionDetection(
            detected=True,
            evidence=["ignore previous instructions"],
        ),
    )

    assert result.safe is False
    assert result.pii_detected is False
    assert result.prompt_injection_detected is True
    assert result.evidence == [
        "ignore previous instructions"
    ]


def test_multiple_safety_signals_are_combined():
    result = build_safety_result(
        pii=PIIDetection(
            detected=True,
            categories=["EMAIL", "PHONE"],
            evidence=[
                "user@example.com",
                "+250788123456",
            ],
        ),
        prompt_injection=PromptInjectionDetection(
            detected=True,
            evidence=[
                "ignore previous instructions"
            ],
        ),
    )

    assert result.safe is False
    assert result.pii_detected is True
    assert result.prompt_injection_detected is True

    assert result.pii_categories == [
        "EMAIL",
        "PHONE",
    ]

    assert result.evidence == [
        "user@example.com",
        "+250788123456",
        "ignore previous instructions",
    ]