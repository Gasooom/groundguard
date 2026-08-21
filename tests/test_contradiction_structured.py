from groundguard.domain.contradiction import (
    evaluate_contradiction,
)


def test_equivalent_bicycle_wording_is_not_contradictory():
    result = evaluate_contradiction(
        "NovaTech manufactures electric bikes.",
        "NovaTech manufactures electric bicycles and battery chargers.",
    )

    assert result.label == "NOT_CONTRADICTORY"


def test_partial_product_overlap_is_not_contradictory():
    result = evaluate_contradiction(
        (
            "Orion Labs sells project-management software, "
            "encrypted messaging tools, and accounting software."
        ),
        (
            "Orion Labs sells project-management software "
            "and encrypted messaging tools."
        ),
    )

    assert result.label == "NOT_CONTRADICTORY"


def test_semantically_equivalent_service_description_is_not_contradictory():
    result = evaluate_contradiction(
        (
            "NovaHealth provides software for monitoring "
            "patients remotely and scheduling appointments."
        ),
        (
            "NovaHealth provides remote patient monitoring "
            "and appointment scheduling software."
        ),
    )

    assert result.label == "NOT_CONTRADICTORY"


def test_same_product_with_different_additional_product_is_not_contradictory():
    result = evaluate_contradiction(
        (
            "DataWorks sells analytics dashboards, "
            "automated reporting software, and cybersecurity tools."
        ),
        (
            "DataWorks sells analytics dashboards "
            "and automated reporting software."
        ),
    )

    assert result.label == "NOT_CONTRADICTORY"


def test_conflicting_expansion_years_are_contradictory():
    result = evaluate_contradiction(
        (
            "Acme Technologies launched its platform in 2021 "
            "and expanded into Rwanda in 2022."
        ),
        (
            "Acme Technologies launched its platform in 2021 "
            "and expanded into Rwanda in 2023."
        ),
    )

    assert result.label == "CONTRADICTORY"


def test_conflicting_operating_locations_are_contradictory():
    result = evaluate_contradiction(
        "DataWorks operates in Rwanda and Tanzania.",
        "DataWorks operates in Rwanda, Kenya, and Uganda.",
    )

    assert result.label == "CONTRADICTORY"


def test_conflicting_capital_claims_are_contradictory():
    result = evaluate_contradiction(
        "Mombasa is the capital of Kenya.",
        "Kenya's capital city is Nairobi.",
    )

    assert result.label == "CONTRADICTORY"


def test_conflicting_employee_counts_are_contradictory():
    result = evaluate_contradiction(
        "NovaTech has 250 employees.",
        "NovaTech employs 120 people.",
    )

    assert result.label == "CONTRADICTORY"


def test_unrelated_product_claims_are_not_contradictory():
    result = evaluate_contradiction(
        "CloudCore sells accounting software.",
        "CloudCore sells backup software and cloud storage.",
    )

    assert result.label == "NOT_CONTRADICTORY"