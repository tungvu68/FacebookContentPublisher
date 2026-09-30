"""Pydantic schemas at application boundaries."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from facebook_content_publisher.domain.enums import CampaignStatus, PublishMode


class CountryProfileCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=2, max_length=2)
    country_name: str = Field(min_length=1, max_length=100)
    language_code: str = Field(min_length=2, max_length=20)
    language_name: str = Field(min_length=1, max_length=100)
    timezone: str
    facebook_page_id: str | None = None
    facebook_page_name: str | None = None
    default_link: str | None = None
    default_comment_template: str = Field(min_length=1)
    translation_prompt_override: str | None = None
    default_hashtags: str | None = None
    native_reader_label: str | None = None
    localization_level: Literal["conservative", "natural", "strong"] = "natural"
    enabled: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("country code must contain letters only")
        return value.upper()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a valid IANA timezone") from error
        return value

    @field_validator("default_link")
    @classmethod
    def validate_link(cls, value: str | None) -> str | None:
        if value and not value.lower().startswith(("http://", "https://")):
            raise ValueError("default link must use HTTP or HTTPS")
        return value

    @field_validator("default_comment_template")
    @classmethod
    def validate_comment_template(cls, value: str) -> str:
        if "{link}" not in value:
            raise ValueError("comment template must contain {link}")
        return value

    @model_validator(mode="after")
    def validate_language_identity(self) -> "CountryProfileCreate":
        language_by_locale = {
            "ro": ("Romanian", "Romanian"),
            "it": ("Italian", "Italian"),
            "th": ("Thai", "Thai"),
            "id": ("Indonesian", "Indonesian"),
            "pt": ("Brazilian Portuguese", "Brazilian Portuguese speaker"),
        }
        prefix = self.language_code.split("-", 1)[0].lower()
        expected = language_by_locale.get(prefix)
        if expected and self.language_name.casefold() != expected[0].casefold():
            raise ValueError(
                f"language name {self.language_name!r} conflicts with locale {self.language_code}"
            )
        if not self.native_reader_label:
            self.native_reader_label = expected[1] if expected else self.language_name
        return self


class CountryProfileRead(CountryProfileCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class CampaignCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    source_text: str = Field(min_length=1)
    source_language: str = Field(default="en", min_length=2, max_length=20)
    status: CampaignStatus = CampaignStatus.DRAFT


class CampaignTargetInput(BaseModel):
    country_profile_id: UUID
    link_override: str | None = None
    comment_delay_hours: int = Field(default=5, ge=0, le=720)
    comment_delay_minutes: int = Field(default=30, ge=0, le=59)
    delayed_comment_enabled: bool = True
    publish_mode: PublishMode = PublishMode.IMMEDIATE
    scheduled_at: datetime | None = None
    scheduled_timezone: str | None = None

    @field_validator("link_override")
    @classmethod
    def validate_link_override(cls, value: str | None) -> str | None:
        if value and not value.lower().startswith(("http://", "https://")):
            raise ValueError("link override must use HTTP or HTTPS")
        return value

    @model_validator(mode="after")
    def validate_schedule(self) -> "CampaignTargetInput":
        if self.publish_mode is PublishMode.SCHEDULED:
            if self.scheduled_at is None or not self.scheduled_timezone:
                raise ValueError("scheduled date/time and timezone are required")
            try:
                timezone = ZoneInfo(self.scheduled_timezone)
            except ZoneInfoNotFoundError as error:
                raise ValueError("scheduled timezone must be valid") from error
            localized = self.scheduled_at
            if localized.tzinfo is None:
                localized = localized.replace(tzinfo=timezone)
            if localized.astimezone(UTC) <= datetime.now(UTC):
                raise ValueError("scheduled time must be in the future")
        return self

    @property
    def delay_minutes_total(self) -> int:
        return self.comment_delay_hours * 60 + self.comment_delay_minutes

    @property
    def scheduled_at_utc(self) -> datetime | None:
        if (
            self.publish_mode is not PublishMode.SCHEDULED
            or self.scheduled_at is None
            or self.scheduled_timezone is None
        ):
            return None
        value = self.scheduled_at
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo(self.scheduled_timezone))
        return value.astimezone(UTC)


class MediaInput(BaseModel):
    path: Path


class CampaignDraftInput(CampaignCreate):
    targets: list[CampaignTargetInput] = Field(min_length=1)
    media: list[MediaInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_targets(self) -> "CampaignDraftInput":
        ids = [target.country_profile_id for target in self.targets]
        if len(ids) != len(set(ids)):
            raise ValueError("each country can be selected only once")
        return self
