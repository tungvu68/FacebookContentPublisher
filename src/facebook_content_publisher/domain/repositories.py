"""Repository contracts owned by the domain layer."""

from typing import Protocol, TypeVar
from uuid import UUID

from facebook_content_publisher.domain.models import (
    ActivityLog,
    Campaign,
    CampaignTarget,
    CommentJob,
    CountryProfile,
    LocalizedContent,
    MediaAsset,
    Publication,
)

EntityT = TypeVar("EntityT")


class Repository(Protocol[EntityT]):
    """Persistence contract for a domain entity."""

    def add(self, entity: EntityT) -> EntityT: ...

    def get(self, entity_id: UUID) -> EntityT | None: ...

    def list(self) -> list[EntityT]: ...

    def update(self, entity: EntityT) -> EntityT: ...

    def delete(self, entity_id: UUID) -> bool: ...


class CountryProfileRepository(Repository[CountryProfile], Protocol):
    def get_by_code(self, code: str) -> CountryProfile | None: ...


CampaignRepository = Repository[Campaign]
CampaignTargetRepository = Repository[CampaignTarget]
MediaAssetRepository = Repository[MediaAsset]
LocalizedContentRepository = Repository[LocalizedContent]
PublicationRepository = Repository[Publication]
CommentJobRepository = Repository[CommentJob]
ActivityLogRepository = Repository[ActivityLog]
