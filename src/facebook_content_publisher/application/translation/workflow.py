"""Concurrent, resumable multi-country translation use cases."""

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Event, Lock
from typing import Protocol
from uuid import UUID

from facebook_content_publisher.application.translation.errors import (
    CancelledTranslationError,
    TranslationError,
    sanitize_error,
)
from facebook_content_publisher.application.translation.schemas import TranslationResult
from facebook_content_publisher.application.translation.service import TranslationService
from facebook_content_publisher.domain.enums import CampaignStatus, TranslationStatus
from facebook_content_publisher.domain.models import Campaign, CountryProfile, LocalizedContent


@dataclass(frozen=True, slots=True)
class TranslationJob:
    localized_id: UUID
    country: CountryProfile
    source_text: str
    link_url: str | None


class TranslationStore(Protocol):
    def prepare(
        self, campaign_id: UUID, include_completed: bool = False
    ) -> list[TranslationJob]: ...

    def set_campaign_status(self, campaign_id: UUID, status: CampaignStatus) -> None: ...

    def mark_started(self, localized_id: UUID) -> None: ...

    def save_result(self, localized_id: UUID, result: TranslationResult) -> None: ...

    def save_failure(self, localized_id: UUID, code: str, message: str) -> None: ...

    def mark_cancelled(self, localized_id: UUID) -> None: ...

    def list_for_campaign(self, campaign_id: UUID) -> list[LocalizedContent]: ...

    def get_campaign(self, campaign_id: UUID) -> Campaign: ...

    def save_edit(self, localized_id: UUID, post: str, comment: str, hashtags: str) -> None: ...

    def set_review_status(self, localized_id: UUID, status: TranslationStatus) -> None: ...

    def recover_interrupted(self) -> int: ...


class TranslationWorkflow:
    def __init__(
        self,
        store: TranslationStore,
        service_factory,
        max_concurrency: int = 3,
    ) -> None:
        self.store = store
        self.service_factory = service_factory
        self.max_concurrency = max_concurrency
        self.cancel_event = Event()
        self._active: set[UUID] = set()
        self._lock = Lock()

    def generate(self, campaign_id: UUID, progress=None) -> list[LocalizedContent]:
        with self._lock:
            if campaign_id in self._active:
                raise ValueError("A translation batch is already running for this campaign")
            self._active.add(campaign_id)
        self.cancel_event.clear()
        try:
            jobs = self.store.prepare(campaign_id)
            self.store.set_campaign_status(campaign_id, CampaignStatus.TRANSLATING)
            completed = 0
            with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
                futures = {executor.submit(self._run_job, job): job for job in jobs}
                for future in as_completed(futures):
                    future.result()
                    completed += 1
                    if progress:
                        progress(completed, len(jobs))
            contents = self.store.list_for_campaign(campaign_id)
            successes = [
                item
                for item in contents
                if item.translation_status is TranslationStatus.NEEDS_REVIEW
            ]
            self.store.set_campaign_status(
                campaign_id,
                CampaignStatus.READY_FOR_REVIEW if successes else CampaignStatus.FAILED,
            )
            return contents
        finally:
            with self._lock:
                self._active.discard(campaign_id)

    def cancel(self) -> None:
        self.cancel_event.set()

    def retry_failed(self, campaign_id: UUID, progress=None) -> list[LocalizedContent]:
        return self.generate(campaign_id, progress)

    def regenerate(self, campaign_id: UUID, localized_id: UUID) -> LocalizedContent:
        jobs = {
            job.localized_id: job for job in self.store.prepare(campaign_id, include_completed=True)
        }
        job = jobs.get(localized_id)
        if job is None:
            raise ValueError("Translation target was not found")
        self._run_job(job)
        return next(
            item for item in self.store.list_for_campaign(campaign_id) if item.id == localized_id
        )

    def save_edit(self, localized_id: UUID, post: str, comment: str, hashtags: str) -> None:
        if not post.strip() or not comment.strip():
            raise ValueError("Post and comment text cannot be empty")
        self.store.save_edit(localized_id, post.strip(), comment.strip(), hashtags.strip())

    def approve(self, campaign_id: UUID, localized_id: UUID) -> None:
        item = next(
            value for value in self.store.list_for_campaign(campaign_id) if value.id == localized_id
        )
        campaign = self.store.get_campaign(campaign_id)
        if item.translation_status not in {
            TranslationStatus.NEEDS_REVIEW,
            TranslationStatus.TRANSLATED,
        }:
            raise ValueError("Only a valid translated result can be approved")
        if item.source_text_hash != source_hash(campaign.source_text):
            raise ValueError("Source changed; regenerate before approval")
        self.store.set_review_status(localized_id, TranslationStatus.APPROVED)

    def reject(self, localized_id: UUID) -> None:
        self.store.set_review_status(localized_id, TranslationStatus.REJECTED)

    def _run_job(self, job: TranslationJob) -> None:
        if self.cancel_event.is_set():
            self.store.mark_cancelled(job.localized_id)
            return
        self.store.mark_started(job.localized_id)
        try:
            service: TranslationService = self.service_factory()
            result = service.translate(job.country, job.source_text, job.link_url)
            if self.cancel_event.is_set():
                self.store.mark_cancelled(job.localized_id)
            else:
                self.store.save_result(job.localized_id, result)
        except CancelledTranslationError:
            self.store.mark_cancelled(job.localized_id)
        except TranslationError as error:
            self.store.save_failure(job.localized_id, error.code, sanitize_error(error))
        except Exception:
            self.store.save_failure(job.localized_id, "validation", "Translation validation failed")


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
