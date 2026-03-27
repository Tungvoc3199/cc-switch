from __future__ import annotations

from dataclasses import dataclass

from tool.storage import Job, JobStorage


@dataclass(slots=True)
class QueueStats:
    total: int
    done: int
    failed: int
    paused: int


class JobQueue:
    def __init__(self, storage: JobStorage, retry_limit: int):
        self.storage = storage
        self.retry_limit = retry_limit

    def recover_after_crash(self) -> int:
        return self.storage.reset_running_to_retryable()

    def next(self) -> Job | None:
        return self.storage.next_job()

    def mark_running(self, job: Job) -> None:
        self.storage.update_state(job.id, "RUNNING")

    def mark_done(self, job: Job, metadata: dict) -> None:
        self.storage.update_state(job.id, "DONE", metadata=metadata)

    def mark_pause_human(self, job: Job, message: str, metadata: dict | None = None) -> None:
        self.storage.update_state(job.id, "PAUSED_NEEDS_HUMAN", error_message=message, metadata=metadata)

    def mark_retryable(self, job: Job, error_message: str, metadata: dict | None = None) -> None:
        if job.retries + 1 > self.retry_limit:
            self.storage.update_state(job.id, "FAILED", error_message=error_message, metadata=metadata)
            return
        self.storage.update_state(
            job.id,
            "RETRYABLE",
            error_message=error_message,
            metadata=metadata,
            bump_retry=True,
        )

    def mark_failed(self, job: Job, error_message: str, metadata: dict | None = None) -> None:
        self.storage.update_state(job.id, "FAILED", error_message=error_message, metadata=metadata)

    def stats(self) -> QueueStats:
        jobs = self.storage.list_jobs()
        return QueueStats(
            total=len(jobs),
            done=sum(1 for j in jobs if j.state == "DONE"),
            failed=sum(1 for j in jobs if j.state == "FAILED"),
            paused=sum(1 for j in jobs if j.state == "PAUSED_NEEDS_HUMAN"),
        )
