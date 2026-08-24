from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any


from groundguard.evaluation.evaluation_record import (
    EvaluationRecord,
)


class EvaluationStore:
    """SQLite-backed persistent storage for evaluation records."""

    def __init__(
        self,
        database_path: str | Path = "groundguard.db",
    ) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
                """
            )

    def save(
        self,
        record: EvaluationRecord,
    ) -> str:
        evaluation_id = str(uuid.uuid4())
        data = record.to_dict()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO evaluations (
                    id,
                    created_at,
                    data
                )
                VALUES (
                    ?,
                    datetime('now'),
                    ?
                )
                """,
                (
                    evaluation_id,
                    json.dumps(
                        data,
                        ensure_ascii=False,
                    ),
                ),
            )

        return evaluation_id

    def get_all(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        system_decision: str | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT id, created_at, data
            FROM evaluations
        """

        parameters: list[Any] = []

        if system_decision is not None:
            query += """
                WHERE json_extract(
                    data,
                    '$.system_decision'
                ) = ?
            """
            parameters.append(system_decision)

        query += """
            ORDER BY created_at DESC
        """

        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)

        if offset:
            query += " OFFSET ?"
            parameters.append(offset)

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [
            self._row_to_dict(row)
            for row in rows
        ]

    def get_by_id(
        self,
        evaluation_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, created_at, data
                FROM evaluations
                WHERE id = ?
                """,
                (evaluation_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_dict(row)

    def count(
        self,
        *,
        system_decision: str | None = None,
    ) -> int:
        query = """
            SELECT COUNT(*) AS count
            FROM evaluations
        """

        parameters: list[Any] = []

        if system_decision is not None:
            query += """
                WHERE json_extract(
                    data,
                    '$.system_decision'
                ) = ?
            """
            parameters.append(system_decision)

        with self._connect() as connection:
            row = connection.execute(
                query,
                parameters,
            ).fetchone()

        return int(row["count"])

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM evaluations"
            )

    @staticmethod
    def _row_to_dict(
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        data = json.loads(row["data"])
        data["id"] = row["id"]
        data["created_at"] = row["created_at"]
        return data