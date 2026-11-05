"""Service settings, read once from the environment by ``Settings.from_env``."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Mapping

from groundguard.storage.v2_store import PAYLOAD_MODES, PayloadMode


AuthMode = Literal["required", "disabled"]


@dataclass(frozen=True)
class Settings:
    database_path: str = "groundguard.db"
    # v2 routes require an API key unless auth is explicitly disabled.
    auth: AuthMode = "required"
    rate_limit_per_minute: int = 120
    max_body_bytes: int = 1_000_000
    payload_mode: PayloadMode = "redacted"
    max_batch_items: int = 50

    def __post_init__(self) -> None:
        if self.auth not in ("required", "disabled"):
            raise ValueError("GROUNDGUARD_AUTH must be 'required' or 'disabled'")
        if self.payload_mode not in PAYLOAD_MODES:
            raise ValueError(f"GROUNDGUARD_PAYLOAD_MODE must be one of {PAYLOAD_MODES}")
        if self.rate_limit_per_minute < 1:
            raise ValueError("GROUNDGUARD_RATE_LIMIT_PER_MINUTE must be positive")
        if self.max_body_bytes < 1024:
            raise ValueError("GROUNDGUARD_MAX_BODY_BYTES must be at least 1024")
        if not 1 <= self.max_batch_items <= 1000:
            raise ValueError("GROUNDGUARD_MAX_BATCH_ITEMS must be between 1 and 1000")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        defaults = cls()
        return cls(
            database_path=env.get("GROUNDGUARD_DATABASE_PATH", defaults.database_path),
            auth=env.get("GROUNDGUARD_AUTH", defaults.auth),  # type: ignore[arg-type]
            rate_limit_per_minute=int(env.get("GROUNDGUARD_RATE_LIMIT_PER_MINUTE", defaults.rate_limit_per_minute)),
            max_body_bytes=int(env.get("GROUNDGUARD_MAX_BODY_BYTES", defaults.max_body_bytes)),
            payload_mode=env.get("GROUNDGUARD_PAYLOAD_MODE", defaults.payload_mode),  # type: ignore[arg-type]
            max_batch_items=int(env.get("GROUNDGUARD_MAX_BATCH_ITEMS", defaults.max_batch_items)),
        )
