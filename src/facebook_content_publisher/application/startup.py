"""Start-with-Windows abstraction with a test-safe in-memory implementation."""

import sys
from pathlib import Path
from typing import Protocol

APP_VALUE_NAME = "FacebookContentPublisher"


def startup_command(executable_path: Path) -> str:
    return f'"{executable_path.resolve()}"'


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


class StartupManager(Protocol):
    def is_enabled(self) -> bool: ...
    def enable(self, executable_path: Path) -> None: ...
    def disable(self) -> None: ...


class InMemoryStartupManager:
    def __init__(self) -> None:
        self.command: str | None = None

    def is_enabled(self) -> bool:
        return self.command is not None

    def enable(self, executable_path: Path) -> None:
        self.command = startup_command(executable_path)

    def disable(self) -> None:
        self.command = None


class WindowsStartupManager:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def is_enabled(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key_path) as key:
                winreg.QueryValueEx(key, APP_VALUE_NAME)
            return True
        except FileNotFoundError:
            return False

    def enable(self, executable_path: Path) -> None:
        if not is_packaged():
            raise RuntimeError("Start with Windows is available only in the packaged app")
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.key_path) as key:
            winreg.SetValueEx(
                key, APP_VALUE_NAME, 0, winreg.REG_SZ, startup_command(executable_path)
            )

    def disable(self) -> None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self.key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, APP_VALUE_NAME)
        except FileNotFoundError:
            return
