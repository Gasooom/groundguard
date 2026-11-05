"""Okapi BM25 evidence selection, pure Python."""

from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

from groundguard.core.text import content_tokens
from groundguard.core.types import EvidenceSpan
from groundguard.evidence.chunking import Chunk


class BM25:
    """BM25 with the non-negative IDF variant ``log(1 + (N - n + 0.5) / (n + 0.5))``."""

    def __init__(self, documents: Sequence[Sequence[str]], *, k1: float = 1.5, b: float = 0.75) -> None:
        if k1 < 0 or not 0.0 <= b <= 1.0:
            raise ValueError("require k1 >= 0 and 0 <= b <= 1")
        self.k1 = k1
        self.b = b
        self.frequencies = [Counter(document) for document in documents]
        self.lengths = [len(document) for document in documents]
        self.average_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        document_frequency: Counter[str] = Counter()
        for frequency in self.frequencies:
            document_frequency.update(frequency.keys())
        total = len(self.frequencies)
        self.idf = {
            term: math.log(1.0 + (total - count + 0.5) / (count + 0.5))
            for term, count in document_frequency.items()
        }

    def score(self, query: Sequence[str], index: int) -> float:
        frequency = self.frequencies[index]
        length = self.lengths[index]
        norm = 1.0 - self.b + self.b * (length / self.average_length if self.average_length else 0.0)
        total = 0.0
        for term in set(query):
            tf = frequency.get(term, 0)
            if tf == 0:
                continue
            total += self.idf[term] * tf * (self.k1 + 1.0) / (tf + self.k1 * norm)
        return total


def select_evidence(
    claim_text: str,
    chunks: Sequence[Chunk],
    *,
    top_k: int = 5,
) -> tuple[EvidenceSpan, ...]:
    """Rank chunks for a claim. Ties keep document order. Zero scores are dropped."""

    if top_k < 1:
        raise ValueError("top_k must be positive")
    if not chunks:
        return ()

    index = BM25([content_tokens(chunk.text) for chunk in chunks])
    query = content_tokens(claim_text)
    scored = [(index.score(query, position), position) for position in range(len(chunks))]
    ranked = sorted((item for item in scored if item[0] > 0), key=lambda item: (-item[0], item[1]))

    return tuple(
        EvidenceSpan(
            source_id=chunks[position].source_id,
            span=chunks[position].span,
            text=chunks[position].text,
            retrieval_score=score,
        )
        for score, position in ranked[:top_k]
    )
