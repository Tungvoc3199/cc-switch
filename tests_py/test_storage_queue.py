from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tool.queue import QueueManager
from tool.storage import Storage


class TestStorageQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite3"
        self.storage = Storage(self.db)
        self.storage.init_schema()
        self.storage.enqueue_jobs(
            prompts=["a", "b"],
            mode="text2video",
            model="Veo 3.1 - Fast",
            aspect_ratio="16:9",
            outputs_per_prompt=1,
        )

    def tearDown(self) -> None:
        self.storage.close()
        self.tmp.cleanup()

    def test_retry_to_failed(self) -> None:
        q = QueueManager(self.storage, retry_limit=1)
        job = q.next_job()
        assert job is not None
        q.mark_retryable(job, "boom")
        job2 = self.storage.list_jobs_by_state(["RETRYABLE"], limit=1)[0]
        q.mark_retryable(job2, "boom again")
        failed = self.storage.list_jobs_by_state(["FAILED"], limit=10)
        self.assertEqual(len(failed), 1)

    def test_resume_paused(self) -> None:
        q = QueueManager(self.storage, retry_limit=1)
        job = q.next_job()
        assert job is not None
        q.pause_needs_human(job, "captcha")
        resumed = q.resume_paused()
        self.assertEqual(resumed, 1)
        rows = self.storage.list_jobs_by_state(["RETRYABLE"], limit=10)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
