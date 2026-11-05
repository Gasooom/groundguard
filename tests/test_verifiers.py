import pytest

from groundguard.core.types import Claim, EvidenceSpan, Span
from groundguard.domain.claims import similarity
from groundguard.verifiers.base import VerifierChain
from groundguard.verifiers.guards import GuardVerifier, _event_years
from groundguard.verifiers.lexical import LexicalVerifier
from groundguard.verifiers.structured_facts import StructuredFactsVerifier


def claim(text):
    return Claim(id="c1", text=text, answer_span=Span(0, len(text)), origin="sentence")


def evidence(*texts):
    return tuple(
        EvidenceSpan(source_id="ctx", span=Span(0, len(text)), text=text, retrieval_score=1.0)
        for text in texts
    )


GUARD = GuardVerifier()


@pytest.mark.parametrize(
    "claim_text, evidence_text, label, check",
    [
        ("Acme is not headquartered in Berlin", "Acme Corp is headquartered in Berlin, Germany", "CONTRADICTED", "negation"),
        ("The API supports batch requests", "The API doesn't support batch requests", "CONTRADICTED", "negation"),
        ("The plan includes 500 GB of storage", "The plan includes 50 GB of storage", "CONTRADICTED", "quantity"),
        ("Responses average 120 seconds", "Responses average 120 milliseconds", "CONTRADICTED", "quantity"),
        ("DataCore has 150 employees", "DataCore has 120 employees", "CONTRADICTED", "quantity"),
        ("The policy took effect in 2019", "The policy took effect on 1 March 2021", "CONTRADICTED", "date"),
        ("The office opened in 2019", "The office opened in 2015 and moved to Nairobi in 2019", "CONTRADICTED", "date"),
        ("Drug X is approved for children", "Drug X is approved only for adults", "CONTRADICTED", "qualifier"),
        ("Drug X is approved for children", "Drug X is approved for adults", "NOT_ENOUGH_INFO", "qualifier"),
        ("The discount applies to all plans", "The discount applies to some plans", "NOT_ENOUGH_INFO", "qualifier"),
    ],
)
def test_guards_fire_with_a_recorded_signal(claim_text, evidence_text, label, check):
    verdict = GUARD.verify(claim(claim_text), evidence(evidence_text))

    assert verdict is not None
    assert verdict.label == label
    assert check in verdict.signals["fired"]
    assert check in verdict.signals
    assert verdict.evidence[0].text == evidence_text
    assert verdict.verifier == "guards@2"


@pytest.mark.parametrize(
    "claim_text, evidence_text",
    [
        ("The service does not store card numbers", "The service does not store card numbers"),
        ("Acme is headquartered in Berlin", "Acme is headquartered in Berlin"),
        ("Storage is 1 GB", "Storage is 1000 MB"),                          # unit conversion
        ("The company employs about 1,200 people", "The company employs about 1200 people"),
        ("The discount applies to some plans", "The discount applies to all plans"),  # all entails some
        ("Version 2.0 shipped in 2023", "Version 2.0 shipped in 2023, after version 1.0"),
        ("Acme sells software", "Kenya is in East Africa"),                 # unrelated: no anchor
    ],
)
def test_guards_abstain_without_a_mismatch(claim_text, evidence_text):
    assert GUARD.verify(claim(claim_text), evidence(evidence_text)) is None


def test_guards_compare_against_the_best_matching_sentence_only():
    # The negated sentence is about hardware; the claim matches the second sentence.
    candidates = evidence("Acme does not sell hardware", "Acme sells software")
    assert GUARD.verify(claim("Acme sells software"), candidates) is None


def test_guards_ignore_multi_sentence_windows():
    candidates = evidence("Acme was founded in 2010. It does not sell hardware.")
    assert GUARD.verify(claim("Acme sells hardware"), candidates) is None


def test_guards_never_return_supported():
    verdict = GUARD.verify(claim("Acme is not in Berlin"), evidence("Acme is in Berlin"))
    assert verdict is not None and verdict.label != "SUPPORTED"


