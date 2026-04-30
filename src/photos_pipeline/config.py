"""Application settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings"]


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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object."""
    return Settings()
