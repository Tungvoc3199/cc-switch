from __future__ import annotations

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from playwright.sync_api import sync_playwright

from tool.adapters.flow_adapter import FlowAdapter, HumanVerificationRequired
from tool.config import AppConfig, to_runtime_labels
from tool.queue import JobQueue
from tool.selectors import SelectorCatalog
from tool.storage import Job


class FlowRunner:
    def __init__(self, config: AppConfig, queue: JobQueue):
        self.config = config
        self.queue = queue
        self.logger = _build_logger(config.log_dir)
        self.selectors = SelectorCatalog(config.selectors_file)

    def run(self) -> None:
        recovered = self.queue.recover_after_crash()
        if recovered:
            self.logger.warning("Recovered %s interrupted RUNNING job(s).", recovered)

        labels = to_runtime_labels(self.config)

        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                user_data_dir=str(self.config.profile_dir),
                headless=self.config.headless,
                accept_downloads=True,
            )
            if self.config.headless:
                self.logger.warning("headless=true có thể dễ bị anti-bot chặn.")
            page = context.pages[0] if context.pages else context.new_page()

            adapter = FlowAdapter(context, page, self.config, labels, self.selectors, self.logger)
            adapter.open_base()
            adapter.ensure_page_ready()
            adapter.ensure_logged_in()
            adapter.set_mode()
            adapter.set_model()
            adapter.set_ratio()
            adapter.set_outputs_per_prompt()

            while True:
                job = self.queue.next()
                if not job:
                    break
                self._run_one_job(adapter, job)

            context.close()

    def _run_one_job(self, adapter: FlowAdapter, job: Job) -> None:
        self.queue.mark_running(job)
        started = datetime.utcnow().isoformat()
        day_folder = datetime.utcnow().strftime("%Y-%m-%d")
        job_dir = self.config.output_dir / day_folder / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "job_id": job.id,
            "prompt": job.prompt,
            "model": self.config.model,
            "aspect_ratio": self.config.aspect_ratio,
            "outputs_per_prompt": self.config.outputs_per_prompt,
            "mode": self.config.mode,
            "started_at": started,
            "status": "RUNNING",
        }

        assets = _resolve_assets(self.config.images_dir)

        try:
            adapter.upload_assets_if_needed(assets)
            adapter.set_prompt(job.prompt)
            adapter.submit_generate()
            adapter.wait_until_done()
            video_path = adapter.download_result(job_dir)

            metadata.update(
                {
                    "status": "DONE",
                    "finished_at": datetime.utcnow().isoformat(),
                    "video_path": str(video_path),
                }
            )
            (job_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            self.queue.mark_done(job, metadata)
            self.logger.info("Job %s DONE -> %s", job.id, video_path)
        except HumanVerificationRequired as exc:
            self._capture_debug_artifacts(adapter.page, job_dir, "human_verification")
            metadata.update(
                {
                    "status": "PAUSED_NEEDS_HUMAN",
                    "finished_at": datetime.utcnow().isoformat(),
                    "error": str(exc),
                }
            )
            (job_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            self.queue.mark_pause_human(job, str(exc), metadata=metadata)
            self.logger.warning("Job %s paused: %s", job.id, exc)

            print("\n[HUMAN ACTION REQUIRED]")
            print(str(exc))
            print("Hãy xử lý xác minh trong browser, rồi nhấn Enter để tiếp tục job kế tiếp...")
            input()
        except Exception as exc:  # noqa: BLE001
            self._capture_debug_artifacts(adapter.page, job_dir, "error")
            metadata.update(
                {
                    "status": "RETRYABLE",
                    "finished_at": datetime.utcnow().isoformat(),
                    "error": str(exc),
                }
            )
            (job_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            self.queue.mark_retryable(job, str(exc), metadata=metadata)
            self.logger.exception("Job %s failed: %s", job.id, exc)

    def print_summary(self) -> None:
        stats = self.queue.stats()
        self.logger.info(
            "Summary => total=%s done=%s failed=%s paused=%s",
            stats.total,
            stats.done,
            stats.failed,
            stats.paused,
        )

    def _capture_debug_artifacts(self, page, job_dir: Path, prefix: str) -> None:
        screenshot_path = job_dir / f"{prefix}.png"
        html_path = job_dir / f"{prefix}.html"
        page.screenshot(path=str(screenshot_path), full_page=True)
        html_path.write_text(page.content(), encoding="utf-8")


def _resolve_assets(images_dir: Path | None) -> list[str]:
    if not images_dir:
        return []
    if not images_dir.exists():
        return []
    files = sorted(
        [
            p
            for p in images_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ]
    )
    return [str(p.resolve()) for p in files]


def _build_logger(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger("flow-automation")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream)
    return logger
