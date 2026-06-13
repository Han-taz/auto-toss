from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from typing import Any


@dataclass(frozen=True)
class AuditStore:
    db_path: str | Path = ".auto_toss/auto_trading.sqlite3"

    def start_run(self, *, mode: str, config_path: str) -> int:
        with self._connect() as connection:
            _create_schema(connection)
            cursor = connection.execute(
                """
                INSERT INTO runs(mode, config_path, status)
                VALUES (?, ?, 'RUNNING')
                """,
                (mode, config_path),
            )
            return int(cursor.lastrowid)

    def complete_run(self, *, run_id: int, status: str) -> None:
        with self._connect() as connection:
            _create_schema(connection)
            connection.execute(
                """
                UPDATE runs
                SET status = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, run_id),
            )

    def record_intent(
        self,
        *,
        run_id: int,
        symbol: str,
        side: str,
        payload: dict[str, Any],
    ) -> int:
        with self._connect() as connection:
            _create_schema(connection)
            cursor = connection.execute(
                """
                INSERT INTO intents(run_id, symbol, side, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, symbol, side, _json_text(payload)),
            )
            return int(cursor.lastrowid)

    def record_check(
        self,
        *,
        run_id: int,
        intent_id: int,
        stage: str,
        name: str,
        status: str,
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> int:
        with self._connect() as connection:
            _create_schema(connection)
            cursor = connection.execute(
                """
                INSERT INTO checks(
                    run_id, intent_id, stage, name, status, reason, evidence_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    intent_id,
                    stage,
                    name,
                    status,
                    reason,
                    _json_text(evidence or {}),
                ),
            )
            return int(cursor.lastrowid)

    def record_execution(
        self,
        *,
        run_id: int,
        intent_id: int,
        mode: str,
        status: str,
        result: dict[str, Any],
        notional: str = "0",
    ) -> int:
        with self._connect() as connection:
            _create_schema(connection)
            cursor = connection.execute(
                """
                INSERT INTO executions(
                    run_id, intent_id, mode, status, notional, result_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, intent_id, mode, status, notional, _json_text(result)),
            )
            return int(cursor.lastrowid)

    def runs(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            _create_schema(connection)
            rows = connection.execute(
                """
                SELECT id, mode, config_path, status, started_at, completed_at
                FROM runs
                ORDER BY id DESC
                """
            ).fetchall()

        return [
            {
                "id": row["id"],
                "mode": row["mode"],
                "configPath": row["config_path"],
                "status": row["status"],
                "startedAt": row["started_at"],
                "completedAt": row["completed_at"],
            }
            for row in rows
        ]

    def daily_order_count(self, *, date: str | None = None) -> int:
        with self._connect() as connection:
            _create_schema(connection)
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM executions
                WHERE date(created_at) = COALESCE(?, date('now'))
                  AND status IN ('FILLED', 'SUBMITTED')
                """,
                (date,),
            ).fetchone()
            return int(row["count"])

    def daily_notional(self, *, date: str | None = None) -> Decimal:
        with self._connect() as connection:
            _create_schema(connection)
            rows = connection.execute(
                """
                SELECT notional
                FROM executions
                WHERE date(created_at) = COALESCE(?, date('now'))
                  AND status IN ('FILLED', 'SUBMITTED')
                """,
                (date,),
            ).fetchall()

        total = Decimal("0")
        for row in rows:
            total += Decimal(row["notional"])
        return total

    def _connect(self) -> sqlite3.Connection:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            config_path TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS intents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            intent_id INTEGER NOT NULL,
            stage TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            intent_id INTEGER NOT NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            notional TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
