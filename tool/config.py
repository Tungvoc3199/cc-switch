from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None

try:
    from pydantic import BaseModel, Field, ValidationError, field_validator
except ModuleNotFoundError:  # pragma: no cover
    BaseModel = None
    Field = None
    ValidationError = ValueError
    field_validator = None

Mode = Literal["text2video", "components", "frames"]
ModelName = Literal[
    "Veo 3.1 - Fast",
    "Veo 3.1 - Quality",
    "Veo 2 - Fast",
    "Veo 2 - Quality",
]
AspectRatio = Literal["16:9", "9:16"]

if BaseModel is not None:

    class TimeoutConfig(BaseModel):
        navigation_ms: int = 60_000
        action_ms: int = 25_000
        generation_ms: int = 600_000
        poll_interval_ms: int = 2_000


    class AppConfig(BaseModel):
        base_url: str = "https://labs.google/flow"
        mode: Mode = "text2video"
        model: ModelName = "Veo 3.1 - Fast"
        aspect_ratio: AspectRatio = "16:9"
        outputs_per_prompt: int = Field(default=1, ge=1, le=4)
        headless: bool = False
        profile_dir: Path = Path(".flow-profile")
        prompts_file: Path = Path("assets/prompts.example.txt")
        images_dir: Path | None = None
        output_dir: Path = Path("output")
        db_path: Path = Path("flow_jobs.sqlite3")
        selectors_path: Path = Path("assets/selectors.json")
        logs_dir: Path = Path("logs")
        retry_limit: int = Field(default=2, ge=0, le=10)
        timeouts: TimeoutConfig = TimeoutConfig()

        @field_validator("base_url")
        @classmethod
        def validate_url(cls, v: str) -> str:
            if not v.startswith("http"):
                raise ValueError("base_url must start with http/https")
            return v

else:

    @dataclass
    class TimeoutConfig:
        navigation_ms: int = 60_000
        action_ms: int = 25_000
        generation_ms: int = 600_000
        poll_interval_ms: int = 2_000


    @dataclass
    class AppConfig:
        base_url: str = "https://labs.google/flow"
        mode: Mode = "text2video"
        model: ModelName = "Veo 3.1 - Fast"
        aspect_ratio: AspectRatio = "16:9"
        outputs_per_prompt: int = 1
        headless: bool = False
        profile_dir: Path = Path(".flow-profile")
        prompts_file: Path = Path("assets/prompts.example.txt")
        images_dir: Path | None = None
        output_dir: Path = Path("output")
        db_path: Path = Path("flow_jobs.sqlite3")
        selectors_path: Path = Path("assets/selectors.json")
        logs_dir: Path = Path("logs")
        retry_limit: int = 2
        timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)


def _naive_yaml_parse(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    current_nested: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not raw.startswith(" ") and line.endswith(":"):
            key = line[:-1].strip()
            root[key] = {}
            current_nested = root[key]
            continue
        if ":" not in line:
            continue
        key, value = [x.strip() for x in line.split(":", 1)]
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        if value.lower() in {"true", "false"}:
            parsed: Any = value.lower() == "true"
        else:
            try:
                parsed = int(value)
            except ValueError:
                parsed = value
        if raw.startswith(" ") and current_nested is not None:
            current_nested[key] = parsed
        else:
            root[key] = parsed
            current_nested = None
    return root


def _coerce_paths(data: dict[str, Any]) -> dict[str, Any]:
    for key in ["profile_dir", "prompts_file", "images_dir", "output_dir", "db_path", "selectors_path", "logs_dir"]:
        if key in data and data[key] is not None:
            data[key] = Path(data[key])
    return data


def load_config(path: Path) -> AppConfig:
    try:
        raw = path.read_text(encoding="utf-8")
        if yaml is not None:
            data = yaml.safe_load(raw) or {}
        else:
            data = _naive_yaml_parse(raw)
        data = _coerce_paths(data)
        if BaseModel is not None:
            return AppConfig(**data)
        if "timeouts" in data and isinstance(data["timeouts"], dict):
            data["timeouts"] = TimeoutConfig(**data["timeouts"])
        return AppConfig(**data)
    except ValidationError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Cannot load config from {path}: {exc}") from exc
