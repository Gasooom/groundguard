from groundguard.domain.grounding import evaluate_grounding


def test_supported_answer():
    result = evaluate_grounding(
        "Acme Technologies was founded in 2018.",
        "Acme Technologies was founded in 2018.",
    )

    assert result.label == "SUPPORTED"
    assert result.score >= 0.80
    assert result.evidence


def test_partially_supported_answer():
    result = evaluate_grounding(
        "Acme Technologies was founded in 2018.",
        "Acme Technologies was founded in 2018 and is headquartered in Kigali.",
    )

    assert result.label == "PARTIALLY_SUPPORTED"
    assert result.evidence


def test_unsupported_answer():
    result = evaluate_grounding(
        "Acme Technologies was founded in 2018.",
        "Acme Technologies was founded in 2015.",
    )

    assert result.label == "UNSUPPORTED"


def test_empty_input():
    result = evaluate_grounding(
        "",
        "Acme was founded in 2018.",
    )

    assert result.label == "UNSUPPORTED"
    assert result.score == 0.0