from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CCHAIR_", extra="ignore")

    app_name: str = "CoChairAI"
    database_url: str = "sqlite:///./data/cchair.db"
    ui_storage_secret: str = Field(default="development-only-change-me", min_length=16)
    scheduler_timezone: str = "UTC"
    reminder_scan_interval_minutes: int = Field(default=15, gt=0)
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, gt=0)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_from_address: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()