"""Claim-level datasets (gg-claims-v2 format): records, validation, freezing.

One JSON object per line. Each record holds sources with provenance, an
answer, gold claims with spans, labels and exact evidence quotes, answer-level
relevance and completeness, and an annotation block that tracks who drafted
and who reviewed it.

Review gate: only records with ``annotation.status == "LABELED"`` (reviewed
by a person) can enter a frozen split. Drafts written by an AI assistant
stay ``NEEDS_REVIEW`` until a person reviews them
(docs/EVALUATION_METHODOLOGY.md §6).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence

from groundguard.bench.errors import DatasetError
from groundguard.core.serialization import canonical_json
from groundguard.core.types import VERDICT_LABELS


RECORD_SCHEMA_VERSION = 1

# Reserved drafter id for records written by an AI assistant. It can draft,
# never review.
AI_DRAFTER = "ai-assistant"

AnnotationStatus = Literal["DRAFT", "NEEDS_REVIEW", "LABELED", "EXCLUDED"]
ANNOTATION_STATUSES: tuple[AnnotationStatus, ...] = ("DRAFT", "NEEDS_REVIEW", "LABELED", "EXCLUDED")
ANSWER_ORIGINS = ("ai_drafted", "perturbation", "human_written")
LABEL_BASES = ("construction", "judgment")
DOMAINS = ("health", "finance", "science")
RELEVANCE = ("RELEVANT", "IRRELEVANT")
COMPLETENESS = ("COMPLETE", "INCOMPLETE", "NOT_ASSESSED")
PHENOMENA = (
    "negation", "qualifier", "number", "unit", "date", "paraphrase", "coreference",
    "list_exhaustiveness", "entity_confusion", "superlative", "multi_source", "none",
)

_RECORD_KEYS = {
    "schema_version", "id", "context_group", "domain", "question", "sources", "answer",
    "answer_origin", "perturbation", "claims", "relevance", "completeness", "annotation",
}
_SOURCE_KEYS = {"id", "text", "url", "publisher", "title", "retrieved_at", "license"}
_CLAIM_KEYS = {"id", "text", "answer_span", "label", "evidence", "phenomena"}
_EVIDENCE_KEYS = {"source_id", "quote"}
_ANNOTATION_KEYS = {
    "status", "drafted_by", "label_basis", "reviewed_by", "reviewed_at", "notes", "uncertain",
}


@dataclass(frozen=True)
class GoldEvidence:
    source_id: str
    quote: str


@dataclass(frozen=True)
class GoldClaim:
    id: str
    text: str
    answer_span: tuple[int, int]
    label: str
    evidence: tuple[GoldEvidence, ...]
    phenomena: tuple[str, ...]


@dataclass(frozen=True)
class GoldSource:
    id: str
    text: str
    url: str
    publisher: str
    title: str
    retrieved_at: str
    license: str


@dataclass(frozen=True)
class ClaimRecord:
    id: str
    context_group: str
    domain: str
    question: str
    sources: tuple[GoldSource, ...]
    answer: str
    answer_origin: str
    claims: tuple[GoldClaim, ...]
    relevance: str
    completeness: str
    status: str
    raw: dict[str, Any]

    @property
    def is_good(self) -> bool:
        """acceptability@1 (methodology §3.3), without the safety term:
        every claim SUPPORTED and the answer relevant."""

        return self.relevance == "RELEVANT" and all(claim.label == "SUPPORTED" for claim in self.claims)


def _require(table: Any, keys: set[str], where: str, optional: frozenset[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(table, dict):
        raise DatasetError(f"{where}: expected an object")
    unknown = sorted(set(table) - keys - optional)
    missing = sorted(keys - set(table))
    if unknown:
        raise DatasetError(f"{where}: unknown keys {unknown}")
    if missing:
        raise DatasetError(f"{where}: missing keys {missing}")
    return table


def _one_of(value: Any, allowed: Sequence[str], where: str) -> str:
    if value not in allowed:
        raise DatasetError(f"{where}: {value!r} not in {list(allowed)}")
    return str(value)


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DatasetError(f"{where}: must be a non-empty string")
    return value


def parse_record(raw: dict[str, Any], *, line: int | str = "?") -> ClaimRecord:
    """Validate one record. Every structural rule raises with the record id."""

    where = f"line {line}"
    _require(raw, _RECORD_KEYS, where)
    record_id = _text(raw["id"], f"{where}.id")
    where = record_id
    if raw["schema_version"] != RECORD_SCHEMA_VERSION:
        raise DatasetError(f"{where}: schema_version must be {RECORD_SCHEMA_VERSION}")

    sources: list[GoldSource] = []
    if not isinstance(raw["sources"], list) or not raw["sources"]:
        raise DatasetError(f"{where}.sources: must be a non-empty list")
    for index, item in enumerate(raw["sources"]):
        sw = f"{where}.sources[{index}]"
        _require(item, _SOURCE_KEYS, sw)
        sources.append(GoldSource(**{key: _text(item[key], f"{sw}.{key}") for key in _SOURCE_KEYS}))
    source_text = {source.id: source.text for source in sources}
    if len(source_text) != len(sources):
        raise DatasetError(f"{where}.sources: duplicate source ids")

    answer = _text(raw["answer"], f"{where}.answer")
    claims: list[GoldClaim] = []
    if not isinstance(raw["claims"], list) or not raw["claims"]:
        raise DatasetError(f"{where}.claims: must be a non-empty list")
    for index, item in enumerate(raw["claims"]):
        cw = f"{where}.claims[{index}]"
        _require(item, _CLAIM_KEYS, cw)
        span = item["answer_span"]
        if (
            not isinstance(span, list) or len(span) != 2
            or not all(isinstance(v, int) for v in span)
            or not 0 <= span[0] < span[1] <= len(answer)
        ):
            raise DatasetError(f"{cw}.answer_span: must be [start, end) inside the answer")
        label = _one_of(item["label"], VERDICT_LABELS, f"{cw}.label")
        evidence: list[GoldEvidence] = []
        for e_index, ev in enumerate(item["evidence"]):
            ew = f"{cw}.evidence[{e_index}]"
            _require(ev, _EVIDENCE_KEYS, ew)
            if ev["source_id"] not in source_text:
                raise DatasetError(f"{ew}.source_id: unknown source {ev['source_id']!r}")
            quote = _text(ev["quote"], f"{ew}.quote")
            if quote not in source_text[ev["source_id"]]:
                raise DatasetError(f"{ew}.quote: not an exact substring of source {ev['source_id']!r}")
            evidence.append(GoldEvidence(ev["source_id"], quote))
        if label in ("SUPPORTED", "CONTRADICTED") and not evidence:
            raise DatasetError(f"{cw}: {label} claims need at least one evidence quote")
        phenomena = item["phenomena"]
        if not isinstance(phenomena, list) or not phenomena:
            raise DatasetError(f"{cw}.phenomena: must be a non-empty list")
        for phenomenon in phenomena:
            _one_of(phenomenon, PHENOMENA, f"{cw}.phenomena")
        claims.append(
            GoldClaim(
                id=_text(item["id"], f"{cw}.id"),
                text=_text(item["text"], f"{cw}.text"),
                answer_span=(span[0], span[1]),
                label=label,
                evidence=tuple(evidence),
                phenomena=tuple(phenomena),
            )
        )
    if len({claim.id for claim in claims}) != len(claims):
        raise DatasetError(f"{where}.claims: duplicate claim ids")

    annotation = _require(raw["annotation"], _ANNOTATION_KEYS, f"{where}.annotation")
    status = _one_of(annotation["status"], ANNOTATION_STATUSES, f"{where}.annotation.status")
    _one_of(annotation["label_basis"], LABEL_BASES, f"{where}.annotation.label_basis")
    _text(annotation["drafted_by"], f"{where}.annotation.drafted_by")
    if not isinstance(annotation["uncertain"], bool):
        raise DatasetError(f"{where}.annotation.uncertain: must be true or false")
    if status == "LABELED":
        _text(annotation["reviewed_by"], f"{where}.annotation.reviewed_by")
        _text(annotation["reviewed_at"], f"{where}.annotation.reviewed_at")
        if annotation["reviewed_by"] == AI_DRAFTER:
            raise DatasetError(f"{where}.annotation.reviewed_by: reviews must be by a person")

    origin = _one_of(raw["answer_origin"], ANSWER_ORIGINS, f"{where}.answer_origin")
    if origin == "perturbation" and not isinstance(raw["perturbation"], dict):
        raise DatasetError(f"{where}.perturbation: perturbed answers must describe the perturbation")

    return ClaimRecord(
        id=record_id,
        context_group=_text(raw["context_group"], f"{where}.context_group"),
        domain=_one_of(raw["domain"], DOMAINS, f"{where}.domain"),
        question=_text(raw["question"], f"{where}.question"),
        sources=tuple(sources),
        answer=answer,
        answer_origin=origin,
        claims=tuple(claims),
        relevance=_one_of(raw["relevance"], RELEVANCE, f"{where}.relevance"),
        completeness=_one_of(raw["completeness"], COMPLETENESS, f"{where}.completeness"),
        status=status,
        raw=raw,
    )


def read_records(path: Path) -> tuple[ClaimRecord, ...]:
    records: list[ClaimRecord] = []
    with path.open(encoding="utf-8") as file:
        for number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as error:
                raise DatasetError(f"{path}:{number}: invalid JSON: {error}") from None
            records.append(parse_record(raw, line=number))
    if len({record.id for record in records}) != len(records):
        raise DatasetError(f"{path}: duplicate record ids")
    return tuple(records)


def write_records(path: Path, records: Iterable[dict[str, Any]]) -> None:
    """Write raw records, one canonical JSON object per line (stable diffs)."""

    lines = [canonical_json(record) for record in records]
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


# --------------------------------------------------------------- splits

SPLIT_SALT = "gg-claims-v2-split"


def assign_split(context_group: str, *, test_fraction: float = 0.4) -> str:
    digest = hashlib.sha256(f"{SPLIT_SALT}:{context_group}".encode("utf-8")).hexdigest()
    return "test" if int(digest[:8], 16) / 0xFFFFFFFF < test_fraction else "dev"


def freeze(records_path: Path, *, version: str, test_fraction: float = 0.4) -> dict[str, Any]:
    """Freeze the LABELED records into a versioned split manifest.

    Writes ``splits.json`` next to the records: the split of every LABELED
    record (by context group), the sha256 of the records file, and the
    version. Refuses if any record is still DRAFT or NEEDS_REVIEW, so a
    release never mixes reviewed and unreviewed data.
    """

    records = read_records(records_path)
    pending = [record.id for record in records if record.status in ("DRAFT", "NEEDS_REVIEW")]
    if pending:
        raise DatasetError(
            f"cannot freeze: {len(pending)} record(s) not reviewed yet, e.g. {pending[:5]}"
        )
    labeled = [record for record in records if record.status == "LABELED"]
    if not labeled:
        raise DatasetError("cannot freeze: no LABELED records")

    splits: dict[str, list[str]] = {"dev": [], "test": []}
    for record in labeled:
        splits[assign_split(record.context_group, test_fraction=test_fraction)].append(record.id)
    manifest = {
        "version": version,
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "records_sha256": hashlib.sha256(records_path.read_bytes()).hexdigest(),
        "test_fraction": test_fraction,
        "salt": SPLIT_SALT,
        "counts": {name: len(ids) for name, ids in splits.items()},
        "excluded": sorted(record.id for record in records if record.status == "EXCLUDED"),
        "splits": {name: sorted(ids) for name, ids in splits.items()},
    }
    (records_path.parent / "splits.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def load_split(records_path: Path, split: Literal["dev", "test", "all"]) -> tuple[ClaimRecord, ...]:
    """Records of a frozen split. Fails if the records changed after freezing."""

    splits_path = records_path.parent / "splits.json"
    if not splits_path.exists():
        raise DatasetError(f"{records_path.parent}: not frozen (no splits.json)")
    manifest = json.loads(splits_path.read_text(encoding="utf-8"))
    if hashlib.sha256(records_path.read_bytes()).hexdigest() != manifest["records_sha256"]:
        raise DatasetError("records changed after freezing; release a new version instead")
    records = {record.id: record for record in read_records(records_path)}
    ids = (
        manifest["splits"]["dev"] + manifest["splits"]["test"]
        if split == "all"
        else manifest["splits"][split]
    )
    return tuple(records[record_id] for record_id in sorted(ids))


def log_test_access(log_path: Path, *, dataset: str, version: str, purpose: str, run_id: str) -> None:
    """Append one line per test-split evaluation (ADR-006)."""

    if not purpose.strip():
        raise DatasetError("a test-split run needs a stated purpose")
    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": dataset,
        "version": version,
        "purpose": purpose,
        "run_id": run_id,
    }
    with log_path.open("a", encoding="utf-8") as file:
        file.write(canonical_json(entry) + "\n")
