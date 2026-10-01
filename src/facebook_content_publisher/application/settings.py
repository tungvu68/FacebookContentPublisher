"""Typed, secret-free application settings persistence."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from facebook_content_publisher.application.translation.prompt import PROMPT_VERSION


class ApplicationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    translation_mode: str = Field(default="mock", pattern=r"^(mock|openai)$")
    openai_model: str = "gpt-5-mini"
    openai_timeout_seconds: float = Field(default=60, ge=5, le=600)
    max_concurrent_translations: int = Field(default=3, ge=1, le=10)
    global_translation_prompt: str = ""
    prompt_version: str = PROMPT_VERSION
    retry_max_attempts: int = Field(default=5, ge=1, le=10)
    retry_initial_delay_seconds: float = Field(default=30, ge=0.1, le=1800)
    retry_max_delay_seconds: float = Field(default=1800, ge=1, le=7200)
    retry_multiplier: float = Field(default=2, ge=1, le=10)
    scheduler_enabled: bool = True
    scheduler_poll_seconds: float = Field(default=5, ge=0.2, le=300)
    publication_concurrency: int = Field(default=2, ge=1, le=10)
    comment_concurrency: int = Field(default=2, ge=1, le=10)
    overdue_grace_minutes: int = Field(default=60, ge=0, le=10080)
    require_confirmation_after_overdue: bool = True
    notifications_enabled: bool = True
    minimize_to_tray: bool = True
    start_with_windows: bool = False
    facebook_provider_mode: str = Field(default="mock", pattern=r"^(mock|production)$")
    graph_api_version: str = Field(default="v24.0", pattern=r"^v\d+\.\d+$")
    meta_app_id: str = ""
    oauth_broker_url: str = ""
    facebook_timeout_seconds: float = Field(default=30, ge=5, le=300)
    facebook_upload_timeout_seconds: float = Field(default=300, ge=30, le=3600)
    background_page_validation: bool = False
    enable_production_publishing: bool = False
    lease_duration_seconds: int = Field(default=300, ge=30, le=3600)
    heartbeat_interval_seconds: int = Field(default=30, ge=5, le=600)
    graceful_shutdown_timeout_seconds: int = Field(default=10, ge=0, le=120)

    @field_validator("heartbeat_interval_seconds")
    @classmethod
    def heartbeat_shorter_than_lease(cls, value: int, info) -> int:
        lease = info.data.get("lease_duration_seconds", 300)
        if value >= lease:
            raise ValueError("Heartbeat interval must be shorter than lease duration")
        return value

    @field_validator("openai_model")
    @classmethod
    def model_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("OpenAI model cannot be blank")
        return value.strip()


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> ApplicationSettings:
        if not self.path.exists():
            return ApplicationSettings()
        return ApplicationSettings.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, settings: ApplicationSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(settings.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
