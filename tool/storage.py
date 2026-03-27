from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


JOB_STATES = (
    "PENDING",
    "RUNNING",
    "PAUSED_NEEDS_HUMAN",
    "DONE",
    "FAILED",
    "RETRYABLE",
)


@dataclass(slots=True)
class Job:
    id: int
    prompt: str
    assets_json: str | None
    state: str
    retries: int
    error_message: str | None
    created_at: str
    updated_at: str

    @property
    def assets(self) -> list[str]:
        if not self.assets_json:
            return []
        return json.loads(self.assets_json)


class JobStorage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                assets_json TEXT,
                state TEXT NOT NULL,
                retries INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def enqueue_prompts(self, prompts: list[str], assets: list[str] | None = None) -> int:
        now = _utc_now()
        values = [
            (prompt.strip(), json.dumps(assets or []), "PENDING", now, now)
            for prompt in prompts
            if prompt.strip()
        ]
        if not values:
            return 0
        self.conn.executemany(
            """
            INSERT INTO jobs (prompt, assets_json, state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            values,
        )
        self.conn.commit()
        return len(values)

    def next_job(self) -> Job | None:
        row = self.conn.execute(
            """
            SELECT * FROM jobs
            WHERE state IN ('PENDING', 'RETRYABLE')
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        return _to_job(row) if row else None

    def get_by_id(self, job_id: int) -> Job | None:
        row = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _to_job(row) if row else None

    def reset_running_to_retryable(self) -> int:
        now = _utc_now()
        cur = self.conn.execute(
            """
            UPDATE jobs
            SET state = 'RETRYABLE',
                updated_at = ?,
                error_message = COALESCE(error_message, 'Recovered after interruption')
            WHERE state = 'RUNNING'
            """,
            (now,),
        )
        self.conn.commit()
        return cur.rowcount

    def update_state(
        self,
        job_id: int,
        state: str,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
        bump_retry: bool = False,
    ) -> None:
        if state not in JOB_STATES:
            raise ValueError(f"invalid state: {state}")
        now = _utc_now()
        updates = ["state = ?", "updated_at = ?"]
        params: list[Any] = [state, now]

        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if metadata is not None:
            updates.append("metadata_json = ?")
            params.append(json.dumps(metadata, ensure_ascii=False, indent=2))

        if bump_retry:
            updates.append("retries = retries + 1")

        params.append(job_id)
        self.conn.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        self.conn.commit()

    def list_jobs(self) -> list[Job]:
        rows = self.conn.execute("SELECT * FROM jobs ORDER BY id ASC").fetchall()
        return [_to_job(r) for r in rows]

    def close(self) -> None:
        self.conn.close()


def _to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        prompt=row["prompt"],
        assets_json=row["assets_json"],
        state=row["state"],
        retries=row["retries"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
