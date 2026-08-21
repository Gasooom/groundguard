from groundguard.domain.grounding import GroundingResult


def test_grounding_result():
    result = GroundingResult(
        score=1.0,
        grounded=True,
        evidence=["The university was established in 1997."],
    )

    assert result.score == 1.0
    assert result.grounded is True
    assert len(result.evidence) == 1