from __future__ import annotations

import importlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str


def _check_module(name: str) -> CheckResult:
    try:
        importlib.import_module(name)
        return CheckResult(name=name, ok=True, message="installed")
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name=name, ok=False, message=str(exc))


def _check_playwright_browser() -> CheckResult:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult("playwright-browser", False, f"cannot execute playwright check: {exc}")

    if result.returncode == 0:
        return CheckResult("playwright-browser", True, "chromium install command available")
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    msg = stderr or stdout or "playwright command failed"
    return CheckResult("playwright-browser", False, msg)


def run_doctor(config_path: Path | None = None) -> tuple[bool, list[CheckResult]]:
    checks: list[CheckResult] = []

    checks.append(CheckResult("python", sys.version_info >= (3, 11), f"{sys.version.split()[0]}"))
    for module in ["typer", "pydantic", "yaml", "playwright"]:
        checks.append(_check_module(module))
    checks.append(_check_playwright_browser())

    if config_path:
        exists = config_path.exists()
        checks.append(CheckResult("config", exists, f"{config_path} {'found' if exists else 'missing'}"))

    proxy_hint = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy_hint:
        checks.append(CheckResult("proxy", True, f"HTTPS_PROXY configured: {proxy_hint}"))
    else:
        checks.append(CheckResult("proxy", False, "HTTPS_PROXY is not set"))

    ok = all(c.ok for c in checks if c.name not in {"proxy", "python"})
    return ok, checks


def print_doctor_report(ok: bool, checks: list[CheckResult]) -> None:
    print("\n=== Flow Tool Doctor ===")
    for c in checks:
        marker = "OK" if c.ok else "FAIL"
        print(f"[{marker}] {c.name}: {c.message}")
    print("------------------------")
    print("READY" if ok else "NOT READY")
