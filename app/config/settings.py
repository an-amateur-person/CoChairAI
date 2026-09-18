from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CCHAIR_", extra="ignore")

    app_name: str = "CoChairAI"
    database_url: str = "sqlite:///./data/cchair.db"
    ui_storage_secret: str = Field(default="development-only-change-me", min_length=16)
    scheduler_timezone: str = "UTC"
    meeting_timezone: str = "Europe/Berlin"
    reminder_scan_interval_minutes: int = Field(default=15, gt=0)
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, gt=0)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_from_address: str | None = None
    foundry_project_endpoint: str = "https://foundry-mbg.services.ai.azure.com/api/projects/proj-default"
    foundry_data_agent_name: str = "DataAgent"
    foundry_minutes_agent_name: str = "MinutesAgent"
    foundry_presentation_agent_name: str = "PresentationAgent"
    foundry_agent_version: str = "2"

    # Microsoft Entra sign-in. Users and documents live in the corporate tenant,
    # which is deliberately separate from the Foundry tenant used for AI calls.
    auth_enabled: bool = False
    auth_tenant_id: str | None = None
    auth_client_id: str | None = None
    auth_client_secret: str | None = None
    auth_redirect_path: str = "/auth/callback"

    # Identity assumed only when auth_enabled is False, for local development.
    dev_user_upn: str = "local.developer@example.com"
    dev_user_name: str = "Local Developer"

    # Comma-separated UPNs allowed to approve. Empty means every signed-in user may approve.
    approver_upns: str = ""

    @property
    def approvers(self) -> set[str]:
        return {value.strip().lower() for value in self.approver_upns.split(",") if value.strip()}

    @property
    def auth_authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.auth_tenant_id}"

    def auth_is_configured(self) -> bool:
        return bool(self.auth_tenant_id and self.auth_client_id and self.auth_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()