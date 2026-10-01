"""Facebook-neutral request/result contracts and classified failures."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MediaSnapshot:
    path: Path
    mime_type: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PageAccessStatus:
    accessible: bool
    page_id: str
    message: str = ""


@dataclass(frozen=True, slots=True)
class PublishRequest:
    publication_id: str
    idempotency_key: str
    page_id: str
    post_text: str
    media_assets: tuple[MediaSnapshot, ...] = ()
    country_code: str = ""
    language_code: str = ""
    correlation_id: str = ""


@dataclass(frozen=True, slots=True)
class PublishResult:
    facebook_post_id: str
    published_at_utc: datetime
    facebook_post_url: str | None = None
    provider_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class CommentRequest:
    comment_job_id: str
    idempotency_key: str
    page_id: str
    facebook_post_id: str
    comment_text: str
    correlation_id: str = ""


@dataclass(frozen=True, slots=True)
class CommentResult:
    facebook_comment_id: str
    created_at_utc: datetime
    provider_request_id: str | None = None


class PublisherError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable=False, ambiguous=False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.ambiguous = ambiguous


class FacebookPublisher(Protocol):
    async def validate_page_access(self, page_id: str) -> PageAccessStatus: ...
    async def publish_text_post(self, request: PublishRequest) -> PublishResult: ...
    async def publish_photo_post(self, request: PublishRequest) -> PublishResult: ...
    async def publish_video_post(self, request: PublishRequest) -> PublishResult: ...
    async def create_comment(self, request: CommentRequest) -> CommentResult: ...
