from groundguard.domain.contradiction import evaluate_contradiction


def test_conflicting_locations_are_contradictory():
    result = evaluate_contradiction(
        "NovaTech is headquartered in Nairobi.",
        "NovaTech is headquartered in Kigali.",
    )

    assert result.label == "CONTRADICTORY"
    assert result.contradictory is True


def test_conflicting_employee_counts_are_contradictory():
    result = evaluate_contradiction(
        "NovaTech has 250 employees.",
        "NovaTech employs 120 people.",
    )

    assert result.label == "CONTRADICTORY"
    assert result.contradictory is True


def test_different_products_are_not_automatically_contradictory():
    result = evaluate_contradiction(
        "CloudCore sells accounting software.",
        "CloudCore sells backup software and cloud storage.",
    )

    assert result.label == "NOT_CONTRADICTORY"
    assert result.contradictory is False


def test_different_services_are_not_automatically_contradictory():
    result = evaluate_contradiction(
        "Delta Systems provides medical diagnostic equipment.",
        "Delta Systems provides logistics software for regional transportation companies.",
    )

    assert result.label == "NOT_CONTRADICTORY"
    assert result.contradictory is False


def test_conflicting_revenue_is_contradictory():
    result = evaluate_contradiction(
        "NovaTech generated $40 million in revenue in 2023.",
        "NovaTech reported annual revenue of $4 million in 2023.",
    )

    assert result.label == "CONTRADICTORY"
    assert result.contradictory is True


def test_conflicting_capital_is_contradictory():
    result = evaluate_contradiction(
        "Mombasa is the capital of Kenya.",
        "Kenya's capital city is Nairobi.",
    )

    assert result.label == "CONTRADICTORY"
    assert result.contradictory is True


def test_conflicting_composition_is_contradictory():
    result = evaluate_contradiction(
        "Water consists of two hydrogen atoms and one carbon atom.",
        "Water consists of two hydrogen atoms and one oxygen atom.",
    )

    assert result.label == "CONTRADICTORY"
    assert result.contradictory is True


def test_matching_claims_remain_non_contradictory():
    result = evaluate_contradiction(
        "Acme Technologies was founded in 2015.",
        "Acme Technologies was founded in 2015.",
    )

    assert result.label == "NOT_CONTRADICTORY"
    assert result.contradictory is False


def test_unrelated_claims_remain_non_contradictory():
    result = evaluate_contradiction(
        "Acme Technologies has offices in Kigali.",
        "Acme Technologies was founded in 2015.",
    )

    assert result.label == "NOT_CONTRADICTORY"
    assert result.contradictory is False