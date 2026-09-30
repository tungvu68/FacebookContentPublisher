"""Transactional SQLAlchemy campaign aggregate store."""

from dataclasses import fields
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from facebook_content_publisher.application.services import CampaignDetails
from facebook_content_publisher.domain.enums import CampaignStatus
from facebook_content_publisher.domain.models import Campaign, CampaignTarget, MediaAsset
from facebook_content_publisher.infrastructure.database.orm import (
    CampaignRecord,
    CampaignTargetRecord,
    MediaAssetRecord,
    PublicationRecord,
)


class SqlAlchemyCampaignStore:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def save(self, details: CampaignDetails) -> CampaignDetails:
        with self._sessions.begin() as session:
            record = session.get(CampaignRecord, details.campaign.id)
            values = self._values(details.campaign)
            if record is None:
                session.add(CampaignRecord(**values))
            else:
                for name, value in values.items():
                    setattr(record, name, value)
                session.execute(
                    delete(CampaignTargetRecord).where(
                        CampaignTargetRecord.campaign_id == details.campaign.id
                    )
                )
                session.execute(
                    delete(MediaAssetRecord).where(
                        MediaAssetRecord.campaign_id == details.campaign.id
                    )
                )
            session.add_all(CampaignTargetRecord(**self._values(item)) for item in details.targets)
            unique_media: dict[tuple[str, str], MediaAsset] = {
                (item.absolute_path.casefold(), item.sha256): item for item in details.media
            }
            session.add_all(
                MediaAssetRecord(**self._values(item)) for item in unique_media.values()
            )
        return details

    def list(self) -> list[CampaignDetails]:
        with self._sessions() as session:
            ids = session.scalars(
                select(CampaignRecord.id).order_by(CampaignRecord.updated_at.desc())
            ).all()
            return [self._load(session, campaign_id) for campaign_id in ids]

    def get(self, campaign_id: UUID | None) -> CampaignDetails | None:
        if campaign_id is None:
            return None
        with self._sessions() as session:
            if session.get(CampaignRecord, campaign_id) is None:
                return None
            return self._load(session, campaign_id)

    def delete_draft(self, campaign_id: UUID) -> bool:
        with self._sessions.begin() as session:
            record = session.get(CampaignRecord, campaign_id)
            publication_count = session.scalar(
                select(func.count())
                .select_from(PublicationRecord)
                .where(PublicationRecord.campaign_id == campaign_id)
            )
            if record is None or record.status is not CampaignStatus.DRAFT or publication_count:
                return False
            session.delete(record)
            return True

    def _load(self, session: Session, campaign_id: UUID) -> CampaignDetails:
        campaign_record = session.get_one(CampaignRecord, campaign_id)
        target_records = session.scalars(
            select(CampaignTargetRecord).where(CampaignTargetRecord.campaign_id == campaign_id)
        ).all()
        media_records = session.scalars(
            select(MediaAssetRecord).where(MediaAssetRecord.campaign_id == campaign_id)
        ).all()
        return CampaignDetails(
            self._domain(Campaign, campaign_record),
            [self._domain(CampaignTarget, item) for item in target_records],
            [self._domain(MediaAsset, item) for item in media_records],
        )

    @staticmethod
    def _values(entity: object) -> dict[str, object]:
        return {item.name: getattr(entity, item.name) for item in fields(entity)}  # type: ignore[arg-type]

    @staticmethod
    def _domain[DomainT](domain_type: type[DomainT], record: object) -> DomainT:
        values = {item.name: getattr(record, item.name) for item in fields(domain_type)}
        return domain_type(**values)
