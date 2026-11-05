"""Benchmark dataset loading, validation, hashing, deduplication and splits.

Only the standard library is used. The legacy v1 dataset is read from the
existing ``benchmark/`` files in place so that its history is preserved.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence

from groundguard.bench.errors import DatasetError


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = REPO_ROOT / "benchmark"
SCHEMA_PATH = BENCHMARK_DIR / "schema.json"

LEGACY_V1_ID = "gg-legacy-v1"
LEGACY_V1_VERSION = "1.0.0"

# Same order as the existing benchmark tests
# (tests/test_grounding_benchmark.py), so record order is identical.
LEGACY_V1_FILES: tuple[Path, ...] = (
    BENCHMARK_DIR / "examples" / "human_labeled_001_020.json",
    BENCHMARK_DIR / "batch_001_021_030.json",
    *sorted((BENCHMARK_DIR / "examples").glob("batch_001_*.json")),
)

Split = Literal["all", "dev", "test"]


@dataclass(frozen=True)
class BenchmarkRecord:
    id: str
    question: str
    context: str
    answer: str
    grounding_label: str
    relevance_label: str
    contradiction_label: str
    evidence: tuple[str, ...]
    source: str
    annotation_status: str
    annotation_notes: str = ""
    source_file: str = ""

    @property
    def triple(self) -> tuple[str, str, str]:
        return (self.question, self.context, self.answer)


@dataclass(frozen=True)
class Dataset:
    id: str
    version: str
    records: tuple[BenchmarkRecord, ...]
    sha256: str
    files: tuple[str, ...] = field(default_factory=tuple)

    def __len__(self) -> int:
        return len(self.records)


def _load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as file:
        schema: dict[str, Any] = json.load(file)
    return schema


def validate_record(raw: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate the subset of ``benchmark/schema.json`` the harness relies on.

    Checks required keys, unknown keys, string types and enum values, plus the
    conditional ``source_metadata`` requirement for public text. Raises
    ``DatasetError`` with the record id on the first violation.
    """

    record_id = raw.get("id", "<missing id>")
    properties: dict[str, Any] = schema["properties"]

    missing = [key for key in schema["required"] if key not in raw]
    if missing:
        raise DatasetError(f"{record_id}: missing required keys {missing}")

    unknown = sorted(set(raw) - set(properties))
    if unknown and schema.get("additionalProperties") is False:
        raise DatasetError(f"{record_id}: unknown keys {unknown}")

    for key, spec in properties.items():
        if key not in raw:
            continue
        value = raw[key]
        expected_type = spec.get("type")
        if expected_type == "string" and not isinstance(value, str):
            raise DatasetError(f"{record_id}: {key} must be a string")
        if expected_type == "array" and not (
            isinstance(value, list) and all(isinstance(item, str) for item in value)
        ):
            raise DatasetError(f"{record_id}: {key} must be a list of strings")
        if "enum" in spec and value not in spec["enum"]:
            raise DatasetError(
                f"{record_id}: {key}={value!r} not in {spec['enum']}"
            )
        if spec.get("minLength") and isinstance(value, str) and not value.strip():
            raise DatasetError(f"{record_id}: {key} must be non-empty")

    if raw.get("source") == "public_text" and "source_metadata" not in raw:
        raise DatasetError(f"{record_id}: public_text requires source_metadata")


def _to_record(raw: dict[str, Any], source_file: str) -> BenchmarkRecord:
    return BenchmarkRecord(
        id=raw["id"],
        question=raw["question"],
        context=raw["context"],
        answer=raw["answer"],
        grounding_label=raw["grounding_label"],
        relevance_label=raw["relevance_label"],
        contradiction_label=raw["contradiction_label"],
        evidence=tuple(raw["evidence"]),
        source=raw["source"],
        annotation_status=raw["annotation_status"],
        annotation_notes=raw.get("annotation_notes", ""),
        source_file=source_file,
    )


