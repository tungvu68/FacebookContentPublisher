"""Milestone 3 use cases consumed by the UI."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from facebook_content_publisher.application.dto import CountryProfileCreate
from facebook_content_publisher.application.dto.schemas import CampaignDraftInput
from facebook_content_publisher.application.media import validate_media
from facebook_content_publisher.domain.enums import CampaignStatus
from facebook_content_publisher.domain.exceptions import DuplicateEntityError, EntityNotFoundError
from facebook_content_publisher.domain.models import (
    Campaign,
    CampaignTarget,
    CountryProfile,
    MediaAsset,
)
from facebook_content_publisher.domain.repositories import CountryProfileRepository


@dataclass(frozen=True, slots=True)
class CampaignDetails:
    campaign: Campaign
    targets: list[CampaignTarget]
    media: list[MediaAsset]


class CampaignStore(Protocol):
    def save(self, details: CampaignDetails) -> CampaignDetails: ...

    def list(self) -> list[CampaignDetails]: ...

    def get(self, campaign_id: UUID) -> CampaignDetails | None: ...

    def delete_draft(self, campaign_id: UUID) -> bool: ...


class CountryService:
    def __init__(self, repository: CountryProfileRepository) -> None:
        self._repository = repository

    def list(self) -> list[CountryProfile]:
        return self._repository.list()

    def create(self, data: CountryProfileCreate) -> CountryProfile:
        if self._repository.get_by_code(data.code):
            raise DuplicateEntityError(f"Country code {data.code} already exists")
        country = CountryProfile(**data.model_dump())
        return self._repository.add(country)

    def update(self, country_id: UUID, data: CountryProfileCreate) -> CountryProfile:
        country = self._repository.get(country_id)
        if country is None:
            raise EntityNotFoundError("Country was not found")
        duplicate = self._repository.get_by_code(data.code)
        if duplicate is not None and duplicate.id != country_id:
            raise DuplicateEntityError(f"Country code {data.code} already exists")
        for name, value in data.model_dump().items():
            setattr(country, name, value)
        country.updated_at = datetime.now(UTC)
        return self._repository.update(country)

    def set_enabled(self, country_id: UUID, enabled: bool) -> CountryProfile:
        country = self._repository.get(country_id)
        if country is None:
            raise EntityNotFoundError("Country was not found")
        country.enabled = enabled
        country.updated_at = datetime.now(UTC)
        return self._repository.update(country)

    def delete(self, country_id: UUID) -> None:
        if not self._repository.delete(country_id):
            raise EntityNotFoundError("Country was not found")


class CampaignService:
    def __init__(self, store: CampaignStore) -> None:
        self._store = store

    def list(self) -> list[CampaignDetails]:
        return self._store.list()

    def get(self, campaign_id: UUID) -> CampaignDetails:
        details = self._store.get(campaign_id)
        if details is None:
            raise EntityNotFoundError("Campaign was not found")
        return details

    def save_draft(
        self, data: CampaignDraftInput, campaign_id: UUID | None = None
    ) -> CampaignDetails:
        now = datetime.now(UTC)
        existing = self._store.get(campaign_id) if campaign_id else None
        if existing and existing.campaign.status is not CampaignStatus.DRAFT:
            raise ValueError("Only draft campaigns can be edited")
        campaign = existing.campaign if existing else Campaign(data.title, data.source_text)
        campaign.title = data.title
        campaign.source_text = data.source_text
        campaign.source_language = data.source_language
        campaign.updated_at = now

        targets = [
            CampaignTarget(
                campaign_id=campaign.id,
                country_profile_id=item.country_profile_id,
                link_override=item.link_override,
                comment_delay_minutes=item.delay_minutes_total,
                delayed_comment_enabled=item.delayed_comment_enabled,
                publish_mode=item.publish_mode,
                scheduled_at_utc=item.scheduled_at_utc,
            )
            for item in data.targets
        ]
        media = [self._media_asset(campaign.id, item.path) for item in data.media]
        return self._store.save(CampaignDetails(campaign, targets, media))

    def duplicate(self, campaign_id: UUID) -> CampaignDetails:
        source = self.get(campaign_id)
        campaign = Campaign(
            title=f"{source.campaign.title} (Copy)",
            source_text=source.campaign.source_text,
            source_language=source.campaign.source_language,
        )
        targets = [
            replace(target, id=uuid4(), campaign_id=campaign.id) for target in source.targets
        ]
        media = [replace(asset, id=uuid4(), campaign_id=campaign.id) for asset in source.media]
        return self._store.save(CampaignDetails(campaign, targets, media))

    def archive(self, campaign_id: UUID) -> CampaignDetails:
        details = self.get(campaign_id)
        details.campaign.status = CampaignStatus.ARCHIVED
        details.campaign.updated_at = datetime.now(UTC)
        return self._store.save(details)

    def delete_draft(self, campaign_id: UUID) -> None:
        if not self._store.delete_draft(campaign_id):
            raise ValueError("Only a safe draft campaign can be deleted")

    @staticmethod
    def _media_asset(campaign_id: UUID, path: Path) -> MediaAsset:
        validated = validate_media(path)
        return MediaAsset(
            campaign_id=campaign_id,
            file_name=validated.path.name,
            absolute_path=str(validated.path),
            media_type=validated.media_type,
            mime_type=validated.mime_type,
            file_size=validated.file_size,
            sha256=validated.sha256,
        )
