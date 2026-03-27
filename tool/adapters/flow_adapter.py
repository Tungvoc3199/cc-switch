from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, TimeoutError as PwTimeoutError, expect

from tool.config import AppConfig, RuntimeLabels
from tool.selectors import SelectorCatalog


class HumanVerificationRequired(Exception):
    pass


class FlowAdapter:
    def __init__(
        self,
        context: BrowserContext,
        page: Page,
        config: AppConfig,
        labels: RuntimeLabels,
        selectors: SelectorCatalog,
        logger,
    ):
        self.context = context
        self.page = page
        self.config = config
        self.labels = labels
        self.selectors = selectors
        self.logger = logger

    def open_base(self) -> None:
        self.page.goto(self.config.base_url, wait_until="domcontentloaded", timeout=self.config.timeouts.page_load_ms)

    def ensure_logged_in(self) -> None:
        if self._has_logged_in_marker():
            return
        print("\n[BYOA] Vui lòng đăng nhập Google trong cửa sổ trình duyệt vừa mở.")
        print("Sau khi đăng nhập thành công, quay lại terminal và nhấn Enter để tiếp tục...")
        input()
        self.page.wait_for_timeout(1000)
        if not self._has_logged_in_marker():
            raise RuntimeError("Không phát hiện trạng thái đăng nhập sau khi người dùng xác nhận.")

    def set_mode(self) -> None:
        combo = self.selectors.build_locator(self.page, "mode_dropdown")
        combo.click(timeout=self.config.timeouts.action_ms)
        self.page.get_by_text(self.labels.mode, exact=False).first.click(timeout=self.config.timeouts.action_ms)

    def set_model(self) -> None:
        combo = self.selectors.build_locator(self.page, "model_dropdown")
        combo.click(timeout=self.config.timeouts.action_ms)
        self.page.get_by_text(self.labels.model, exact=False).first.click(timeout=self.config.timeouts.action_ms)

    def set_ratio(self) -> None:
        combo = self.selectors.build_locator(self.page, "ratio_dropdown")
        combo.click(timeout=self.config.timeouts.action_ms)
        self.page.get_by_text(self.labels.aspect_ratio, exact=False).first.click(timeout=self.config.timeouts.action_ms)

    def set_outputs_per_prompt(self) -> None:
        combo = self.selectors.build_locator(self.page, "outputs_dropdown")
        combo.click(timeout=self.config.timeouts.action_ms)
        self.page.get_by_role("option", name=str(self.config.outputs_per_prompt)).first.click(
            timeout=self.config.timeouts.action_ms
        )

    def upload_assets_if_needed(self, files: list[str]) -> None:
        if self.config.mode == "text2video":
            return
        if not files:
            raise RuntimeError("Mode hiện tại yêu cầu assets nhưng không có images_dir hoặc file ảnh.")

        add_btn = self.selectors.build_locator(self.page, "asset_add_button")
        with self.page.expect_file_chooser(timeout=self.config.timeouts.action_ms) as fc_info:
            add_btn.click(timeout=self.config.timeouts.action_ms)
        chooser = fc_info.value
        chooser.set_files(files)
        self.page.wait_for_timeout(1200)

    def set_prompt(self, prompt: str) -> None:
        prompt_box = self.selectors.build_locator(self.page, "prompt_textarea")
        prompt_box.click(timeout=self.config.timeouts.action_ms)
        prompt_box.fill(prompt, timeout=self.config.timeouts.action_ms)

    def submit_generate(self) -> None:
        submit = self.selectors.build_locator(self.page, "submit_button")
        submit.click(timeout=self.config.timeouts.action_ms)

    def wait_until_done(self) -> None:
        start = time.time()
        poll_s = self.config.timeouts.poll_interval_ms / 1000

        while True:
            self._check_human_challenge()
            if self._is_done_signal_present():
                return
            if time.time() - start > self.config.timeouts.generate_ms / 1000:
                raise TimeoutError("Quá thời gian chờ render video.")
            time.sleep(poll_s)

    def download_result(self, job_dir: Path) -> Path:
        dl_btn = self.selectors.build_locator(self.page, "download_button")
        with self.page.expect_download(timeout=self.config.timeouts.action_ms) as dl_info:
            dl_btn.click(timeout=self.config.timeouts.action_ms)
        download = dl_info.value
        suggested = download.suggested_filename
        ext = Path(suggested).suffix or ".mp4"
        target = job_dir / f"video{ext}"
        download.save_as(str(target))
        return target

    def _has_logged_in_marker(self) -> bool:
        marker = self.selectors.build_locator(self.page, "logged_in_marker")
        try:
            return marker.is_visible(timeout=2000)
        except PwTimeoutError:
            return False

    def _is_done_signal_present(self) -> bool:
        preview = self.selectors.build_locator(self.page, "preview_duration_marker")
        download = self.selectors.build_locator(self.page, "download_button")
        try:
            return preview.is_visible(timeout=1000) and download.is_visible(timeout=1000)
        except PwTimeoutError:
            return False

    def _check_human_challenge(self) -> None:
        challenge = self.selectors.build_locator(self.page, "human_challenge_marker")
        if challenge.count() == 0:
            return
        if challenge.first.is_visible():
            raise HumanVerificationRequired(
                "Phát hiện verify/captcha/unusual traffic/2FA. Vui lòng xác minh thủ công rồi tiếp tục."
            )

    def ensure_page_ready(self) -> None:
        expect(self.page).to_have_url(lambda url: "labs.google" in url, timeout=self.config.timeouts.page_load_ms)
