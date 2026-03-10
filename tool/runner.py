from __future__ import annotations

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
from tool.config import AppConfig
from tool.queue import QueueManager
from tool.storage import Job, Storage


class Runner:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.cfg.logs_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("flow_tool")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            fh = RotatingFileHandler(self.cfg.logs_dir / "flow_tool.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            self.logger.addHandler(fh)

    def init(self) -> None:
        storage = Storage(self.cfg.db_path)
        storage.init_schema()
        storage.close()
        self.logger.info("Initialized DB schema at %s", self.cfg.db_path)

    def enqueue_prompts(self, prompts: list[str]) -> int:
        storage = Storage(self.cfg.db_path)
        try:
            added = storage.enqueue_jobs(
                prompts=prompts,
                mode=self.cfg.mode,
                model=self.cfg.model,
                aspect_ratio=self.cfg.aspect_ratio,
                outputs_per_prompt=self.cfg.outputs_per_prompt,
            )
            return added
        finally:
            storage.close()

    def resume(self) -> int:
        storage = Storage(self.cfg.db_path)
        try:
            q = QueueManager(storage, self.cfg.retry_limit)
            return q.resume_paused()
        finally:
            storage.close()

    def run(self) -> None:
        from playwright.sync_api import sync_playwright

        from tool.adapters.flow_adapter import FlowAdapter, NeedsHumanVerification
        from tool.selectors import SelectorCatalog

        storage = Storage(self.cfg.db_path)
        selectors = SelectorCatalog.load(self.cfg.selectors_path)
        q = QueueManager(storage, self.cfg.retry_limit)
        image_paths = self._discover_images()

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(self.cfg.profile_dir),
                headless=self.cfg.headless,
                accept_downloads=True,
            )
            page = browser.pages[0] if browser.pages else browser.new_page()
            adapter = FlowAdapter(page=page, context=browser, config=self.cfg, selectors=selectors)

            try:
                adapter.open_base()
                adapter.ensure_logged_in()
            except NeedsHumanVerification as exc:
                self.logger.warning("Init stopped by human verification: %s", exc)
                print("[PAUSED] Phát hiện verify/captcha. Xác minh thủ công rồi chạy lại lệnh run.")
                browser.close()
                storage.close()
                return

            while True:
                job = q.next_job()
                if not job:
                    self.logger.info("No more jobs.")
                    break

                try:
                    self._execute_job(adapter, job, image_paths)
                except NeedsHumanVerification as exc:
                    q.pause_needs_human(job, str(exc))
                    self._capture_failure_artifacts(page, job, exc)
                    print("\n[PAUSED_NEEDS_HUMAN] Gặp verify/captcha/2FA. Hoàn tất xác minh rồi Enter để tiếp tục...")
                    input()
                    q.storage.transition(job.id, "RETRYABLE")
                except Exception as exc:  # noqa: BLE001
                    self.logger.exception("Job %s failed", job.id)
                    q.mark_retryable(job, str(exc))
                    self._capture_failure_artifacts(page, job, exc)

            browser.close()
            storage.close()

    def _execute_job(self, adapter: "FlowAdapter", job: Job, image_paths: list[Path]) -> None:
        self.logger.info("Processing job %s", job.id)
        adapter.set_mode(job.mode)
        adapter.set_model(job.model)
        adapter.set_ratio(job.aspect_ratio)
        adapter.set_outputs_per_prompt(job.outputs_per_prompt)
        adapter.upload_assets_if_needed(job.mode, image_paths)
        adapter.set_prompt(job.prompt)
        adapter.submit_generate()
        adapter.wait_until_done()

        dated_dir = self.cfg.output_dir / datetime.now().strftime("%Y-%m-%d") / str(job.id)
        video_path = adapter.download_result(dated_dir)
        metadata = {
            "job_id": job.id,
            "prompt": job.prompt,
            "model": job.model,
            "aspect_ratio": job.aspect_ratio,
            "outputs_per_prompt": job.outputs_per_prompt,
            "state": "DONE",
            "video_path": str(video_path),
            "finished_at": datetime.utcnow().isoformat() + "Z",
        }
        (dated_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        storage = Storage(self.cfg.db_path)
        try:
            q = QueueManager(storage, self.cfg.retry_limit)
            q.mark_done(job, str(video_path))
        finally:
            storage.close()

    def _capture_failure_artifacts(self, page, job: Job, exc: Exception) -> None:
        stamp = int(time.time())
        root = self.cfg.logs_dir / f"job_{job.id}_{stamp}"
        root.mkdir(parents=True, exist_ok=True)
        screenshot_path = root / "error.png"
        html_path = root / "snapshot.html"
        txt_path = root / "error.txt"
        page.screenshot(path=str(screenshot_path), full_page=True)
        html_path.write_text(page.content(), encoding="utf-8")
        txt_path.write_text(str(exc), encoding="utf-8")
        self.logger.info("Captured failure artifacts at %s", root)

    def _discover_images(self) -> list[Path]:
        if not self.cfg.images_dir or not self.cfg.images_dir.exists():
            return []
        return sorted(
            p
            for p in self.cfg.images_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