def test_event_years_bind_year_to_preceding_event_word():
    assert _event_years("The office opened in 2015 and moved to Nairobi in 2019") == {
        "open": {2015},
        "nairobi": {2019},
    }
    assert _event_years("It took effect on 1 March 2021") == {"effect": {2021}}


def test_lexical_content_mode_requires_full_coverage_by_default():
    verifier = LexicalVerifier()
    supported = verifier.verify(claim("Acme operates in Kenya"), evidence("Acme operates in Kenya and Uganda"))
    assert supported.label == "SUPPORTED"
    assert supported.raw_score == 1.0

    missing = verifier.verify(
        claim("Orion Labs sells accounting software"),
        evidence("Orion Labs sells project-management software"),
    )
    assert missing.label == "NOT_ENOUGH_INFO"
    assert missing.signals["uncovered"] == ["account"]


def test_lexical_threshold_is_configurable():
    candidates = evidence("Orion Labs sells project-management software")
    text = claim("Orion Labs sells accounting software")
    assert LexicalVerifier(threshold=0.8).verify(text, candidates).label == "SUPPORTED"
    assert LexicalVerifier(threshold=1.0).verify(text, candidates).label == "NOT_ENOUGH_INFO"


def test_lexical_v1_mode_matches_v1_similarity():
    text = "The meeting is on Monday at 10 a.m."
    source = "The meeting is scheduled for Monday at 10 a.m. in Room 4."
    verdict = LexicalVerifier(threshold=0.8, mode="v1").verify(claim(text), evidence(source))
    assert verdict.raw_score == pytest.approx(similarity(text, source))


def test_lexical_without_candidates_is_not_enough_info():
    verdict = LexicalVerifier().verify(claim("Acme sells software"), ())
    assert verdict.label == "NOT_ENOUGH_INFO"
    assert verdict.evidence == ()


def test_lexical_validates_configuration():
    with pytest.raises(ValueError):
        LexicalVerifier(threshold=0.0)
    with pytest.raises(ValueError):
        LexicalVerifier(mode="fuzzy")


def test_structured_facts_detects_single_valued_conflicts_only():
    verifier = StructuredFactsVerifier()

    conflict = verifier.verify(claim("Acme was founded in 2015."), evidence("Acme was founded in 2018."))
    assert conflict is not None and conflict.label == "CONTRADICTED"

    # Additive predicate: a different product is extra information, not a conflict.
    assert verifier.verify(claim("Acme sells routers."), evidence("Acme sells software.")) is None
    # Never returns SUPPORTED, even for an identical fact.
    assert verifier.verify(claim("Acme was founded in 2018."), evidence("Acme was founded in 2018.")) is None
    # Outside its predicate vocabulary it abstains.
    assert verifier.verify(claim("The sky is blue."), evidence("The sky is grey.")) is None


def test_chain_uses_first_non_abstaining_verifier():
    chain = VerifierChain((GuardVerifier(), StructuredFactsVerifier(), LexicalVerifier()))
    assert chain.ids == ("guards@2", "structured_facts@1", "lexical@1-content-1")

    contradicted = chain.verify(claim("Acme is not in Berlin"), evidence("Acme is in Berlin"))
    assert contradicted.verifier == "guards@2"

    supported = chain.verify(claim("Acme is in Berlin"), evidence("Acme is in Berlin"))
    assert (supported.label, supported.verifier) == ("SUPPORTED", "lexical@1-content-1")


def test_chain_requires_a_verifier():
    with pytest.raises(ValueError):
        VerifierChain(())


def test_guards_do_not_compare_sentences_that_share_only_the_subject():
    # guards@1 reported a false contradiction here: both sentences are about
    # Drug Q, but they state different facts (sales vs approval).
    candidates = evidence("Drug Q is not approved for children under 12")
    assert GUARD.verify(claim("Drug Q is sold in 40 countries"), candidates) is None


def test_guards_still_compare_when_the_predicate_is_shared():
    candidates = evidence("Drug Q is not approved for children under 12")
    verdict = GUARD.verify(claim("Drug Q is approved for children under 12"), candidates)
    assert verdict is not None and verdict.label == "CONTRADICTED"
