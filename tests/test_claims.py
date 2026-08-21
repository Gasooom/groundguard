from groundguard.domain.claims import ClaimResult


def test_claim_result():
    result = ClaimResult(
        claim="Acme was founded in 2018.",
        evidence=["Acme was founded in 2018."],
        score=1.0,
        supported=True,
    )

    assert result.claim == "Acme was founded in 2018."
    assert result.evidence == [
        "Acme was founded in 2018."
    ]
    assert result.score == 1.0
    assert result.supported is True
    
from groundguard.domain.claims import (
    ClaimResult,
    evaluate_claims,
)


def test_claim_result():
    result = ClaimResult(
        claim="Acme was founded in 2018.",
        evidence=["Acme was founded in 2018."],
        score=1.0,
        supported=True,
    )

    assert result.claim == "Acme was founded in 2018."
    assert result.evidence == [
        "Acme was founded in 2018."
    ]
    assert result.score == 1.0
    assert result.supported is True


def test_evaluate_supported_claim():
    results = evaluate_claims(
        "Acme Technologies was founded in 2018.",
        "Acme Technologies was founded in 2018.",
    )

    assert len(results) == 1

    result = results[0]

    assert result.claim == (
        "Acme Technologies was founded in 2018."
    )
    assert result.supported is True
    assert result.score == 1.0
    assert result.evidence


def test_evaluate_unsupported_claim():
    results = evaluate_claims(
        "Acme Technologies was founded in 2018.",
        "Acme Technologies was founded in 2015.",
    )

    assert len(results) == 1
    assert results[0].supported is False    