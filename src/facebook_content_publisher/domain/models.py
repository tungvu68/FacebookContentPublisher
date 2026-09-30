"""Pure Python domain entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from facebook_content_publisher.domain.enums import (
    CampaignStatus,
    CommentJobStatus,
    LogLevel,
    MediaType,
    PublicationStatus,
    PublishMode,
    TranslationStatus,
)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


@dataclass(slots=True)
class CountryProfile:
    code: str
    country_name: str
    language_code: str
    language_name: str
    timezone: str
    default_comment_template: str
    id: UUID = field(default_factory=uuid4)
    facebook_page_id: str | None = None
    facebook_page_name: str | None = None
    default_link: str | None = None
    translation_prompt_override: str | None = None
    default_hashtags: str | None = None
    native_reader_label: str = ""
    localization_level: str = "natural"
    enabled: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Campaign:
    title: str
    source_text: str
    id: UUID = field(default_factory=uuid4)
    source_language: str = "en"
    status: CampaignStatus = CampaignStatus.DRAFT
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class CampaignTarget:
    campaign_id: UUID
    country_profile_id: UUID
    id: UUID = field(default_factory=uuid4)
    link_override: str | None = None
    comment_delay_minutes: int = 330
    delayed_comment_enabled: bool = True
    publish_mode: PublishMode = PublishMode.IMMEDIATE
    scheduled_at_utc: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class MediaAsset:
    campaign_id: UUID
    file_name: str
    absolute_path: str
    media_type: MediaType
    mime_type: str
    file_size: int
    sha256: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class LocalizedContent:
    campaign_id: UUID
    country_profile_id: UUID
    language_code: str
    id: UUID = field(default_factory=uuid4)
    translated_text: str = ""
    comment_text: str = ""
    hashtags: str = ""
    link_url: str | None = None
    translation_status: TranslationStatus = TranslationStatus.PENDING
    quality_warnings: str = ""
    prompt_version: str | None = None
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    approved_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Publication:
    campaign_id: UUID
    localized_content_id: UUID
    country_profile_id: UUID
    facebook_page_id: str
    idempotency_key: str
    id: UUID = field(default_factory=uuid4)
    publish_mode: PublishMode = PublishMode.IMMEDIATE
    scheduled_at_utc: datetime | None = None
    published_at_utc: datetime | None = None
    facebook_post_id: str | None = None
    facebook_post_url: str | None = None
    status: PublicationStatus = PublicationStatus.DRAFT
    attempt_count: int = 0
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class CommentJob:
    publication_id: UUID
    execute_at_utc: datetime
    comment_text: str
    link_url: str | None
    idempotency_key: str
    id: UUID = field(default_factory=uuid4)
    facebook_comment_id: str | None = None
    status: CommentJobStatus = CommentJobStatus.PENDING
    attempt_count: int = 0
    next_retry_at_utc: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class ActivityLog:
    level: LogLevel
    event_type: str
    safe_message: str
    id: UUID = field(default_factory=uuid4)
    entity_type: str | None = None
    entity_id: UUID | None = None
    created_at: datetime = field(default_factory=utc_now)
