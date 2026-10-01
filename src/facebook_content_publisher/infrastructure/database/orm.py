"""SQLAlchemy mapping for Milestone 2 entities."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import CHAR, TypeDecorator

from facebook_content_publisher.domain.enums import (
    CampaignStatus,
    CommentJobStatus,
    LogLevel,
    MediaType,
    PublicationStatus,
    PublishMode,
    TranslationStatus,
)


class UUIDText(TypeDecorator[UUID]):
    """Portable UUID storage for SQLite."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: UUID | None, dialect: object) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: str | None, dialect: object) -> UUID | None:
        return UUID(value) if value is not None else None


class UTCDateTime(TypeDecorator[datetime]):
    """Persist UTC and restore timezone awareness on SQLite."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class CountryProfileRecord(TimestampMixin, Base):
    __tablename__ = "country_profiles"

    id: Mapped[UUID] = mapped_column(UUIDText(), primary_key=True)
    code: Mapped[str] = mapped_column(String(2), unique=True, index=True)
    country_name: Mapped[str] = mapped_column(String(100))
    language_code: Mapped[str] = mapped_column(String(20))
    language_name: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(100))
    facebook_page_id: Mapped[str | None] = mapped_column(String(100))
    facebook_page_name: Mapped[str | None] = mapped_column(String(200))
    default_link: Mapped[str | None] = mapped_column(Text)
    default_comment_template: Mapped[str] = mapped_column(Text)
    translation_prompt_override: Mapped[str | None] = mapped_column(Text)
    default_hashtags: Mapped[str | None] = mapped_column(Text)
    native_reader_label: Mapped[str] = mapped_column(String(100), default="")
    localization_level: Mapped[str] = mapped_column(String(20), default="natural")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class CampaignRecord(TimestampMixin, Base):
    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(UUIDText(), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    source_language: Mapped[str] = mapped_column(String(20), default="en")
    source_text: Mapped[str] = mapped_column(Text)
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus))


class CampaignTargetRecord(TimestampMixin, Base):
    __tablename__ = "campaign_targets"
    __table_args__ = (
        UniqueConstraint("campaign_id", "country_profile_id", name="uq_campaign_target_country"),
    )

    id: Mapped[UUID] = mapped_column(UUIDText(), primary_key=True)
    campaign_id: Mapped[UUID] = mapped_column(
        UUIDText(), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    country_profile_id: Mapped[UUID] = mapped_column(
        UUIDText(), ForeignKey("country_profiles.id", ondelete="RESTRICT"), index=True
    )
    link_override: Mapped[str | None] = mapped_column(Text)
    comment_delay_minutes: Mapped[int] = mapped_column(Integer, default=330)
    delayed_comment_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    publish_mode: Mapped[PublishMode] = mapped_column(Enum(PublishMode))
    scheduled_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())


class MediaAssetRecord(Base):
    __tablename__ = "media_assets"

    id: Mapped[UUID] = mapped_column(UUIDText(), primary_key=True)
    campaign_id: Mapped[UUID] = mapped_column(
        UUIDText(), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    file_name: Mapped[str] = mapped_column(String(255))
    absolute_path: Mapped[str] = mapped_column(Text)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class LocalizedContentRecord(TimestampMixin, Base):
    __tablename__ = "localized_contents"
    __table_args__ = (
        UniqueConstraint("campaign_id", "country_profile_id", name="uq_localized_campaign_country"),
    )

    id: Mapped[UUID] = mapped_column(UUIDText(), primary_key=True)
    campaign_id: Mapped[UUID] = mapped_column(
        UUIDText(), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    country_profile_id: Mapped[UUID] = mapped_column(
        UUIDText(), ForeignKey("country_profiles.id"), index=True
    )
    language_code: Mapped[str] = mapped_column(String(20))
    translated_text: Mapped[str] = mapped_column(Text)
    comment_text: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[str] = mapped_column(Text)
    link_url: Mapped[str | None] = mapped_column(Text)
    translation_status: Mapped[TranslationStatus] = mapped_column(Enum(TranslationStatus))
    quality_warnings: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    model_name: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    provider_request_id: Mapped[str | None] = mapped_column(String(100))
    translation_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    translation_completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(Text)
    source_text_hash: Mapped[str] = mapped_column(String(64), default="")
    manually_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    rejected_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class PublicationRecord(TimestampMixin, Base):
    __tablename__ = "publications"

    id: Mapped[UUID] = mapped_column(UUIDText(), primary_key=True)
    campaign_id: Mapped[UUID] = mapped_column(UUIDText(), ForeignKey("campaigns.id"), index=True)
    localized_content_id: Mapped[UUID] = mapped_column(
        UUIDText(), ForeignKey("localized_contents.id"), index=True
    )
    country_profile_id: Mapped[UUID] = mapped_column(
        UUIDText(), ForeignKey("country_profiles.id"), index=True
    )
    facebook_page_id: Mapped[str] = mapped_column(String(100))
    publish_mode: Mapped[PublishMode] = mapped_column(Enum(PublishMode))
    scheduled_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    published_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    facebook_post_id: Mapped[str | None] = mapped_column(String(100))
    facebook_post_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PublicationStatus] = mapped_column(Enum(PublicationStatus))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    started_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    next_retry_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    heartbeat_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    provider_request_id: Mapped[str | None] = mapped_column(String(100))
    cancelled_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    correlation_id: Mapped[str] = mapped_column(String(100), default="")
    post_text_snapshot: Mapped[str] = mapped_column(Text, default="")
    country_code_snapshot: Mapped[str] = mapped_column(String(10), default="")
    language_code_snapshot: Mapped[str] = mapped_column(String(20), default="")
    comment_text_snapshot: Mapped[str] = mapped_column(Text, default="")
    link_url_snapshot: Mapped[str | None] = mapped_column(Text)
    media_snapshot_json: Mapped[str] = mapped_column(Text, default="[]")
    delayed_comment_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    comment_delay_minutes: Mapped[int] = mapped_column(Integer, default=330)
    version: Mapped[int] = mapped_column(Integer, default=1)
    provider_mode_snapshot: Mapped[str] = mapped_column(String(20), default="mock")
    attention_required: Mapped[bool] = mapped_column(Boolean, default=False)


class CommentJobRecord(TimestampMixin, Base):
    __tablename__ = "comment_jobs"

    id: Mapped[UUID] = mapped_column(UUIDText(), primary_key=True)
    publication_id: Mapped[UUID] = mapped_column(
        UUIDText(), ForeignKey("publications.id", ondelete="CASCADE"), index=True
    )
    execute_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    comment_text: Mapped[str] = mapped_column(Text)
    link_url: Mapped[str | None] = mapped_column(Text)
    facebook_comment_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[CommentJobStatus] = mapped_column(Enum(CommentJobStatus))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    started_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    heartbeat_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    provider_request_id: Mapped[str | None] = mapped_column(String(100))
    cancelled_at_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    page_id_snapshot: Mapped[str] = mapped_column(String(100), default="")
    facebook_post_id_snapshot: Mapped[str] = mapped_column(String(100), default="")
    correlation_id: Mapped[str] = mapped_column(String(100), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    provider_mode_snapshot: Mapped[str] = mapped_column(String(20), default="mock")
    attention_required: Mapped[bool] = mapped_column(Boolean, default=False)


class ActivityLogRecord(Base):
    __tablename__ = "activity_logs"

    id: Mapped[UUID] = mapped_column(UUIDText(), primary_key=True)
    level: Mapped[LogLevel] = mapped_column(Enum(LogLevel))
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[UUID | None] = mapped_column(UUIDText())
    safe_message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    correlation_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    actor: Mapped[str] = mapped_column(String(20), default="system")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class FacebookPageConnectionRecord(TimestampMixin, Base):
    __tablename__ = "facebook_page_connections"

    id: Mapped[UUID] = mapped_column(UUIDText(), primary_key=True)
    page_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    page_name: Mapped[str] = mapped_column(String(200))
    credential_alias: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="CONNECTED")
    permissions_json: Mapped[str] = mapped_column(Text, default="[]")
    can_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    can_comment: Mapped[bool] = mapped_column(Boolean, default=False)
    connected_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    token_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
