from groundguard.domain.relevance import evaluate_relevance


def test_same_entity_wrong_fact_is_irrelevant():
    result = evaluate_relevance(
        "When was Acme Technologies founded?",
        "Acme Technologies has offices in Kigali.",
    )

    assert result.label == "IRRELEVANT"


def test_numeric_answer_is_relevant():
    result = evaluate_relevance(
        "How many offices does Orion Labs have?",
        "Orion Labs has five offices.",
    )

    assert result.label == "RELEVANT"


def test_location_answer_is_relevant():
    result = evaluate_relevance(
        "Where is NovaTech headquartered?",
        "NovaTech is headquartered in Nairobi.",
    )

    assert result.label == "RELEVANT"


def test_temporal_answer_is_relevant():
    result = evaluate_relevance(
        "When did BrightAI launch its platform?",
        "BrightAI launched its platform in 2022.",
    )

    assert result.label == "RELEVANT"


def test_unrelated_answer_is_irrelevant():
    result = evaluate_relevance(
        "What does SecureNet sell?",
        "Orion Labs operates in Nairobi.",
    )

    assert result.label == "IRRELEVANT"


def test_empty_question_is_irrelevant():
    result = evaluate_relevance(
        "",
        "Acme Technologies was founded in 2018.",
    )

    assert result.label == "IRRELEVANT"


def test_empty_answer_is_irrelevant():
    result = evaluate_relevance(
        "When was Acme Technologies founded?",
        "",
    )

    assert result.label == "IRRELEVANT"