from __future__ import annotations

import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestCliSmoke(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "prompts.txt").write_text("prompt 1\nprompt 2\n", encoding="utf-8")
        (self.root / "selectors.json").write_text("{}", encoding="utf-8")
        config = """
base_url: "https://labs.google/flow"
mode: "text2video"
model: "Veo 3.1 - Fast"
aspect_ratio: "16:9"
outputs_per_prompt: 1
headless: false
profile_dir: ".flow-profile"
prompts_file: "{prompts}"
images_dir: null
output_dir: "{out}"
db_path: "{db}"
selectors_path: "{selectors}"
logs_dir: "{logs}"
retry_limit: 2
timeouts:
  navigation_ms: 60000
  action_ms: 25000
  generation_ms: 600000
  poll_interval_ms: 2000
""".strip().format(
            prompts=(self.root / "prompts.txt").as_posix(),
            out=(self.root / "output").as_posix(),
            db=(self.root / "jobs.sqlite3").as_posix(),
            selectors=(self.root / "selectors.json").as_posix(),
            logs=(self.root / "logs").as_posix(),
        )
        self.config = self.root / "config.yaml"
        self.config.write_text(config, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_cmd(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tool.main", *args],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            text=True,
            capture_output=True,
        )

    def test_init_enqueue_resume(self) -> None:
        r1 = self.run_cmd("init", "-c", str(self.config))
        self.assertEqual(r1.returncode, 0, msg=r1.stderr)

        r2 = self.run_cmd("enqueue", "-c", str(self.config))
        self.assertEqual(r2.returncode, 0, msg=r2.stderr)
        self.assertIn("Enqueued 2 jobs", r2.stdout)

        r3 = self.run_cmd("resume", "-c", str(self.config))
        self.assertEqual(r3.returncode, 0, msg=r3.stderr)

        conn = sqlite3.connect(self.root / "jobs.sqlite3")
        rows = conn.execute("SELECT state, COUNT(*) FROM jobs GROUP BY state").fetchall()
        conn.close()
        self.assertEqual(rows, [("PENDING", 2)])


if __name__ == "__main__":
    unittest.main()
