"""Canonical JSON and content hashing, shared by the engine and the harness."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(data: Any) -> str:
    """Deterministic JSON: sorted keys, no insignificant whitespace."""

    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
