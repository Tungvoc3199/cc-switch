from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Job:
    id: int
    prompt: str
    state: str
    attempts: int
    mode: str
    model: str
    aspect_ratio: str
    outputs_per_prompt: int
    output_path: str | None
    error: str | None


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                mode TEXT NOT NULL,
                model TEXT NOT NULL,
                aspect_ratio TEXT NOT NULL,
                outputs_per_prompt INTEGER NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                output_path TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                event TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );
            """
        )
        self.conn.commit()

    def enqueue_jobs(
        self,
        prompts: list[str],
        mode: str,
        model: str,
        aspect_ratio: str,
        outputs_per_prompt: int,
    ) -> int:
        now = _now_iso()
        rows = [
            (p, mode, model, aspect_ratio, outputs_per_prompt, "PENDING", 0, now, now)
            for p in prompts
            if p.strip()
        ]
        self.conn.executemany(
            """
            INSERT INTO jobs(prompt, mode, model, aspect_ratio, outputs_per_prompt, state, attempts, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        self.conn.commit()
        return len(rows)

    def list_jobs_by_state(self, states: list[str], limit: int = 100) -> list[Job]:
        placeholders = ",".join("?" for _ in states)
        cur = self.conn.execute(
            f"""
            SELECT id, prompt, state, attempts, mode, model, aspect_ratio, outputs_per_prompt, output_path, error
            FROM jobs
            WHERE state IN ({placeholders})
            ORDER BY id ASC
            LIMIT ?
            """,
            [*states, limit],
        )
        return [Job(**dict(r)) for r in cur.fetchall()]

    def transition(self, job_id: int, state: str, error: str | None = None, output_path: str | None = None) -> None:
        self.conn.execute(
            """
            UPDATE jobs
            SET state = ?,
                error = COALESCE(?, error),
                output_path = COALESCE(?, output_path),
                updated_at = ?
            WHERE id = ?
            """,
            (state, error, output_path, _now_iso(), job_id),
        )
        self.conn.commit()

    def bump_attempt(self, job_id: int) -> int:
        self.conn.execute(
            "UPDATE jobs SET attempts = attempts + 1, updated_at = ? WHERE id = ?",
            (_now_iso(), job_id),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT attempts FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return int(row["attempts"])

    def add_event(self, job_id: int, event: str, payload: dict[str, Any] | None = None) -> None:
        self.conn.execute(
            "INSERT INTO job_events(job_id, event, payload, created_at) VALUES(?,?,?,?)",
            (job_id, event, json.dumps(payload or {}, ensure_ascii=False), _now_iso()),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
