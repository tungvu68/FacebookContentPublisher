import asyncio
from datetime import UTC, datetime

import pytest

from facebook_content_publisher.application.facebook import (
    CommentRequest,
    PublisherError,
    PublishRequest,
)
from facebook_content_publisher.application.scheduler import retry_delay, sanitize_error
from facebook_content_publisher.domain.enums import CommentJobStatus, PublicationStatus
from facebook_content_publisher.domain.job_state import InvalidTransition, ensure_transition
from facebook_content_publisher.infrastructure.facebook import MockFacebookPublisher


def test_state_machines_reject_invalid_transitions():
    ensure_transition(PublicationStatus.READY, PublicationStatus.RUNNING)
    ensure_transition(CommentJobStatus.PENDING, CommentJobStatus.RUNNING)
    with pytest.raises(InvalidTransition):
        ensure_transition(PublicationStatus.PUBLISHED, PublicationStatus.RUNNING)


def test_backoff_is_bounded_and_deterministic():
    assert retry_delay(1, rng=lambda: 0.5) == 30
    assert retry_delay(10, rng=lambda: 0.5) == 1800


def test_error_sanitization_redacts_secrets():
    assert sanitize_error("authorization: Bearer secret") == "Sensitive provider error was redacted"


def test_mock_provider_is_offline_deterministic_and_idempotent():
    def clock():
        return datetime(2026, 1, 1, tzinfo=UTC)

    provider = MockFacebookPublisher(clock=clock)
    request = PublishRequest("p1", "same-key", "page", "hello")
    first = asyncio.run(provider.publish_text_post(request))
    second = asyncio.run(provider.publish_text_post(request))
    assert first.facebook_post_id == second.facebook_post_id
    assert first.facebook_post_id.startswith("MOCK-POST-")
    assert provider.call_count == 2


def test_mock_unknown_result_is_not_retryable():
    provider = MockFacebookPublisher(["unknown"])
    request = CommentRequest("c1", "key", "page", "post", "comment")
    with pytest.raises(PublisherError) as caught:
        asyncio.run(provider.create_comment(request))
    assert caught.value.ambiguous is True
    assert caught.value.retryable is False
