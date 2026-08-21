from groundguard.domain.propositions import (
    Proposition,
    extract_propositions,
)


def test_extract_manufactures():
    propositions = extract_propositions(
        "NovaTech manufactures electric bikes."
    )

    assert propositions == [
        Proposition(
            subject="NovaTech",
            predicate="manufactures",
            object="electric bikes",
            attributes={},
        )
    ]


def test_extract_operating_locations():
    propositions = extract_propositions(
        "DataWorks operates in Rwanda, Kenya, and Uganda."
    )

    assert propositions == [
        Proposition(
            subject="DataWorks",
            predicate="operates_in",
            object="Rwanda",
            attributes={},
        ),
        Proposition(
            subject="DataWorks",
            predicate="operates_in",
            object="Kenya",
            attributes={},
        ),
        Proposition(
            subject="DataWorks",
            predicate="operates_in",
            object="Uganda",
            attributes={},
        ),
    ]


def test_extract_employee_count():
    propositions = extract_propositions(
        "NovaTech has 120 employees."
    )

    assert propositions == [
        Proposition(
            subject="NovaTech",
            predicate="has_employees",
            object="120",
            attributes={},
        )
    ]


def test_extract_employed_people():
    propositions = extract_propositions(
        "NovaTech employs 120 people."
    )

    assert propositions == [
        Proposition(
            subject="NovaTech",
            predicate="has_employees",
            object="120",
            attributes={},
        )
    ]


def test_extract_launch_and_expansion():
    propositions = extract_propositions(
        "Acme Technologies launched its platform in 2021 "
        "and expanded into Rwanda in 2022."
    )

    assert propositions == [
        Proposition(
            subject="Acme Technologies",
            predicate="launched",
            object="platform",
            attributes={"year": "2021"},
        ),
        Proposition(
            subject="Acme Technologies",
            predicate="expanded_into",
            object="Rwanda",
            attributes={"year": "2022"},
        ),
    ]


def test_extract_capital():
    propositions = extract_propositions(
        "Kenya's capital city is Nairobi."
    )

    assert propositions == [
        Proposition(
            subject="Kenya",
            predicate="capital_city",
            object="Nairobi",
            attributes={},
        )
    ]


def test_extract_founded_year():
    propositions = extract_propositions(
        "Acme Technologies was founded in 2018."
    )

    assert propositions == [
        Proposition(
            subject="Acme Technologies",
            predicate="founded",
            object="company",
            attributes={"year": "2018"},
        )
    ]


def test_extract_office_count():
    propositions = extract_propositions(
        "Orion Labs has five offices."
    )

    assert propositions == [
        Proposition(
            subject="Orion Labs",
            predicate="has_offices",
            object="5",
            attributes={},
        )
    ]


def test_extract_headquarters():
    propositions = extract_propositions(
        "NovaTech is headquartered in Nairobi."
    )

    assert propositions == [
        Proposition(
            subject="NovaTech",
            predicate="headquartered_in",
            object="Nairobi",
            attributes={},
        )
    ]


def test_extract_revenue():
    propositions = extract_propositions(
        "NovaTech generated $40 million in revenue in 2023."
    )

    assert propositions == [
        Proposition(
            subject="NovaTech",
            predicate="revenue",
            object="40 million",
            attributes={"year": "2023"},
        )
    ]


def test_extract_composition():
    propositions = extract_propositions(
        "Water consists of two hydrogen atoms and one oxygen atom."
    )

    assert propositions == [
        Proposition(
            subject="Water",
            predicate="composition",
            object="two hydrogen atoms and one oxygen atom",
            attributes={},
        )
    ]