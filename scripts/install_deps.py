from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_PACKAGES = ["typer", "pydantic", "PyYAML", "playwright", "pyinstaller"]
MIRRORS = [
    "https://pypi.org/simple",
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
]


def run_cmd(args: list[str]) -> bool:
    print("+", " ".join(args))
    result = subprocess.run(args, check=False)
    return result.returncode == 0


def install_from_wheelhouse(wheelhouse: Path, packages: list[str]) -> bool:
    if not wheelhouse.exists():
        print(f"wheelhouse not found: {wheelhouse}")
        return False
    return run_cmd(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--user",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            *packages,
        ]
    )


def install_from_index(packages: list[str], index_url: str) -> bool:
    return run_cmd(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--user",
            "--index-url",
            index_url,
            *packages,
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Install dependencies for Flow tool (proxy/offline friendly)")
    parser.add_argument("--wheelhouse", type=Path, default=Path("wheelhouse"))
    parser.add_argument("--online-only", action="store_true", help="Skip offline wheelhouse install")
    args = parser.parse_args()

    packages = DEFAULT_PACKAGES

    if not args.online_only and install_from_wheelhouse(args.wheelhouse, packages):
        print("Installed from wheelhouse successfully.")
        return 0

    for mirror in MIRRORS:
        if install_from_index(packages, mirror):
            print(f"Installed from {mirror}")
            return 0

    print("Failed to install dependencies from wheelhouse and all mirrors.")
    print("Action: prepare a local wheelhouse then run:")
    print("  python scripts/install_deps.py --wheelhouse wheelhouse")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
