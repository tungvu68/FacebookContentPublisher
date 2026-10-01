import pytest
from pydantic import ValidationError

from facebook_content_publisher.application.settings import ApplicationSettings
from facebook_content_publisher.application.startup import (
    InMemoryStartupManager,
    startup_command,
)
from facebook_content_publisher.infrastructure.facebook import (
    FacebookProductionNotConfigured,
    MockFacebookPublisher,
    create_facebook_publisher,
)
from facebook_content_publisher.ui.job_dialogs import safe_diagnostics


def test_scheduler_settings_validate_heartbeat_and_lease():
    with pytest.raises(ValidationError):
        ApplicationSettings(lease_duration_seconds=30, heartbeat_interval_seconds=30)


def test_startup_manager_is_scoped_and_quotes_path(tmp_path):
    executable = tmp_path / "Folder With Spaces" / "app.exe"
    manager = InMemoryStartupManager()
    manager.enable(executable)
    assert manager.is_enabled()
    assert manager.command == startup_command(executable)
    assert manager.command.startswith('"') and manager.command.endswith('"')
    manager.disable()
    assert not manager.is_enabled()


def test_provider_factory_mock_and_production_fail_closed():
    assert isinstance(create_facebook_publisher("mock"), MockFacebookPublisher)
    with pytest.raises(
        FacebookProductionNotConfigured,
        match="Facebook production connection is not configured",
    ):
        create_facebook_publisher("graph_api")


def test_safe_diagnostics_omits_content_and_metadata_payload():
    result = safe_diagnostics(
        {
            "id": "1",
            "post_text_snapshot": "private post",
            "comment_text": "private comment",
        },
        [{"event_type": "TEST", "metadata_json": '{"token":"secret"}'}],
    )
    assert "private post" not in result
    assert "private comment" not in result
    assert "secret" not in result
