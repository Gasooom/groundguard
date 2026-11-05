import math

import pytest

from groundguard.core.types import SourceDocument
from groundguard.evidence.bm25 import BM25, select_evidence
from groundguard.evidence.chunking import chunk_sources


def test_chunks_are_sentences_and_adjacent_pairs_with_offsets():
    source = SourceDocument("doc-1", "Acme was founded in 2010. It is based in Berlin. It sells tools.")
    chunks = chunk_sources([source])

    texts = [chunk.text for chunk in chunks]
    assert texts == [
        "Acme was founded in 2010",
        "It is based in Berlin",
        "It sells tools",
        "Acme was founded in 2010. It is based in Berlin",
        "It is based in Berlin. It sells tools",
    ]
    for chunk in chunks:
        assert source.text[chunk.span.start : chunk.span.end] == chunk.text
        assert chunk.source_id == "doc-1"


def test_chunking_validates_window_sizes():
    with pytest.raises(ValueError):
        chunk_sources([SourceDocument("d", "x.")], window_sizes=(0,))


def test_bm25_matches_hand_computed_value():
    documents = [["acme", "berlin"], ["acme", "tool", "tool"], ["kenya"]]
    index = BM25(documents, k1=1.5, b=0.75)

    # term "tool": n=1, N=3 -> idf = ln(1 + 2.5/1.5)
    idf = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))
    average = 6 / 3
    norm = 1 - 0.75 + 0.75 * (3 / average)
    expected = idf * 2 * 2.5 / (2 + 1.5 * norm)
    assert index.score(["tool"], 1) == pytest.approx(expected)
    assert index.score(["tool"], 0) == 0.0


def test_bm25_rewards_rarer_terms():
    index = BM25([["acme", "berlin"], ["acme", "kenya"], ["acme", "uganda"]])
    assert index.score(["berlin"], 0) > index.score(["acme"], 0)


def test_select_evidence_ranks_and_drops_zero_scores():
    source = SourceDocument(
        "ctx",
        "Refunds are available within 30 days. Shipping takes five days. Digital goods are excluded from refunds.",
    )
    chunks = chunk_sources([source], window_sizes=(1,))
    evidence = select_evidence("Can digital goods be refunded?", chunks, top_k=5)

    assert evidence[0].text == "Digital goods are excluded from refunds"
    assert all(item.retrieval_score > 0 for item in evidence)
    assert "Shipping takes five days" not in [item.text for item in evidence]


def test_select_evidence_edge_cases():
    assert select_evidence("anything", []) == ()
    with pytest.raises(ValueError):
        select_evidence("x", [], top_k=0)
