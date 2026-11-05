import random

import pytest

from groundguard.claims.assertiveness import classify
from groundguard.claims.segmenter import segment, split_sentences


def _texts(answer, granularity="conjunct"):
    return [claim.text for claim in segment(answer, granularity)]


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("Acme was founded in 2018. It sells software.", ["Acme was founded in 2018", "It sells software"]),
        ("The meeting is at 10 a.m. in Room 4.", ["The meeting is at 10 a.m. in Room 4"]),
        ("The meeting is at 10 a.m. It is in Room 4.", ["The meeting is at 10 a.m.", "It is in Room 4"]),
        ("Version 2.0 shipped in 2023.", ["Version 2.0 shipped in 2023"]),
        ("Dr. Smith leads the team, e.g. on audits.", ["Dr. Smith leads the team, e.g. on audits"]),
        ("J. Smith founded Acme.", ["J. Smith founded Acme"]),
        ("Is it free? Yes.", ["Is it free", "Yes"]),
        ("", []),
    ],
)
def test_sentence_segmentation(answer, expected):
    assert _texts(answer, "sentence") == expected


def test_clause_segmentation_splits_on_semicolons_and_contrast():
    assert _texts("Acme is cheap; it is also fast.", "clause") == ["Acme is cheap", "it is also fast"]
    assert _texts("Acme is cheap but it is slow.", "clause") == ["Acme is cheap", "it is slow"]
    # One-word fragments mean the split was wrong: keep the sentence whole.
    assert _texts("Acme is slow, but reliable.", "clause") == ["Acme is slow, but reliable"]


@pytest.mark.parametrize(
    "answer, expected",
    [
        (
            "Orion Labs sells project-management software, encrypted messaging tools, and accounting software.",
            [
                "Orion Labs sells project-management software",
                "Orion Labs sells encrypted messaging tools",
                "Orion Labs sells accounting software",
            ],
        ),
        (
            "DataCore has 120 employees and operates in five countries.",
            ["DataCore has 120 employees", "DataCore operates in five countries"],
        ),
        (
            "Acme Technologies launched its platform in 2021 and expanded into Rwanda in 2022.",
            ["Acme Technologies launched its platform in 2021", "Acme Technologies expanded into Rwanda in 2022"],
        ),
        ("Acme operates in Kenya and Uganda.", ["Acme operates in Kenya", "Acme operates in Uganda"]),
        (
            "The museum is open Tuesday to Sunday and admission is free on Fridays.",
            ["The museum is open Tuesday to Sunday", "admission is free on Fridays"],
        ),
        (
            "The United Nations currently has 193 Member States and was founded in 1945.",
            ["The United Nations currently has 193 Member States", "The United Nations was founded in 1945"],
        ),
        # Conservative fallbacks: structure unclear, keep the clause whole.
        ("Mercury and Venus are planets.", ["Mercury and Venus are planets"]),
        (
            "Earth's atmosphere consists mainly of nitrogen and oxygen, with nitrogen accounting for about 78 percent.",
            ["Earth's atmosphere consists mainly of nitrogen and oxygen, with nitrogen accounting for about 78 percent"],
        ),
    ],
)
def test_conjunct_segmentation(answer, expected):
    assert _texts(answer) == expected


def test_conjunct_claims_point_at_their_answer_slice():
    answer = "Acme operates in Kenya and Uganda."
    first, second = segment(answer, "conjunct")
    assert answer[first.answer_span.start : first.answer_span.end] == "Acme operates in Kenya"
    assert answer[second.answer_span.start : second.answer_span.end] == "Uganda"
    assert second.text == "Acme operates in Uganda"
    assert (first.origin, second.origin) == ("conjunct", "conjunct")


def test_non_assertive_text_is_kept_but_marked():
    claims = segment("Version 2.0 was released in 2023. Is that right? I'm not sure about the date.")
    assert [(c.assertive, c.non_assertive_reason) for c in claims] == [
        (True, None),
        (False, "question"),
        (False, "hedge_or_abstention"),
    ]


def test_meta_prefix_is_stripped_and_span_moves():
    answer = "Based on the context, the warranty lasts two years."
    (claim,) = segment(answer)
    assert claim.text == "the warranty lasts two years"
    assert answer[claim.answer_span.start : claim.answer_span.end] == claim.text


@pytest.mark.parametrize(
    "text, assertive",
    [
        ("According to the provided documents, Acme is in Berlin", True),
        ("The context does not mention the founding date", False),
        ("I don't know", False),
        ("Acme is in Berlin", True),
    ],
)
def test_classify(text, assertive):
    assert classify(text).assertive is assertive


def test_claim_ids_are_sequential():
    claims = segment("A sells x. B sells y and z.")
    assert [claim.id for claim in claims] == [f"c{i}" for i in range(1, len(claims) + 1)]


def test_unknown_granularity_raises():
    with pytest.raises(ValueError):
        segment("Acme sells software.", "word")


_VOCABULARY = (
    "Acme sells software and hardware . It was founded in 2018 ; but it is small , "
    "and operates in Kenya , Uganda , and Rwanda . Is it profitable ? 10 a.m. Dr. "
    "Smith v2.0 1,200 people e.g. not never"
).split()


@pytest.mark.parametrize("granularity", ["sentence", "clause", "conjunct"])
def test_property_spans_always_map_into_the_answer(granularity):
    rng = random.Random(1234)
    for _ in range(500):
        answer = " ".join(rng.choice(_VOCABULARY) for _ in range(rng.randint(0, 30)))
        previous_end = -1
        for claim in segment(answer, granularity):
            span = claim.answer_span
            assert 0 <= span.start < span.end <= len(answer)
            sliced = answer[span.start : span.end]
            assert sliced == sliced.strip() and sliced
            assert span.start >= previous_end - 0  # claims are in answer order, non-overlapping
            previous_end = span.end
            assert claim.text


def test_split_sentences_covers_text_without_gaps_in_content():
    text = "One. Two! Three? Four"
    pieces = split_sentences(text)
    assert [text[p.start : p.end] for p in pieces] == ["One", "Two", "Three", "Four"]
    assert [p.question for p in pieces] == [False, False, True, False]
