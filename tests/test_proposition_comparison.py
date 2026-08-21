from groundguard.domain.propositions import Proposition
from groundguard.domain.proposition_comparison import (
    compare_propositions,
)


def test_identical_propositions_are_same():
    result = compare_propositions(
        Proposition(
            subject="NovaTech",
            predicate="manufactures",
            object="electric bikes",
            attributes={},
        ),
        Proposition(
            subject="NovaTech",
            predicate="manufactures",
            object="electric bikes",
            attributes={},
        ),
    )

    assert result == "SAME"


def test_paraphrased_product_propositions_are_same():
    result = compare_propositions(
        Proposition(
            subject="NovaTech",
            predicate="manufactures",
            object="electric bikes",
            attributes={},
        ),
        Proposition(
            subject="NovaTech",
            predicate="manufactures",
            object="electric bicycles",
            attributes={},
        ),
    )

    assert result == "SAME"


def test_different_products_are_unrelated():
    result = compare_propositions(
        Proposition(
            subject="CloudCore",
            predicate="sells",
            object="accounting software",
            attributes={},
        ),
        Proposition(
            subject="CloudCore",
            predicate="sells",
            object="backup software",
            attributes={},
        ),
    )

    assert result == "UNRELATED"


def test_different_locations_are_conflicting():
    result = compare_propositions(
        Proposition(
            subject="DataWorks",
            predicate="operates_in",
            object="Tanzania",
            attributes={},
        ),
        Proposition(
            subject="DataWorks",
            predicate="operates_in",
            object="Kenya",
            attributes={},
        ),
    )

    assert result == "CONFLICTING"


def test_different_employee_counts_are_conflicting():
    result = compare_propositions(
        Proposition(
            subject="NovaTech",
            predicate="has_employees",
            object="250",
            attributes={},
        ),
        Proposition(
            subject="NovaTech",
            predicate="has_employees",
            object="120",
            attributes={},
        ),
    )

    assert result == "CONFLICTING"


def test_different_capitals_are_conflicting():
    result = compare_propositions(
        Proposition(
            subject="Kenya",
            predicate="capital_city",
            object="Mombasa",
            attributes={},
        ),
        Proposition(
            subject="Kenya",
            predicate="capital_city",
            object="Nairobi",
            attributes={},
        ),
    )

    assert result == "CONFLICTING"


def test_different_years_for_same_expansion_are_conflicting():
    result = compare_propositions(
        Proposition(
            subject="Acme Technologies",
            predicate="expanded_into",
            object="Rwanda",
            attributes={"year": "2022"},
        ),
        Proposition(
            subject="Acme Technologies",
            predicate="expanded_into",
            object="Rwanda",
            attributes={"year": "2023"},
        ),
    )

    assert result == "CONFLICTING"


def test_different_predicates_are_unrelated():
    result = compare_propositions(
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
    )

    assert result == "UNRELATED"


def test_different_subjects_are_unrelated():
    result = compare_propositions(
        Proposition(
            subject="NovaTech",
            predicate="has_employees",
            object="120",
            attributes={},
        ),
        Proposition(
            subject="DataWorks",
            predicate="has_employees",
            object="120",
            attributes={},
        ),
    )

    assert result == "UNRELATED"