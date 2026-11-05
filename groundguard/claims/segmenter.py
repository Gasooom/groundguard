"""Deterministic, offset-preserving claim segmentation.

Granularities (each includes the previous one):

``sentence``
    Sentence boundaries, with protection for abbreviations, initials and
    decimal numbers.
``clause``
    Additionally splits on ``;`` and on contrastive coordinators
    (``but``, ``whereas``).
``conjunct``
    Additionally splits ``and``-coordinations: list items share the verb
    phrase prefix ("sells A, B, and C" → three claims), coordinated
    predicates share the subject ("has X and operates in Y"), and
    independent clauses are kept as they are. When the structure is unclear,
    the clause is left unsplit (conservative).

The decomposition exists for localization and explanation. Its effect on
accuracy is measured, not assumed (ADR-013).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from groundguard.claims.assertiveness import classify
from groundguard.core.types import Claim, Granularity, Span


ABBREVIATIONS = frozenset(
    {
        "a.m.", "p.m.", "e.g.", "i.e.", "etc.", "vs.", "approx.", "dr.", "mr.",
        "mrs.", "ms.", "prof.", "inc.", "ltd.", "co.", "corp.", "no.", "st.",
        "u.s.", "u.k.", "e.u.", "jan.", "feb.", "mar.", "apr.", "jun.", "jul.",
        "aug.", "sep.", "sept.", "oct.", "nov.", "dec.",
    }
)
# Abbreviations that commonly end a sentence; a following capital starts a new one.
SENTENCE_FINAL_ABBREVIATIONS = frozenset({"a.m.", "p.m.", "etc."})

AUXILIARIES = frozenset(
    {
        "is", "are", "was", "were", "be", "been", "has", "have", "had", "can",
        "could", "will", "would", "may", "might", "must", "shall", "should",
        "does", "do", "did",
    }
)

_TOKEN = re.compile(r"\S+")
_BOUNDARY = re.compile(r"[.!?]+(?=\s+|$)")


@dataclass(frozen=True)
class _Piece:
    start: int
    end: int
    question: bool = False


def _trim(text: str, start: int, end: int) -> _Piece | None:
    """Shrink [start, end) to exclude surrounding whitespace and a trailing
    sentence terminator or comma."""

    original_end = end
    while start < end and text[start].isspace():
        start += 1
    while True:
        previous = end
        while end > start and (text[end - 1].isspace() or text[end - 1] in ",;"):
            end -= 1
        if end > start and text[end - 1] in ".!?" and not _ends_with_abbreviation(text[start:end]):
            while end > start and text[end - 1] in ".!?":
                end -= 1
        if end == previous:
            break
    if end <= start:
        return None
    question = text[start:original_end].rstrip().endswith("?")
    return _Piece(start, end, question)


def _ends_with_abbreviation(text: str) -> bool:
    last = text.split()[-1].lower() if text.split() else ""
    return last in ABBREVIATIONS


def split_sentences(text: str) -> list[_Piece]:
    pieces: list[_Piece] = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        end = match.end()
        candidate = text[start:end]
        tokens = candidate.split()
        last = tokens[-1].lower() if tokens else ""
        following = text[end:].lstrip()
        next_char = following[:1]

        if next_char and not (next_char.isupper() or next_char.isdigit() or next_char in "\"'("):
            continue
        if last in ABBREVIATIONS and not (last in SENTENCE_FINAL_ABBREVIATIONS and next_char.isupper()):
            continue
        if re.fullmatch(r"[A-Z]\.", tokens[-1] if tokens else ""):
            continue  # an initial, as in "J. Smith"

        piece = _trim(text, start, end)
        if piece:
            pieces.append(piece)
        start = end

    piece = _trim(text, start, len(text))
    if piece:
        pieces.append(piece)
    return pieces


_CLAUSE_SPLIT = re.compile(r";\s*|,?\s+(?:but|whereas)\s+", re.IGNORECASE)


def split_clauses(text: str, sentence: _Piece) -> list[_Piece]:
    pieces: list[_Piece] = []
    cursor = sentence.start
    segment = text[sentence.start : sentence.end]
    for match in _CLAUSE_SPLIT.finditer(segment):
        piece = _trim(text, cursor, sentence.start + match.start())
        if piece:
            pieces.append(piece)
        cursor = sentence.start + match.end()
    piece = _trim(text, cursor, sentence.end)
    if piece:
        pieces.append(piece)
    if len(pieces) > 1 and any(len(_raw_tokens(text[p.start : p.end])) < 2 for p in pieces):
        return [sentence]  # a one-word fragment means the split was wrong
    return [_Piece(p.start, p.end, sentence.question) for p in pieces]


def _tokens(text: str) -> list[str]:
    return [token.strip(",.;:!?\"'()").lower() for token in text.split() if token.strip(",.;:!?\"'()")]


def _raw_tokens(text: str) -> list[str]:
    return [token for token in text.split() if token.strip(",.;:!?\"'()")]


def subject_prefix(text: str) -> str:
    """Words before the first verb-like word after the first token, e.g.
    "Drug Q is sold in 40 countries" -> "Drug Q". Empty if no verb is found."""

    raw = _raw_tokens(text)
    for index, token in enumerate(raw):
        if index > 0 and _verb_like(token):
            return " ".join(raw[:index])
    return ""


def _verb_like(token: str) -> bool:
    """Crude verb test: auxiliaries, or a lower-case word ending in -ed / -s."""

    if not token or not token[0].islower():
        return False
    word = token.strip(",.;:!?\"'()").lower()
    if word in AUXILIARIES:
        return True
    if len(word) <= 3:
        return False
    return word.endswith("ed") or (word.endswith("s") and not word.endswith(("ss", "us", "is")))


_AND = re.compile(r",?\s+and\s+", re.IGNORECASE)
_LIST = re.compile(r",\s+[^,]+,?\s+and\s+", re.IGNORECASE)


def _segments(text: str, clause: _Piece) -> list[_Piece]:
    body = text[clause.start : clause.end]
    if _LIST.search(body):
        separator = re.compile(r",?\s+and\s+|,\s+", re.IGNORECASE)
    else:
        separator = _AND
    pieces: list[_Piece] = []
    cursor = clause.start
    for match in separator.finditer(body):
        piece = _trim(text, cursor, clause.start + match.start())
        if piece:
            pieces.append(piece)
        cursor = clause.start + match.end()
    piece = _trim(text, cursor, clause.end)
    if piece:
        pieces.append(piece)
    return pieces


_CONNECTORS = frozenset(
    {"in", "into", "to", "for", "from", "at", "on", "with", "by", "of", "as", "a", "an", "the", "its", "their"}
)


def _verb_prefix(raw: list[str]) -> list[str] | None:
    """Tokens up to and including the main verb group and any following
    prepositions/determiners: "Acme operates in Kenya" → ["Acme", "operates", "in"]."""

    verb_index = next(
        (index for index, token in enumerate(raw) if index > 0 and _verb_like(token)),
        None,
    )
    if verb_index is None:
        return None
    end = verb_index + 1
    while end < len(raw) and _verb_like(raw[end]):
        end += 1  # "is headquartered", "has been acquired"
    while end < len(raw) and raw[end].lower() in _CONNECTORS:
        end += 1
    return raw[:end]


def _subject(raw: list[str]) -> list[str] | None:
    verb_index = next(
        (index for index, token in enumerate(raw) if index > 0 and _verb_like(token)),
        None,
    )
    if verb_index is None:
        return None
    subject = raw[:verb_index]
    while len(subject) > 1 and subject[-1].lower().endswith("ly"):
        subject = subject[:-1]  # drop trailing adverbs: "currently"
    return subject


def split_conjuncts(text: str, clause: _Piece) -> list[tuple[_Piece, str]]:
    """Return (span, claim text) pairs. Falls back to the whole clause."""

    whole = [(clause, text[clause.start : clause.end])]
    body = text[clause.start : clause.end]
    is_list = bool(_LIST.search(body))
    segments = _segments(text, clause)
    if len(segments) < 2:
        return whole

    first = segments[0]
    first_text = text[first.start : first.end]
    first_raw = _raw_tokens(first_text)
    if len(first_raw) < 2 or not any(_verb_like(token) for token in first_raw[1:]):
        return whole  # e.g. coordinated subjects: "Mercury and Venus are planets"

    prefix = _verb_prefix(first_raw)
    subject = _subject(first_raw)
    results: list[tuple[_Piece, str]] = [(first, first_text)]
    for segment in segments[1:]:
        segment_text = text[segment.start : segment.end]
        raw = _raw_tokens(segment_text)
        lowered = _tokens(segment_text)

        # Independent clause with its own subject and verb.
        if len(raw) >= 3 and any(token in AUXILIARIES for token in lowered[1:]):
            results.append((segment, segment_text))
            continue

        predicate = len(raw) >= 2 and _verb_like(raw[0]) and not is_list
        if predicate and subject:
            # Coordinated predicate: reuse the subject of the first segment.
            results.append((segment, " ".join(subject + raw)))
            continue

        if not predicate and prefix and len(prefix) < len(first_raw) and len(raw) <= 6:
            # List item: reuse the verb phrase prefix of the first segment.
            results.append((segment, " ".join(prefix + raw)))
            continue

        return whole
    return [(_Piece(piece.start, piece.end, clause.question), claim_text) for piece, claim_text in results]


def segment(answer: str, granularity: Granularity = "sentence") -> tuple[Claim, ...]:
    """Split an answer into claims with spans into ``answer``."""

    if granularity not in ("sentence", "clause", "conjunct"):
        raise ValueError(f"unknown granularity {granularity!r}")

    claims: list[Claim] = []
    for sentence in split_sentences(answer):
        clauses = [sentence] if granularity == "sentence" else split_clauses(answer, sentence)
        for clause in clauses:
            if granularity == "conjunct":
                parts = split_conjuncts(answer, clause)
                origin = "conjunct" if len(parts) > 1 else ("clause" if len(clauses) > 1 else "sentence")
            else:
                parts = [(clause, answer[clause.start : clause.end])]
                origin = "clause" if len(clauses) > 1 else "sentence"

            for piece, claim_text in parts:
                assessment = classify(claim_text, question=piece.question)
                span = Span(piece.start, piece.end)
                if assessment.strip_prefix:
                    # Only move the span when the claim text is a verbatim slice
                    # of the answer; synthesized conjunct text keeps its span.
                    verbatim = claim_text == answer[piece.start : piece.end]
                    claim_text = claim_text[assessment.strip_prefix :]
                    if verbatim:
                        span = Span(piece.start + assessment.strip_prefix, piece.end)
                claims.append(
                    Claim(
                        id=f"c{len(claims) + 1}",
                        text=claim_text.strip(),
                        answer_span=span,
                        origin=origin,  # type: ignore[arg-type]
                        assertive=assessment.assertive,
                        non_assertive_reason=assessment.reason,
                    )
                )
    return tuple(claims)
