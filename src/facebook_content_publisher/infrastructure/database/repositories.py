"""SQLAlchemy implementations of domain repository contracts."""

from dataclasses import fields
from typing import TypeVar, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

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
from facebook_content_publisher.infrastructure.database.orm import (
    ActivityLogRecord,
    CampaignRecord,
    CampaignTargetRecord,
    CommentJobRecord,
    CountryProfileRecord,
    LocalizedContentRecord,
    MediaAssetRecord,
    PublicationRecord,
)

DomainT = TypeVar("DomainT")
RecordT = TypeVar("RecordT")


class SqlAlchemyRepository[DomainT, RecordT]:
    """Small synchronous CRUD adapter suitable for desktop use cases."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        domain_type: type[DomainT],
        record_type: type[RecordT],
    ) -> None:
        self._sessions = sessions
        self._domain_type = domain_type
        self._record_type = record_type

    def add(self, entity: DomainT) -> DomainT:
        with self._sessions.begin() as session:
            session.add(self._record_type(**self._values(entity)))  # type: ignore[call-arg]
        return entity

    def get(self, entity_id: UUID) -> DomainT | None:
        with self._sessions() as session:
            record = session.get(self._record_type, entity_id)
            return self._to_domain(record) if record is not None else None

    def list(self) -> list[DomainT]:
        with self._sessions() as session:
            records = session.scalars(select(self._record_type)).all()
            return [self._to_domain(record) for record in records]

    def update(self, entity: DomainT) -> DomainT:
        values = self._values(entity)
        with self._sessions.begin() as session:
            record = session.get(self._record_type, values["id"])
            if record is None:
                raise LookupError(f"Entity {values['id']} was not found")
            for name, value in values.items():
                setattr(record, name, value)
        return entity

    def delete(self, entity_id: UUID) -> bool:
        with self._sessions.begin() as session:
            record = session.get(self._record_type, entity_id)
            if record is None:
                return False
            session.delete(record)
            return True

    def _values(self, entity: DomainT) -> dict[str, object]:
        return {item.name: getattr(entity, item.name) for item in fields(entity)}  # type: ignore[arg-type]

    def _to_domain(self, record: RecordT) -> DomainT:
        values = {item.name: getattr(record, item.name) for item in fields(self._domain_type)}
        return self._domain_type(**values)


class SqlAlchemyCountryProfileRepository(
    SqlAlchemyRepository[CountryProfile, CountryProfileRecord]
):
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        super().__init__(sessions, CountryProfile, CountryProfileRecord)

    def get_by_code(self, code: str) -> CountryProfile | None:
        with self._sessions() as session:
            record = session.scalar(
                select(CountryProfileRecord).where(CountryProfileRecord.code == code.upper())
            )
            return self._to_domain(record) if record is not None else None


class RepositorySet:
    """Typed repository collection sharing a session factory."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.countries = SqlAlchemyCountryProfileRepository(sessions)
        self.campaigns = SqlAlchemyRepository(sessions, Campaign, CampaignRecord)
        self.campaign_targets = SqlAlchemyRepository(sessions, CampaignTarget, CampaignTargetRecord)
        self.media_assets = SqlAlchemyRepository(sessions, MediaAsset, MediaAssetRecord)
        self.localized_contents = SqlAlchemyRepository(
            sessions, LocalizedContent, LocalizedContentRecord
        )
        self.publications = SqlAlchemyRepository(sessions, Publication, PublicationRecord)
        self.comment_jobs = SqlAlchemyRepository(sessions, CommentJob, CommentJobRecord)
        self.activity_logs = SqlAlchemyRepository(sessions, ActivityLog, ActivityLogRecord)


def repository_set(sessions: sessionmaker[Session]) -> RepositorySet:
    return cast(RepositorySet, RepositorySet(sessions))
