from groundguard.domain.relevance import (
    RelevanceResult,
    evaluate_relevance,
)


def test_relevance_result():
    result = RelevanceResult(
        score=1.0,
        relevant=True,
        label="RELEVANT",
    )

    assert result.score == 1.0
    assert result.relevant is True
    assert result.label == "RELEVANT"


def test_relevant_answer():
    result = evaluate_relevance(
        "When was Acme Technologies founded?",
        "Acme Technologies was founded in 2018.",
    )

    assert result.label == "RELEVANT"
    assert result.relevant is True


def test_irrelevant_answer():
    result = evaluate_relevance(
        "When was Acme Technologies founded?",
        "Acme Technologies has offices in Kigali.",
    )

    assert result.label == "IRRELEVANT"
    assert result.relevant is False


def test_empty_answer_is_irrelevant():
    result = evaluate_relevance(
        "When was Acme Technologies founded?",
        "",
    )

    assert result.label == "IRRELEVANT"
    assert result.score == 0.0


def test_numeric_question():
    result = evaluate_relevance(
        "How many offices does Orion Labs have?",
        "Orion Labs has five offices.",
    )

    assert result.label == "RELEVANT"


def test_location_question():
    result = evaluate_relevance(
        "Where is NovaTech headquartered?",
        "NovaTech is headquartered in Nairobi.",
    )

    assert result.label == "RELEVANT"


def test_temporal_question():
    result = evaluate_relevance(
        "When did BrightAI launch its platform?",
        "BrightAI launched its platform in 2022.",
    )

    assert result.label == "RELEVANT"