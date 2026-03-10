from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Page


@dataclass
class SelectorCatalog:
    data: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> "SelectorCatalog":
        return cls(data=json.loads(path.read_text(encoding="utf-8")))

    def locate(self, page: Page, key: str):
        candidates = self.data.get(key, [])
        if not candidates:
            raise KeyError(f"Selector key missing: {key}")

        for sel in candidates:
            by = sel.get("by")
            if by == "role":
                locator = page.get_by_role(sel["role"], name=sel.get("name"), exact=sel.get("exact", False))
            elif by == "text":
                locator = page.get_by_text(sel["value"], exact=sel.get("exact", False))
            elif by == "placeholder":
                locator = page.get_by_placeholder(sel["value"], exact=sel.get("exact", False))
            elif by == "label":
                locator = page.get_by_label(sel["value"], exact=sel.get("exact", False))
            elif by == "css":
                locator = page.locator(sel["value"])
            else:
                continue
            if locator.count() > 0:
                return locator.first

        return page.locator("__not_found__")
