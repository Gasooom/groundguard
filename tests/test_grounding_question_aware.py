from groundguard.domain.grounding import evaluate_grounding


def test_answer_must_address_question():
    result = evaluate_grounding(
        "Acme Technologies was founded in 2018. "
        "Acme Technologies has offices in Kigali.",
        "Acme Technologies has offices in Kigali.",
        question="When was Acme Technologies founded?",
    )

    assert result.label == "UNSUPPORTED"


def test_answer_addresses_question():
    result = evaluate_grounding(
        "Acme Technologies was founded in 2018. "
        "Acme Technologies has offices in Kigali.",
        "Acme Technologies was founded in 2018.",
        question="When was Acme Technologies founded?",
    )

    assert result.label == "SUPPORTED"


def test_question_specific_numeric_claim():
    result = evaluate_grounding(
        "Orion Labs has three offices.",
        "Orion Labs has five offices.",
        question="How many offices does Orion Labs have?",
    )

    assert result.label == "UNSUPPORTED"