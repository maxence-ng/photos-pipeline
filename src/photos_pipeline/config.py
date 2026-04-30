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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object."""
    return Settings()
