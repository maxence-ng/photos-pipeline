"""Application settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ScorerMode = Literal["nima", "clip"]
SCORER_MODES: tuple[ScorerMode, ...] = ("nima", "clip")
DEFAULT_SCORER_MODE: ScorerMode = "nima"
DEFAULT_SCORER_WEIGHTS_PATH = Path.home() / ".photos_pipeline" / "models" / "nima_weights.pth"
DEFAULT_SCORER_WEIGHTS_URL = (
    "https://s3-us-west-1.amazonaws.com/models-nima/pretrain-model.pth"
)
DEFAULT_SCORER_CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
DEFAULT_SCORER_BATCH_SIZE = 16
DEFAULT_SCORER_DEVICE = "auto"

__all__ = [
    "DEFAULT_SCORER_BATCH_SIZE",
    "DEFAULT_SCORER_CLIP_MODEL_NAME",
    "DEFAULT_SCORER_DEVICE",
    "DEFAULT_SCORER_MODE",
    "DEFAULT_SCORER_WEIGHTS_PATH",
    "DEFAULT_SCORER_WEIGHTS_URL",
    "SCORER_MODES",
    "ScorerMode",
    "Settings",
    "get_settings",
]


class Settings(BaseSettings):
    """Base configuration shared by CLI and API entry points."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PHOTOS_PIPELINE_",
        extra="ignore",
    )

    app_name: str = "photos-pipeline"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    blur_threshold: float = Field(default=100.0, gt=0, description="Laplacian variance threshold; images below this are flagged as blurry.")
    duplicate_threshold: int = Field(default=10, ge=1, description="Maximum Hamming distance between two image hashes to be considered duplicates.")
    duplicate_hash_algorithm: str = Field(default="phash", description="Perceptual hash algorithm: 'phash', 'dhash', or 'ahash'.")
    duplicate_burst_gap_seconds: float = Field(default=3.0, ge=0, description="Two images whose timestamps differ by more than 0 and less than this value (seconds) are treated as burst/bracketing shots and are never considered duplicates.")
    burst_gap_seconds: float = Field(default=2.0, ge=0, description="Maximum time gap in seconds between images in the same burst sequence.")
    burst_blur_weight: float = Field(default=0.6, ge=0, le=1, description="Relative weight of blur score in the burst composite score.")
    burst_aesthetic_weight: float = Field(default=0.4, ge=0, le=1, description="Relative weight of aesthetic score in the burst composite score.")
    scorer_mode: ScorerMode = Field(
        default=DEFAULT_SCORER_MODE,
        description="Aesthetic scorer backend to use: 'nima' or 'clip'.",
    )
    scorer_weights_path: Path = Field(
        default=DEFAULT_SCORER_WEIGHTS_PATH,
        description="Local cache path for aesthetic scorer weights.",
    )
    scorer_weights_url: str = Field(
        default=DEFAULT_SCORER_WEIGHTS_URL,
        description="Default download URL for aesthetic scorer weights.",
    )
    scorer_clip_model_name: str = Field(
        default=DEFAULT_SCORER_CLIP_MODEL_NAME,
        description="Hugging Face model identifier used when scorer_mode='clip'.",
    )
    scorer_batch_size: int = Field(
        default=DEFAULT_SCORER_BATCH_SIZE,
        ge=1,
        description="Maximum number of thumbnails to score per inference batch.",
    )
    scorer_device: str = Field(
        default=DEFAULT_SCORER_DEVICE,
        description="Preferred inference device ('auto', 'cpu', 'cuda', etc.).",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object."""
    return Settings()
