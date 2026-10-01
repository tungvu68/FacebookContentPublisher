"""OS-backed secret storage."""

from facebook_content_publisher.infrastructure.security.keyring_store import (
    WindowsCredentialSecretStore,
)

__all__ = ["WindowsCredentialSecretStore"]
