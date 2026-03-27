from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


Mode = Literal["text2video", "components", "frames"]
ModelName = Literal["veo31_fast", "veo31_quality", "veo2_fast", "veo2_quality"]
AspectRatio = Literal["16:9", "9:16"]


class TimeoutConfig(BaseModel):
    page_load_ms: int = 60_000
    action_ms: int = 30_000
    generate_ms: int = 900_000
    poll_interval_ms: int = 2_000


class AppConfig(BaseModel):
    base_url: str = "https://labs.google/flow"
    mode: Mode = "text2video"
    model: ModelName = "veo31_fast"
    aspect_ratio: AspectRatio = "16:9"
    outputs_per_prompt: int = Field(default=1, ge=1, le=4)
    headless: bool = False
    profile_dir: Path = Path("./runtime/profile")
    prompts_file: Path = Path("./assets/prompts.txt")
    images_dir: Path | None = None
    selectors_file: Path = Path("./assets/selectors.json")
    database_path: Path = Path("./runtime/jobs.db")
    output_dir: Path = Path("./output")
    log_dir: Path = Path("./runtime/logs")
    retry_limit: int = Field(default=2, ge=0, le=10)
    timeouts: TimeoutConfig = TimeoutConfig()

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        if not value.startswith("http"):
            raise ValueError("base_url must start with http/https")
        return value


class RuntimeLabels(BaseModel):
    mode: str
    model: str
    aspect_ratio: str


MODE_LABEL_MAP = {
    "text2video": "Từ văn bản sang video",
    "components": "Tạo video từ các thành phần",
    "frames": "Tạo video từ các khung hình",
}

MODEL_LABEL_MAP = {
    "veo31_fast": "Veo 3.1 - Fast",
    "veo31_quality": "Veo 3.1 - Quality",
    "veo2_fast": "Veo 2 - Fast",
    "veo2_quality": "Veo 2 - Quality",
}

RATIO_LABEL_MAP = {
    "16:9": "Khổ ngang (16:9)",
    "9:16": "Khổ dọc (9:16)",
}


def load_config(path: Path) -> AppConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config = AppConfig.model_validate(data)

    config.profile_dir.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)
    config.database_path.parent.mkdir(parents=True, exist_ok=True)

    return config


def to_runtime_labels(config: AppConfig) -> RuntimeLabels:
    return RuntimeLabels(
        mode=MODE_LABEL_MAP[config.mode],
        model=MODEL_LABEL_MAP[config.model],
        aspect_ratio=RATIO_LABEL_MAP[config.aspect_ratio],
    )
