"""Environment-backed application configuration."""

import os
from dataclasses import dataclass
from enum import StrEnum


class ServiceMode(StrEnum):
    """Supported external-service operating modes."""

    MOCK = "mock"
    PRODUCTION = "production"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime configuration with credential-free bootstrap defaults."""

    app_name: str = "Facebook Content Publisher"
    app_environment: str = "development"
    openai_mode: ServiceMode = ServiceMode.MOCK
    facebook_mode: ServiceMode = ServiceMode.MOCK

    @property
    def is_mock_mode(self) -> bool:
        return self.openai_mode is ServiceMode.MOCK and self.facebook_mode is ServiceMode.MOCK

    @classmethod
    def from_environment(cls) -> "AppConfig":
        """Create configuration without reading or requiring any credentials."""

        return cls(
            app_environment=os.getenv("FCP_APP_ENV", "development"),
            openai_mode=_read_mode("FCP_OPENAI_MODE"),
            facebook_mode=_read_mode("FCP_FACEBOOK_MODE"),
        )


def _read_mode(name: str) -> ServiceMode:
    value = os.getenv(name, ServiceMode.MOCK.value).strip().lower()
    try:
        return ServiceMode(value)
    except ValueError as error:
        allowed = ", ".join(mode.value for mode in ServiceMode)
        raise ValueError(f"{name} must be one of: {allowed}") from error
