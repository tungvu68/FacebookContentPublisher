"""Windows Credential Manager adapter through keyring."""

import keyring
from keyring.errors import KeyringError

SERVICE_NAME = "FacebookContentPublisher/v1"


class SecretStoreError(RuntimeError):
    pass


class WindowsCredentialSecretStore:
    def get_secret(self, name: str) -> str | None:
        try:
            return keyring.get_password(SERVICE_NAME, name)
        except KeyringError as error:
            raise SecretStoreError("Windows Credential Manager is unavailable") from error

    def set_secret(self, name: str, value: str) -> None:
        if not value.strip():
            raise ValueError("secret cannot be empty")
        try:
            keyring.set_password(SERVICE_NAME, name, value.strip())
        except KeyringError as error:
            raise SecretStoreError("Unable to save credential securely") from error

    def delete_secret(self, name: str) -> None:
        try:
            if self.has_secret(name):
                keyring.delete_password(SERVICE_NAME, name)
        except KeyringError as error:
            raise SecretStoreError("Unable to delete credential") from error

    def has_secret(self, name: str) -> bool:
        return self.get_secret(name) is not None
