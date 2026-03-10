from __future__ import annotations

from dataclasses import dataclass

from tool.storage import Job, Storage

TERMINAL_STATES = {"DONE", "FAILED"}
ACTIVE_STATES = ["PENDING", "RETRYABLE", "PAUSED_NEEDS_HUMAN"]


@dataclass
class QueueManager:
    storage: Storage
    retry_limit: int

    def next_job(self) -> Job | None:
        jobs = self.storage.list_jobs_by_state(ACTIVE_STATES, limit=1)
        if not jobs:
            return None
        job = jobs[0]
        if job.state == "PAUSED_NEEDS_HUMAN":
            return job
        self.storage.transition(job.id, "RUNNING")
        return Job(**{**job.__dict__, "state": "RUNNING"})

    def mark_done(self, job: Job, output_path: str) -> None:
        self.storage.transition(job.id, "DONE", output_path=output_path)
        self.storage.add_event(job.id, "job_done", {"output_path": output_path})

    def mark_retryable(self, job: Job, error: str) -> None:
        attempts = self.storage.bump_attempt(job.id)
        if attempts > self.retry_limit:
            self.storage.transition(job.id, "FAILED", error=error)
            self.storage.add_event(job.id, "job_failed", {"error": error, "attempts": attempts})
            return
        self.storage.transition(job.id, "RETRYABLE", error=error)
        self.storage.add_event(job.id, "job_retryable", {"error": error, "attempts": attempts})

    def pause_needs_human(self, job: Job, reason: str) -> None:
        self.storage.transition(job.id, "PAUSED_NEEDS_HUMAN", error=reason)
        self.storage.add_event(job.id, "job_paused", {"reason": reason})

    def resume_paused(self) -> int:
        jobs = self.storage.list_jobs_by_state(["PAUSED_NEEDS_HUMAN"], limit=10000)
        for job in jobs:
            self.storage.transition(job.id, "RETRYABLE")
            self.storage.add_event(job.id, "job_resumed")
        return len(jobs)
