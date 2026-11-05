"""Split source documents into sentence windows that keep their offsets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from groundguard.claims.segmenter import split_sentences
from groundguard.core.types import SourceDocument, Span


_REFERRING = re.compile(
    r"^(?:it|its|they|their|them|this|these|that|those|he|she|his|her|the company|the firm)\b",
    re.IGNORECASE,
)


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

    Multi-sentence windows exist for coreference ("GroundGuard evaluates
    answers. It reports verdicts."), so a window is only created when every
    sentence after the first opens with a referring word. Pooling tokens from
    unrelated neighbouring sentences would let a claim borrow support from
    sentences about something else.
    """

    if not window_sizes or any(size < 1 for size in window_sizes):
        raise ValueError("window_sizes must contain positive integers")

    chunks: list[Chunk] = []
    for source in sources:
        sentences = split_sentences(source.text)
        for size in sorted(set(window_sizes)):
            for index in range(len(sentences) - size + 1):
                window = sentences[index : index + size]
                if size > 1 and not all(
                    _REFERRING.match(source.text[part.start : part.end]) for part in window[1:]
                ):
                    continue
                first, last = window[0], window[-1]
                span = Span(first.start, last.end)
                chunks.append(
                    Chunk(source.id, span, source.text[span.start : span.end], size)
                )
    return tuple(chunks)
