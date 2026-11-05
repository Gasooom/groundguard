"""SQLite storage for engine v2: migrations, API keys, tenant-scoped evaluations.

Shares the database file with the v1 ``evaluations`` table, which it never
touches. Schema changes are numbered migrations recorded in
``schema_migrations``, applied in order inside a transaction.

Privacy: ``payload_mode`` controls what is persisted for each evaluation.

full      the complete report
redacted  the report with detected PII spans replaced in question, answer
          and sources (default; regex-based, so names or addresses may survive)
none      decisions, labels, counts and the manifest only; no text
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

from groundguard.domain.pii import detect_pii


PayloadMode = Literal["full", "redacted", "none"]
PAYLOAD_MODES: tuple[PayloadMode, ...] = ("full", "redacted", "none")
DECISIONS = ("ACCEPT", "FLAG", "REJECT", "HUMAN_REVIEW")

MIGRATIONS: tuple[tuple[int, str, str], ...] = (
    (
        1,
        "api keys",
        """
        CREATE TABLE api_keys (
            key_id      TEXT PRIMARY KEY,
            tenant_id   TEXT NOT NULL,
            secret_hash TEXT NOT NULL,
            label       TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            revoked_at  TEXT
        );
        CREATE INDEX ix_api_keys_tenant ON api_keys (tenant_id);
        """,
    ),
    (
        2,
        "v2 evaluations",
        """
        CREATE TABLE evaluations_v2 (
            id              TEXT PRIMARY KEY,
            tenant_id       TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            decision        TEXT NOT NULL CHECK (decision IN ('ACCEPT','FLAG','REJECT','HUMAN_REVIEW')),
            rule            TEXT NOT NULL,
            policy_id       TEXT NOT NULL,
            policy_version  TEXT NOT NULL,
            engine_version  TEXT NOT NULL,
            config_hash     TEXT NOT NULL,
            n_claims        INTEGER NOT NULL,
            n_supported     INTEGER NOT NULL,
            n_contradicted  INTEGER NOT NULL,
            n_nei           INTEGER NOT NULL,
            safety_findings INTEGER NOT NULL,
            payload_mode    TEXT NOT NULL CHECK (payload_mode IN ('full','redacted','none')),
            report          TEXT NOT NULL
        );
        CREATE INDEX ix_eval_v2_tenant_time ON evaluations_v2 (tenant_id, created_at DESC, id DESC);
        CREATE INDEX ix_eval_v2_tenant_decision ON evaluations_v2 (tenant_id, decision, created_at DESC);
        """,
    ),
)

KEY_PREFIX = "gg"


@dataclass(frozen=True)
class ApiKeyRecord:
    key_id: str
    tenant_id: str
    label: str
    created_at: str
    revoked_at: str | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def redact_text(text: str) -> str:
    """Replace every PII match found by the v1 detector with a marker.

    Longest matches are replaced first, so a card number is not partly
    replaced as a phone number.
    """

    detection = detect_pii(text)
    redacted = text
    for match in sorted(set(detection.evidence), key=len, reverse=True):
        redacted = redacted.replace(match, "[REDACTED]")
    return redacted


def _redact_report(report: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(report))
    redacted["question"] = redact_text(redacted["question"])
    redacted["answer"] = redact_text(redacted["answer"])
    for source in redacted.get("sources", []):
        source["text"] = redact_text(source["text"])
    for claim in redacted.get("claims", []):
        claim["text"] = redact_text(claim["text"])
    for verdict in redacted.get("verdicts", []):
        for evidence in verdict.get("evidence", []):
            evidence["text"] = redact_text(evidence["text"])
    if "safety" in redacted:
        redacted["safety"]["evidence"] = ["[REDACTED]" for _ in redacted["safety"]["evidence"]]
    return redacted


def _minimal_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": report["decision"],
        "labels": report["labels"],
        "relevance": {"label": report["relevance"]["label"]},
        "safety": {key: value for key, value in report["safety"].items() if key != "evidence"},
        "verdicts": [
            {key: verdict[key] for key in ("claim_id", "label", "raw_score", "confidence", "verifier")}
            for verdict in report["verdicts"]
        ],
        "manifest": report["manifest"],
    }


class V2Store:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    # ------------------------------------------------------------- schema

    def migrate(self) -> list[int]:
        applied: list[int] = []
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
            )
            done = {row["version"] for row in connection.execute("SELECT version FROM schema_migrations")}
            for version, name, sql in MIGRATIONS:
                if version in done:
                    continue
                for statement in filter(None, (part.strip() for part in sql.split(";"))):
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, _now()),
                )
                applied.append(version)
        return applied

    def schema_version(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
        return int(row["v"] or 0)

    # ------------------------------------------------------------ API keys

    def create_api_key(self, tenant_id: str, label: str = "") -> str:
        """Create a key and return it once: ``gg_<key_id>_<secret>``. Only a
        SHA-256 hash of the secret is stored."""

        if not tenant_id.strip():
            raise ValueError("tenant_id must not be empty")
        key_id = secrets.token_hex(6)
        secret = secrets.token_urlsafe(32)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO api_keys (key_id, tenant_id, secret_hash, label, created_at) VALUES (?, ?, ?, ?, ?)",
                (key_id, tenant_id, _hash_secret(secret), label, _now()),
            )
        return f"{KEY_PREFIX}_{key_id}_{secret}"

    def authenticate(self, presented: str) -> str | None:
        """Return the tenant id for a valid, unrevoked key, else ``None``."""

        parts = presented.split("_", 2)
        if len(parts) != 3 or parts[0] != KEY_PREFIX or not parts[1] or not parts[2]:
            return None
        _, key_id, secret = parts
        with self._connect() as connection:
            row = connection.execute(
                "SELECT tenant_id, secret_hash, revoked_at FROM api_keys WHERE key_id = ?", (key_id,)
            ).fetchone()
        expected = row["secret_hash"] if row is not None else _hash_secret("not-a-key")
        valid = hmac.compare_digest(expected, _hash_secret(secret))
        if row is None or not valid or row["revoked_at"] is not None:
            return None
        return str(row["tenant_id"])

    def revoke_api_key(self, key_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE api_keys SET revoked_at = ? WHERE key_id = ? AND revoked_at IS NULL", (_now(), key_id)
            )
        return cursor.rowcount == 1

    def list_api_keys(self) -> list[ApiKeyRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key_id, tenant_id, label, created_at, revoked_at FROM api_keys ORDER BY created_at"
            ).fetchall()
        return [ApiKeyRecord(**dict(row)) for row in rows]

    # --------------------------------------------------------- evaluations

    def save_evaluation(self, tenant_id: str, report: dict[str, Any], payload_mode: PayloadMode) -> str:
        if payload_mode not in PAYLOAD_MODES:
            raise ValueError(f"payload_mode must be one of {PAYLOAD_MODES}")
        labels = [verdict["label"] for verdict in report["verdicts"]]
        stored = (
            report if payload_mode == "full"
            else _redact_report(report) if payload_mode == "redacted"
            else _minimal_report(report)
        )
        evaluation_id = str(uuid.uuid4())
        decision = report["decision"]
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO evaluations_v2 (id, tenant_id, created_at, decision, rule, policy_id,
                   policy_version, engine_version, config_hash, n_claims, n_supported, n_contradicted,
                   n_nei, safety_findings, payload_mode, report)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    evaluation_id, tenant_id, _now(), decision["decision"], decision["rule"],
                    decision["policy"]["id"], decision["policy"]["version"],
                    report["manifest"]["engine_version"], report["manifest"]["config_hash"],
                    len(labels), labels.count("SUPPORTED"), labels.count("CONTRADICTED"),
                    labels.count("NOT_ENOUGH_INFO"),
                    int(report["safety"]["pii_detected"]) + int(report["safety"]["prompt_injection_detected"]),
                    payload_mode, json.dumps(stored, ensure_ascii=False, sort_keys=True),
                ),
            )
        return evaluation_id

    def get_evaluation(self, tenant_id: str, evaluation_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM evaluations_v2 WHERE tenant_id = ? AND id = ?", (tenant_id, evaluation_id)
            ).fetchone()
        return None if row is None else self._row(row)

    def list_evaluations(
        self,
        tenant_id: str,
        *,
        limit: int = 50,
        before: tuple[str, str] | None = None,
        decision: str | None = None,
    ) -> list[dict[str, Any]]:
        """Newest first. ``before`` is a (created_at, id) cursor from the previous page."""

        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if decision is not None and decision not in DECISIONS:
            raise ValueError(f"decision must be one of {DECISIONS}")
        query = "SELECT * FROM evaluations_v2 WHERE tenant_id = ?"
        parameters: list[Any] = [tenant_id]
        if decision is not None:
            query += " AND decision = ?"
            parameters.append(decision)
        if before is not None:
            query += " AND (created_at < ? OR (created_at = ? AND id < ?))"
            parameters.extend([before[0], before[0], before[1]])
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._row(row, include_report=False) for row in rows]

    def stats(self, tenant_id: str, *, since: str | None = None) -> dict[str, Any]:
        """Aggregates computed in SQL; nothing is loaded row by row."""

        where = "WHERE tenant_id = ?" + (" AND created_at >= ?" if since else "")
        parameters: list[Any] = [tenant_id] + ([since] if since else [])
        with self._connect() as connection:
            totals = connection.execute(
                f"""SELECT COUNT(*) AS total, COALESCE(SUM(n_claims), 0) AS claims,
                    COALESCE(SUM(n_contradicted), 0) AS contradicted, COALESCE(SUM(n_nei), 0) AS nei,
                    COALESCE(SUM(safety_findings > 0), 0) AS with_safety_findings
                    FROM evaluations_v2 {where}""",
                parameters,
            ).fetchone()
            by_decision = connection.execute(
                f"SELECT decision, COUNT(*) AS n FROM evaluations_v2 {where} GROUP BY decision", parameters
            ).fetchall()
            by_rule = connection.execute(
                f"SELECT rule, COUNT(*) AS n FROM evaluations_v2 {where} GROUP BY rule ORDER BY n DESC", parameters
            ).fetchall()
            by_day = connection.execute(
                f"""SELECT substr(created_at, 1, 10) AS day, decision, COUNT(*) AS n
                    FROM evaluations_v2 {where} GROUP BY day, decision ORDER BY day""",
                parameters,
            ).fetchall()
        total = int(totals["total"])
        decisions = {label: 0 for label in DECISIONS} | {row["decision"]: int(row["n"]) for row in by_decision}
        days: dict[str, dict[str, int]] = {}
        for row in by_day:
            days.setdefault(row["day"], {label: 0 for label in DECISIONS})[row["decision"]] = int(row["n"])
        return {
            "total": total,
            "decisions": decisions,
            "decision_rates": {k: (round(v / total, 6) if total else 0.0) for k, v in decisions.items()},
            "claims": int(totals["claims"]),
            "contradicted_claims": int(totals["contradicted"]),
            "not_enough_info_claims": int(totals["nei"]),
            "evaluations_with_safety_findings": int(totals["with_safety_findings"]),
            "by_rule": {row["rule"]: int(row["n"]) for row in by_rule},
            "by_day": [{"day": day, **counts} for day, counts in days.items()],
        }

    @staticmethod
    def _row(row: sqlite3.Row, *, include_report: bool = True) -> dict[str, Any]:
        data = {key: row[key] for key in row.keys() if key not in ("report", "tenant_id")}
        if include_report:
            data["report"] = json.loads(row["report"])
        return data