def files_sha256(paths: Iterable[Path]) -> str:
    """Hash file names and bytes in order, so reordering changes the hash."""

    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(REPO_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_legacy_v1() -> Dataset:
    """Load the 250 v0.1.0 benchmark records exactly as the v1 tests do."""

    schema = _load_schema()
    records: list[BenchmarkRecord] = []

    for path in LEGACY_V1_FILES:
        if not path.exists():
            raise DatasetError(f"missing benchmark file: {path}")
        with path.open(encoding="utf-8") as file:
            items = json.load(file)
        if not isinstance(items, list):
            raise DatasetError(f"{path}: expected a JSON list of records")
        relative = path.relative_to(REPO_ROOT).as_posix()
        for raw in items:
            validate_record(raw, schema)
            records.append(_to_record(raw, relative))

    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise DatasetError("duplicate record ids in legacy dataset")

    return Dataset(
        id=LEGACY_V1_ID,
        version=LEGACY_V1_VERSION,
        records=tuple(records),
        sha256=files_sha256(LEGACY_V1_FILES),
        files=tuple(path.relative_to(REPO_ROOT).as_posix() for path in LEGACY_V1_FILES),
    )


DATASETS = {
    LEGACY_V1_ID: load_legacy_v1,
}


def load_dataset(dataset_id: str) -> Dataset:
    try:
        loader = DATASETS[dataset_id]
    except KeyError:
        raise DatasetError(
            f"unknown dataset {dataset_id!r}; known: {sorted(DATASETS)}"
        ) from None
    return loader()


def deduplicate(records: Sequence[BenchmarkRecord]) -> tuple[BenchmarkRecord, ...]:
    """Keep the first record for each exact (question, context, answer) triple."""

    seen: set[tuple[str, str, str]] = set()
    unique: list[BenchmarkRecord] = []
    for record in records:
        if record.triple in seen:
            continue
        seen.add(record.triple)
        unique.append(record)
    return tuple(unique)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def _shingles(text: str, size: int = 5) -> set[str]:
    normalized = _normalize(text)
    if len(normalized) <= size:
        return {normalized}
    return {normalized[i : i + size] for i in range(len(normalized) - size + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def assign_context_groups(
    records: Sequence[BenchmarkRecord],
    *,
    near_duplicate_threshold: float = 0.8,
) -> dict[str, str]:
    """Map record id → context group id.

    Records whose normalized contexts are identical, or whose character
    5-gram Jaccard similarity is at least ``near_duplicate_threshold``, share
    a group (transitively, via union-find). The group id is the smallest
    record id in the group, which keeps it stable under reordering.
    """

    contexts = sorted({_normalize(record.context) for record in records})
    parent = {context: context for context in contexts}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    shingles = {context: _shingles(context) for context in contexts}
    for i, left in enumerate(contexts):
        for right in contexts[i + 1 :]:
            if jaccard(shingles[left], shingles[right]) >= near_duplicate_threshold:
                root_left, root_right = find(left), find(right)
                if root_left != root_right:
                    parent[max(root_left, root_right)] = min(root_left, root_right)

    root_to_ids: dict[str, list[str]] = {}
    for record in records:
        root_to_ids.setdefault(find(_normalize(record.context)), []).append(record.id)

    groups: dict[str, str] = {}
    for ids in root_to_ids.values():
        group_id = min(ids)
        for record_id in ids:
            groups[record_id] = group_id
    return groups


def group_split(
    records: Sequence[BenchmarkRecord],
    groups: dict[str, str],
    *,
    test_fraction: float = 0.4,
    salt: str = "groundguard-split-v1",
) -> dict[str, str]:
    """Deterministically assign each record to ``dev`` or ``test`` by group.

    A group goes to ``test`` when ``sha256(salt + group_id)`` falls below
    ``test_fraction`` of the hash space, so the assignment does not depend on
    record order or a random seed.
    """

    if not 0.0 < test_fraction < 1.0:
        raise ValueError("test_fraction must be between 0 and 1")

    assignment: dict[str, str] = {}
    for record in records:
        group_id = groups[record.id]
        digest = hashlib.sha256(f"{salt}:{group_id}".encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        assignment[record.id] = "test" if bucket < test_fraction else "dev"
    return assignment
