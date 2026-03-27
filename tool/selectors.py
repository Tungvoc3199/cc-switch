from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page


class SelectorCatalog:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, list[dict[str, Any]]] = json.loads(path.read_text(encoding="utf-8"))

    def build_locator(self, page: Page, key: str) -> Locator:
        entries = self.data.get(key, [])
        if not entries:
            raise KeyError(f"selector key not found: {key}")

        locator: Locator | None = None
        for entry in entries:
            kind = entry.get("kind")
            if kind == "role":
                role = entry["role"]
                locator = page.get_by_role(role, name=entry.get("name"), exact=entry.get("exact", False))
            elif kind == "text":
                locator = page.get_by_text(entry["text"], exact=entry.get("exact", False))
            elif kind == "label":
                locator = page.get_by_label(entry["label"], exact=entry.get("exact", False))
            elif kind == "placeholder":
                locator = page.get_by_placeholder(entry["placeholder"])
            elif kind == "css":
                locator = page.locator(entry["css"])
            else:
                continue

            if locator and locator.count() > 0:
                return locator.first

        # fallback to first entry even if not visible; caller may wait/retry
        first = entries[0]
        if first["kind"] == "role":
            return page.get_by_role(first["role"], name=first.get("name"), exact=first.get("exact", False)).first
        if first["kind"] == "text":
            return page.get_by_text(first["text"], exact=first.get("exact", False)).first
        if first["kind"] == "label":
            return page.get_by_label(first["label"], exact=first.get("exact", False)).first
        if first["kind"] == "placeholder":
            return page.get_by_placeholder(first["placeholder"]).first
        return page.locator(first["css"]).first
