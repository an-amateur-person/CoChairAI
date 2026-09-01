from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PPM_", extra="ignore")

    app_name: str = "CoChairAI"
    database_url: str = "sqlite:///./data/powerplatform_migration.db"
    ui_storage_secret: str = Field(default="development-only-change-me", min_length=16)
    scheduler_timezone: str = "UTC"
    import_directory: Path = Path("data/import")
    unpack_directory: Path = Path("data/unpacked")
    max_import_size_mb: int = Field(default=100, gt=0)
    reminder_scan_interval_minutes: int = Field(default=15, gt=0)
    solution_export_directory: Path = Path("data/unpacked")


@lru_cache
def get_settings() -> Settings:
    return Settings()