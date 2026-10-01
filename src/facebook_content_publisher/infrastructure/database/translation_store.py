"""Transactional persistence for translation workflow state."""

from dataclasses import fields
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from facebook_content_publisher.application.translation.schemas import TranslationResult
from facebook_content_publisher.application.translation.workflow import TranslationJob, source_hash
from facebook_content_publisher.domain.enums import CampaignStatus, TranslationStatus
from facebook_content_publisher.domain.models import (
    Campaign,
    CountryProfile,
    LocalizedContent,
    utc_now,
)
from facebook_content_publisher.infrastructure.database.orm import (
    CampaignRecord,
    CampaignTargetRecord,
    CountryProfileRecord,
    LocalizedContentRecord,
)


class SqlAlchemyTranslationStore:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def prepare(self, campaign_id: UUID, include_completed: bool = False) -> list[TranslationJob]:
        with self.sessions.begin() as session:
            campaign = session.get_one(CampaignRecord, campaign_id)
            targets = session.scalars(
                select(CampaignTargetRecord).where(CampaignTargetRecord.campaign_id == campaign_id)
            ).all()
            jobs = []
            for target in targets:
                country = session.get_one(CountryProfileRecord, target.country_profile_id)
                record = session.scalar(
                    select(LocalizedContentRecord).where(
                        LocalizedContentRecord.campaign_id == campaign_id,
                        LocalizedContentRecord.country_profile_id == target.country_profile_id,
                    )
                )
                if record is None:
                    entity = LocalizedContent(
                        campaign_id=campaign_id,
                        country_profile_id=country.id,
                        language_code=country.language_code,
                        link_url=target.link_override or country.default_link,
                        source_text_hash=source_hash(campaign.source_text),
                    )
                    record = LocalizedContentRecord(**self._values(entity))
                    session.add(record)
                    session.flush()
                elif not include_completed and record.translation_status not in {
                    TranslationStatus.FAILED,
                    TranslationStatus.CANCELLED,
                    TranslationStatus.PENDING,
                    TranslationStatus.REJECTED,
                }:
                    continue
                record.source_text_hash = source_hash(campaign.source_text)
                record.language_code = country.language_code
                jobs.append(
                    TranslationJob(
                        record.id,
                        self._domain(CountryProfile, country),
                        campaign.source_text,
                        target.link_override or country.default_link,
                    )
                )
            return jobs

    def set_campaign_status(self, campaign_id: UUID, status: CampaignStatus) -> None:
        with self.sessions.begin() as session:
            record = session.get_one(CampaignRecord, campaign_id)
            record.status = status
            record.updated_at = utc_now()

    def mark_started(self, localized_id: UUID) -> None:
        with self.sessions.begin() as session:
            record = session.get_one(LocalizedContentRecord, localized_id)
            record.translation_status = TranslationStatus.TRANSLATING
            record.translation_started_at = utc_now()
            record.failure_code = record.failure_message = None

    def save_result(self, localized_id: UUID, result: TranslationResult) -> None:
        with self.sessions.begin() as session:
            record = session.get_one(LocalizedContentRecord, localized_id)
            output = result.output
            record.translated_text = output.post_text
            record.comment_text = output.comment_text
            record.hashtags = " ".join(output.hashtags)
            record.quality_warnings = "\n".join(output.quality_warnings)
            record.prompt_version = result.prompt_version
            record.provider_request_id = result.request_id
            record.model_name = result.model_name
            record.input_tokens = result.usage.input_tokens
            record.output_tokens = result.usage.output_tokens
            record.cached_input_tokens = result.usage.cached_input_tokens
            record.translation_status = TranslationStatus.NEEDS_REVIEW
            record.translation_completed_at = utc_now()
            record.manually_edited = False
            record.updated_at = utc_now()

    def save_failure(self, localized_id: UUID, code: str, message: str) -> None:
        with self.sessions.begin() as session:
            record = session.get_one(LocalizedContentRecord, localized_id)
            record.translation_status = TranslationStatus.FAILED
            record.failure_code = code[:100]
            record.failure_message = message[:500]
            record.updated_at = utc_now()

    def mark_cancelled(self, localized_id: UUID) -> None:
        with self.sessions.begin() as session:
            record = session.get_one(LocalizedContentRecord, localized_id)
            record.translation_status = TranslationStatus.CANCELLED
            record.updated_at = utc_now()

    def list_for_campaign(self, campaign_id: UUID) -> list[LocalizedContent]:
        with self.sessions() as session:
            records = session.scalars(
                select(LocalizedContentRecord).where(
                    LocalizedContentRecord.campaign_id == campaign_id
                )
            ).all()
            return [self._domain(LocalizedContent, item) for item in records]

    def get_campaign(self, campaign_id: UUID) -> Campaign:
        with self.sessions() as session:
            return self._domain(Campaign, session.get_one(CampaignRecord, campaign_id))

    def save_edit(self, localized_id: UUID, post: str, comment: str, hashtags: str) -> None:
        with self.sessions.begin() as session:
            record = session.get_one(LocalizedContentRecord, localized_id)
            record.translated_text = post
            record.comment_text = comment
            record.hashtags = hashtags
            record.manually_edited = True
            record.updated_at = utc_now()

    def set_review_status(self, localized_id: UUID, status: TranslationStatus) -> None:
        with self.sessions.begin() as session:
            record = session.get_one(LocalizedContentRecord, localized_id)
            record.translation_status = status
            record.approved_at = utc_now() if status is TranslationStatus.APPROVED else None
            record.rejected_at = utc_now() if status is TranslationStatus.REJECTED else None
            record.updated_at = utc_now()

    def recover_interrupted(self) -> int:
        with self.sessions.begin() as session:
            records = session.scalars(
                select(LocalizedContentRecord).where(
                    LocalizedContentRecord.translation_status == TranslationStatus.TRANSLATING
                )
            ).all()
            for record in records:
                record.translation_status = TranslationStatus.FAILED
                record.failure_code = "interrupted"
                record.failure_message = "Translation was interrupted; retry when ready."
                record.updated_at = datetime.now(UTC)
            return len(records)

    @staticmethod
    def _values(entity: object) -> dict[str, object]:
        return {item.name: getattr(entity, item.name) for item in fields(entity)}  # type: ignore[arg-type]

    @staticmethod
    def _domain[DomainT](domain_type: type[DomainT], record: object) -> DomainT:
        return domain_type(
            **{item.name: getattr(record, item.name) for item in fields(domain_type)}
        )
