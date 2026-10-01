from pathlib import Path

import pytest
from pydantic import ValidationError

from facebook_content_publisher.application.secrets import InMemorySecretStore, mask_secret
from facebook_content_publisher.application.settings import ApplicationSettings, SettingsStore


def test_in_memory_secret_store_and_mask() -> None:
    store = InMemorySecretStore()
    assert not store.has_secret("key")
    store.set_secret("key", "sensitive-value")
    assert store.get_secret("key") == "sensitive-value"
    assert "sensitive-value" not in mask_secret(True)
    store.delete_secret("key")
    assert not store.has_secret("key")


def test_settings_persist_without_api_key(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    settings = ApplicationSettings(translation_mode="openai", openai_model="gpt-test")
    store.save(settings)
    assert store.load() == settings
    text = path.read_text(encoding="utf-8")
    assert "api_key" not in text and "sensitive" not in text


@pytest.mark.parametrize(
    "values",
    [
        {"openai_model": " "},
        {"max_concurrent_translations": 0},
        {"openai_timeout_seconds": 1},
        {"retry_max_attempts": 0},
    ],
)
def test_settings_validation(values) -> None:
    with pytest.raises(ValidationError):
        ApplicationSettings(**values)
