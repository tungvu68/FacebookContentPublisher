import pytest

from facebook_content_publisher.config import AppConfig, ServiceMode


def test_configuration_defaults_to_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FCP_OPENAI_MODE", raising=False)
    monkeypatch.delenv("FCP_FACEBOOK_MODE", raising=False)

    config = AppConfig.from_environment()

    assert config.openai_mode is ServiceMode.MOCK
    assert config.facebook_mode is ServiceMode.MOCK
    assert config.is_mock_mode


def test_invalid_mode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FCP_OPENAI_MODE", "unexpected")

    with pytest.raises(ValueError, match="FCP_OPENAI_MODE"):
        AppConfig.from_environment()
