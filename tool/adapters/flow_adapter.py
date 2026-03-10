from __future__ import annotations

import logging
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, TimeoutError as PwTimeoutError

from tool.config import AppConfig
from tool.selectors import SelectorCatalog

HUMAN_VERIFY_KEYWORDS = [
    "verify",
    "captcha",
    "unusual traffic",
    "xác minh",
    "2-step",
    "2fa",
]


class NeedsHumanVerification(Exception):
    pass


class FlowAdapter:
    def __init__(self, page: Page, context: BrowserContext, config: AppConfig, selectors: SelectorCatalog) -> None:
        self.page = page
        self.context = context
        self.cfg = config
        self.sel = selectors
        self.log = logging.getLogger(self.__class__.__name__)

    def open_base(self) -> None:
        self.page.goto(self.cfg.base_url, wait_until="domcontentloaded", timeout=self.cfg.timeouts.navigation_ms)

    def ensure_logged_in(self) -> None:
        if self._needs_human_check():
            raise NeedsHumanVerification("Captcha/verify detected before login.")

        marker = self.sel.locate(self.page, "logged_in_marker")
        if marker.count() > 0:
            return

        print("\n[HUMAN ACTION] Vui lòng đăng nhập Google trong cửa sổ trình duyệt, rồi nhấn Enter...")
        input()
        self.page.wait_for_timeout(1000)
        if self._needs_human_check():
            raise NeedsHumanVerification("Verification gate detected after login step.")

    def set_mode(self, mode: str) -> None:
        mode_map = {
            "text2video": "mode_text2video",
            "components": "mode_components",
            "frames": "mode_frames",
        }
        self.sel.locate(self.page, "mode_dropdown").click(timeout=self.cfg.timeouts.action_ms)
        self.sel.locate(self.page, mode_map[mode]).click(timeout=self.cfg.timeouts.action_ms)

    def set_model(self, model_name: str) -> None:
        self.sel.locate(self.page, "model_dropdown").click(timeout=self.cfg.timeouts.action_ms)
        self.page.get_by_text(model_name, exact=False).first.click(timeout=self.cfg.timeouts.action_ms)

    def set_ratio(self, ratio: str) -> None:
        self.sel.locate(self.page, "aspect_dropdown").click(timeout=self.cfg.timeouts.action_ms)
        ratio_label = "Khổ ngang (16:9)" if ratio == "16:9" else "Khổ dọc (9:16)"
        self.page.get_by_text(ratio_label, exact=False).first.click(timeout=self.cfg.timeouts.action_ms)

    def set_outputs_per_prompt(self, count: int) -> None:
        self.sel.locate(self.page, "outputs_dropdown").click(timeout=self.cfg.timeouts.action_ms)
        self.page.get_by_text(str(count), exact=True).first.click(timeout=self.cfg.timeouts.action_ms)

    def upload_assets_if_needed(self, mode: str, image_paths: list[Path]) -> None:
        if mode not in {"components", "frames"}:
            return
        if not image_paths:
            raise RuntimeError("Mode components/frames yêu cầu images folder có file.")
        plus_btn = self.sel.locate(self.page, "add_assets_button")
        plus_btn.click(timeout=self.cfg.timeouts.action_ms)
        file_input = self.sel.locate(self.page, "file_input")
        file_input.set_input_files([str(p) for p in image_paths])

    def set_prompt(self, prompt: str) -> None:
        textbox = self.sel.locate(self.page, "prompt_input")
        textbox.click(timeout=self.cfg.timeouts.action_ms)
        textbox.fill(prompt, timeout=self.cfg.timeouts.action_ms)

    def submit_generate(self) -> None:
        self.sel.locate(self.page, "submit_button").click(timeout=self.cfg.timeouts.action_ms)

    def wait_until_done(self) -> None:
        import time

        deadline = time.monotonic() + self.cfg.timeouts.generation_ms / 1000
        while time.monotonic() < deadline:
            if self._needs_human_check():
                raise NeedsHumanVerification("Captcha/verify detected during generation.")
            preview = self.sel.locate(self.page, "preview_video")
            download = self.sel.locate(self.page, "download_button")
            if preview.count() > 0 and download.count() > 0:
                return
            self.page.wait_for_timeout(self.cfg.timeouts.poll_interval_ms)
        raise PwTimeoutError("Generation timeout")

    def download_result(self, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        with self.page.expect_download(timeout=self.cfg.timeouts.action_ms) as dl_info:
            self.sel.locate(self.page, "download_button").click()
        dl = dl_info.value
        suffix = Path(dl.suggested_filename).suffix or ".mp4"
        file_path = target_dir / f"video{suffix}"
        dl.save_as(str(file_path))
        return file_path

    def _needs_human_check(self) -> bool:
        body_text = (self.page.content() or "").lower()
        return any(k in body_text for k in HUMAN_VERIFY_KEYWORDS)
