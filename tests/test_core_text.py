import pytest

from groundguard.core.text import content_tokens, is_negated, overlap, quantities, stem
from groundguard.core.types import Span


def _q(text):
    return [(q.value, q.unit, q.kind) for q in quantities(text)]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("The company employs about 1,200 people.", [(1200.0, None, "number")]),
        ("Battery life is up to ten hours.", [(10.0, "h", "quantity")]),
        ("The plan includes 50 GB of storage.", [(50.0, "gb", "quantity")]),
        ("Responses average 120 milliseconds.", [(120.0, "ms", "quantity")]),
        ("It weighs 1.2 kilograms.", [(1.2, "kg", "quantity")]),
        ("It costs $5 or 30%.", [(5.0, "usd", "quantity"), (30.0, "percent", "quantity")]),
        ("It took effect in 2021.", [(2021.0, None, "year")]),
        ("Version 2.0 was released in 2023.", [(2023.0, None, "year")]),
        ("The meeting is at 10 a.m.", [(10.0, None, "number")]),
        ("No numbers here.", []),
    ],
)
def test_quantities(text, expected):
    assert _q(text) == expected


def test_quantity_offsets_point_at_raw_text():
    text = "Storage is 50 GB per user."
    (quantity,) = quantities(text)
    assert text[quantity.start : quantity.end] == quantity.raw == "50 GB"


@pytest.mark.parametrize(
    "text, negated",
    [
        ("The API does not support batch requests.", True),
        ("The API doesn't support batch requests.", True),
        ("The library never sends telemetry.", True),
        ("Refunds are available without a receipt.", True),
        ("The API supports batch requests.", False),
        ("Nothing is stored.", True),
    ],
)
def test_is_negated(text, negated):
    assert is_negated(text) is negated


def test_content_tokens_drop_stop_and_negation_words_and_canonicalize_numbers():
    assert content_tokens("The API doesn't support twenty batch requests.") == [
        "api", "support", "20", "batch", "request",
    ]
    assert content_tokens("about 1,200 people") == ["1200", "people"]


def test_overlap_ignores_polarity_by_design():
    # Polarity is checked by the guards, not by lexical overlap.
    assert overlap("Acme is not headquartered in Berlin.", "Acme is headquartered in Berlin.") == 1.0
    assert overlap("", "anything") == 0.0


@pytest.mark.parametrize(
    "token, expected",
    [("requests", "request"), ("companies", "company"), ("founded", "found"),
     ("operating", "operat"), ("class", "class"), ("status", "status"), ("is", "is"), ("2021", "2021")],
)
def test_stem(token, expected):
    assert stem(token) == expected


def test_span_validation():
    assert Span(0, 0).to_dict() == {"start": 0, "end": 0}
    with pytest.raises(ValueError):
        Span(3, 2)
    with pytest.raises(ValueError):
        Span(-1, 2)
