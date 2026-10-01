"""Deterministic, offline Facebook publisher."""

import asyncio
from collections import deque
from datetime import UTC, datetime
from hashlib import sha256

from facebook_content_publisher.application.facebook import (
    CommentRequest,
    CommentResult,
    PageAccessStatus,
    PublisherError,
    PublishRequest,
    PublishResult,
)


class MockFacebookPublisher:
    def __init__(self, outcomes=(), delay_seconds: float = 0, clock=None):
        self.outcomes = deque(outcomes)
        self.delay_seconds = delay_seconds
        self.clock = clock or (lambda: datetime.now(UTC))
        self.call_count = 0
        self._results = {}

    async def validate_page_access(self, page_id: str) -> PageAccessStatus:
        return PageAccessStatus(bool(page_id.strip()), page_id, "MOCK FACEBOOK MODE")

    async def _run(self, key: str, prefix: str):
        self.call_count += 1
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if key in self._results:
            return self._results[key]
        outcome = self.outcomes.popleft() if self.outcomes else "success"
        failures = {
            "connection": PublisherError("CONNECTION", "Mock connection failure", retryable=True),
            "rate_limit": PublisherError("RATE_LIMIT", "Mock rate limit", retryable=True),
            "server": PublisherError("SERVER", "Mock temporary server error", retryable=True),
            "timeout": PublisherError("TIMEOUT", "Mock timeout", ambiguous=True),
            "unknown": PublisherError("UNKNOWN", "Mock delivery is ambiguous", ambiguous=True),
            "auth": PublisherError("AUTH", "Mock authentication failure"),
            "permission": PublisherError("PERMISSION", "Mock permission failure"),
            "invalid_content": PublisherError("INVALID_CONTENT", "Mock invalid content"),
            "invalid_media": PublisherError("INVALID_MEDIA", "Mock invalid media"),
        }
        if outcome in failures:
            raise failures[outcome]
        value = f"MOCK-{prefix}-{sha256(key.encode()).hexdigest()[:16].upper()}"
        self._results[key] = value
        return value

    async def publish_text_post(self, request: PublishRequest) -> PublishResult:
        post_id = await self._run(request.idempotency_key, "POST")
        return PublishResult(
            post_id, self.clock(), f"https://mock.facebook.invalid/{post_id}", "MOCK-REQ"
        )

    async def publish_photo_post(self, request: PublishRequest) -> PublishResult:
        return await self.publish_text_post(request)

    async def publish_video_post(self, request: PublishRequest) -> PublishResult:
        return await self.publish_text_post(request)

    async def create_comment(self, request: CommentRequest) -> CommentResult:
        comment_id = await self._run(request.idempotency_key, "COMMENT")
        return CommentResult(comment_id, self.clock(), "MOCK-REQ")
