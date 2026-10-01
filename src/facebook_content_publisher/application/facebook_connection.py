"""OAuth broker and Page credential contracts; live OAuth is disabled in 7A."""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from facebook_content_publisher.application.secrets import SecretStore

PAGE_TOKEN_PREFIX = "facebook.page_token."


class PageCredentialStore:
    def __init__(self, secret_store: SecretStore):
        self.secrets = secret_store

    @staticmethod
    def alias(page_id: str) -> str:
        return f"{PAGE_TOKEN_PREFIX}{page_id}"

    def save(self, page_id: str, token: str) -> str:
        alias = self.alias(page_id)
        self.secrets.set_secret(alias, token)
        return alias

    def get(self, page_id: str) -> str | None:
        return self.secrets.get_secret(self.alias(page_id))

    def delete(self, page_id: str) -> None:
        self.secrets.delete_secret(self.alias(page_id))


@dataclass(frozen=True, slots=True)
class OAuthResult:
    user_access_token: str
    expires_at: datetime | None = None


class OAuthBroker(Protocol):
    async def exchange(self, code: str, redirect_uri: str) -> OAuthResult: ...


class HttpsOAuthBroker:
    def __init__(self, url: str):
        self.url = url

    async def exchange(self, code: str, redirect_uri: str) -> OAuthResult:
        raise RuntimeError("HTTPS OAuth broker is not configured for Phase 7A")


class MockOAuthBroker:
    async def exchange(self, code: str, redirect_uri: str) -> OAuthResult:
        if code != "mock-valid-code":
            raise ValueError("Invalid mock authorization code")
        return OAuthResult("mock-user-token", datetime.now(UTC) + timedelta(hours=1))


class OAuthStateStore:
    def __init__(self, clock=None):
        self.clock = clock or (lambda: datetime.now(UTC))
        self._states = {}

    def issue(self, lifetime_seconds=300) -> str:
        value = secrets.token_urlsafe(32)
        self._states[value] = self.clock() + timedelta(seconds=lifetime_seconds)
        return value

    def consume(self, value: str) -> None:
        expires = self._states.pop(value, None)
        if expires is None or expires < self.clock():
            raise ValueError("Invalid or expired OAuth state")
