from groundguard.domain.contradiction import (
    ContradictionResult,
    evaluate_contradiction,
)


def test_contradiction_result():
    result = ContradictionResult(
        score=1.0,
        contradictory=True,
        label="CONTRADICTORY",
        evidence=[
            "The company was founded in 2015.",
        ],
    )

    assert result.score == 1.0
    assert result.contradictory is True
    assert result.label == "CONTRADICTORY"
    assert result.evidence == [
        "The company was founded in 2015.",
    ]


def test_non_contradictory_result():
    result = ContradictionResult(
        score=0.0,
        contradictory=False,
        label="NOT_CONTRADICTORY",
        evidence=[],
    )

    assert result.score == 0.0
    assert result.contradictory is False
    assert result.label == "NOT_CONTRADICTORY"
    assert result.evidence == []


def test_matching_year_is_not_contradictory():
    result = evaluate_contradiction(
        "Acme Technologies was founded in 2015.",
        "Acme Technologies was founded in 2015.",
    )

    assert result.label == "NOT_CONTRADICTORY"
    assert result.contradictory is False


def test_conflicting_year_is_contradictory():
    result = evaluate_contradiction(
        "Acme Technologies was founded in 2018.",
        "Acme Technologies was founded in 2015.",
    )

    assert result.label == "CONTRADICTORY"
    assert result.contradictory is True
    assert result.score == 1.0


def test_matching_number_is_not_contradictory():
    result = evaluate_contradiction(
        "Orion Labs has five offices.",
        "Orion Labs has five offices.",
    )

    assert result.label == "NOT_CONTRADICTORY"
    assert result.contradictory is False


def test_conflicting_number_is_contradictory():
    result = evaluate_contradiction(
        "Orion Labs has five offices.",
        "Orion Labs has three offices.",
    )

    assert result.label == "CONTRADICTORY"
    assert result.contradictory is True
    assert result.score == 1.0


def test_unrelated_claim_is_not_contradictory():
    result = evaluate_contradiction(
        "Acme Technologies has offices in Kigali.",
        "Acme Technologies was founded in 2015.",
    )

    assert result.label == "NOT_CONTRADICTORY"
    assert result.contradictory is False


def test_empty_answer_is_not_contradictory():
    result = evaluate_contradiction(
        "",
        "Acme Technologies was founded in 2015.",
    )

    assert result.label == "NOT_CONTRADICTORY"
    assert result.contradictory is False
    assert result.score == 0.0


def test_empty_evidence_is_not_contradictory():
    result = evaluate_contradiction(
        "Acme Technologies was founded in 2018.",
        "",
    )

    assert result.label == "NOT_CONTRADICTORY"
    assert result.contradictory is False
    assert result.score == 0.0