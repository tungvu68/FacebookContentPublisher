"""Secret storage contracts and test implementation."""

from typing import Protocol


class SecretStore(Protocol):
    def get_secret(self, name: str) -> str | None: ...

    def set_secret(self, name: str, value: str) -> None: ...

    def delete_secret(self, name: str) -> None: ...

    def has_secret(self, name: str) -> bool: ...


class InMemorySecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get_secret(self, name: str) -> str | None:
        return self._values.get(name)

    def set_secret(self, name: str, value: str) -> None:
        if not value:
            raise ValueError("secret cannot be empty")
        self._values[name] = value

    def delete_secret(self, name: str) -> None:
        self._values.pop(name, None)

    def has_secret(self, name: str) -> bool:
        return name in self._values


def mask_secret(configured: bool) -> str:
    return "Configured (••••••••)" if configured else "Not configured"
