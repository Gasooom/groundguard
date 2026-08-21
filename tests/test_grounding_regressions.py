from groundguard.domain.grounding import evaluate_grounding


def test_matching_year_is_supported():
    result = evaluate_grounding(
        "NovaTech expanded into Kenya in 2024.",
        "NovaTech expanded into Kenya in 2024.",
        question="What country did NovaTech expand into in 2024?",
    )

    assert result.label == "SUPPORTED"


def test_different_numeric_value_is_unsupported():
    result = evaluate_grounding(
        "Orion Labs has three offices.",
        "Orion Labs has five offices.",
        question="How many offices does Orion Labs have?",
    )

    assert result.label == "UNSUPPORTED"


def test_different_year_is_unsupported():
    result = evaluate_grounding(
        "Acme Technologies was founded in 2018.",
        "Acme Technologies was founded in 2015.",
        question="When was Acme Technologies founded?",
    )

    assert result.label == "UNSUPPORTED"