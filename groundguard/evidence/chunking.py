"""Split source documents into sentence windows that keep their offsets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from groundguard.claims.segmenter import split_sentences
from groundguard.core.types import SourceDocument, Span


@dataclass(frozen=True)
class Chunk:
    source_id: str
    span: Span
    text: str
    sentences: int   # 1 for single sentences, 2 for adjacent pairs


def chunk_sources(
    sources: Sequence[SourceDocument],
    *,
    window_sizes: tuple[int, ...] = (1, 2),
) -> tuple[Chunk, ...]:
    """Single sentences plus windows of adjacent sentences.

    Pair windows let a claim be supported by two consecutive sentences
    ("It was founded in 2010. It is based in Berlin." with a pronoun subject).
    """

    if not window_sizes or any(size < 1 for size in window_sizes):
        raise ValueError("window_sizes must contain positive integers")

    chunks: list[Chunk] = []
    for source in sources:
        sentences = split_sentences(source.text)
        for size in sorted(set(window_sizes)):
            for index in range(len(sentences) - size + 1):
                first, last = sentences[index], sentences[index + size - 1]
                span = Span(first.start, last.end)
                chunks.append(
                    Chunk(source.id, span, source.text[span.start : span.end], size)
                )
    return tuple(chunks)
