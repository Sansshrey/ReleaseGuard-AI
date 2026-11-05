"""SQLite persistence and append-only, hash-chained audit events."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import ReleaseRecord

GENESIS_HASH = "0" * 64


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class SQLiteReleaseRepository:
    """Local-first SQLite storage. Use managed storage for production."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = str(database_path or os.getenv("RELEASEGUARD_DB_PATH", "releaseguard.db"))
        if self.database_path != ":memory:":
            Path(self.database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS releases (
                    release_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    record_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    release_id TEXT NOT NULL REFERENCES releases(release_id),
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_audit_release_sequence
                    ON audit_events(release_id, sequence);
                CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                BEFORE UPDATE ON audit_events BEGIN
                    SELECT RAISE(ABORT, 'audit events are append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                BEFORE DELETE ON audit_events BEGIN
                    SELECT RAISE(ABORT, 'audit events are append-only');
                END;
            """)

    @staticmethod
    def _hash(event_id: str, release_id: str, event_type: str, occurred_at: str,
              details_json: str, previous_hash: str) -> str:
        body = {
            "event_id": event_id, "release_id": release_id, "event_type": event_type,
            "occurred_at": occurred_at, "details_json": details_json,
            "previous_hash": previous_hash,
        }
        return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()

    def _append_event(self, db: sqlite3.Connection, record: ReleaseRecord,
                      event_type: str, details: dict[str, Any]) -> None:
        previous = db.execute(
            "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else GENESIS_HASH
        event_id = str(uuid4())
        occurred_at = datetime.now(timezone.utc).isoformat()
        details_json = _canonical(details)
        event_hash = self._hash(event_id, record.release_id, event_type, occurred_at,
                                details_json, previous_hash)
        db.execute(
            """INSERT INTO audit_events
            (event_id, release_id, event_type, occurred_at, details_json, previous_hash, event_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, record.release_id, event_type, occurred_at, details_json,
             previous_hash, event_hash),
        )

    def save_new(self, record: ReleaseRecord) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO releases VALUES (?, ?, ?, ?)",
                (record.release_id, record.created_at.isoformat(), record.decision.value,
                 record.model_dump_json()),
            )
            self._append_event(db, record, "release_created", {
                "decision": record.decision.value,
                "risk_score": record.risk.total,
                "finding_count": len(record.findings),
            })

    def update_decision(self, record: ReleaseRecord, previous_decision: str) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                "UPDATE releases SET decision = ?, record_json = ? WHERE release_id = ?",
                (record.decision.value, record.model_dump_json(), record.release_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(record.release_id)
            self._append_event(db, record, "release_decision_changed", {
                "previous_decision": previous_decision,
                "decision": record.decision.value,
                "note": record.approval_note,
            })

    def get(self, release_id: str) -> ReleaseRecord | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT record_json FROM releases WHERE release_id = ?", (release_id,)
            ).fetchone()
        return ReleaseRecord.model_validate_json(row["record_json"]) if row else None

    def list_audit_events(self, release_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT sequence, event_id, release_id, event_type, occurred_at,
                details_json, previous_hash, event_hash FROM audit_events
                WHERE release_id = ? ORDER BY sequence""", (release_id,)
            ).fetchall()
        return [{
            "sequence": row["sequence"], "event_id": row["event_id"],
            "release_id": row["release_id"], "event_type": row["event_type"],
            "occurred_at": row["occurred_at"], "details": json.loads(row["details_json"]),
            "previous_hash": row["previous_hash"], "event_hash": row["event_hash"],
        } for row in rows]

    def verify_audit_chain(self) -> dict[str, Any]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT sequence, event_id, release_id, event_type, occurred_at,
                details_json, previous_hash, event_hash FROM audit_events ORDER BY sequence"""
            ).fetchall()
        previous = GENESIS_HASH
        for row in rows:
            if row["previous_hash"] != previous:
                return {"valid": False, "checked_events": row["sequence"] - 1,
                        "failed_sequence": row["sequence"]}
            expected = self._hash(
                row["event_id"], row["release_id"], row["event_type"], row["occurred_at"],
                row["details_json"], row["previous_hash"],
            )
            if not hmac.compare_digest(expected, row["event_hash"]):
                return {"valid": False, "checked_events": row["sequence"] - 1,
                        "failed_sequence": row["sequence"]}
            previous = row["event_hash"]
        return {"valid": True, "checked_events": len(rows), "failed_sequence": None}
