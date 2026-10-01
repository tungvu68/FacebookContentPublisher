from pathlib import Path
from threading import Event, Thread

import pytest

from facebook_content_publisher.application.dto import CountryProfileCreate
from facebook_content_publisher.application.dto.schemas import (
    CampaignDraftInput,
    CampaignTargetInput,
)
from facebook_content_publisher.application.services import CampaignService, CountryService
from facebook_content_publisher.application.translation.errors import TranslationError
from facebook_content_publisher.application.translation.schemas import ProviderResponse
from facebook_content_publisher.application.translation.service import TranslationService
from facebook_content_publisher.application.translation.workflow import TranslationWorkflow
from facebook_content_publisher.domain.enums import CampaignStatus, TranslationStatus
from facebook_content_publisher.infrastructure.database.campaign_store import (
    SqlAlchemyCampaignStore,
)
from facebook_content_publisher.infrastructure.database.engine import create_database
from facebook_content_publisher.infrastructure.database.migrations import upgrade_database
from facebook_content_publisher.infrastructure.database.repositories import RepositorySet
from facebook_content_publisher.infrastructure.database.translation_store import (
    SqlAlchemyTranslationStore,
)
from facebook_content_publisher.infrastructure.openai.mock import MockTranslationProvider


class FailIndonesiaOnceProvider(MockTranslationProvider):
    def __init__(self) -> None:
        self.failed = False

    def translate(self, prompt: str, *, prompt_version: str) -> ProviderResponse:
        if "locale: id-ID" in prompt and not self.failed:
            self.failed = True
            raise TranslationError("simulated failure")
        return super().translate(prompt, prompt_version=prompt_version)


class BlockingProvider(MockTranslationProvider):
    def __init__(self, started: Event, release: Event) -> None:
        self.started, self.release = started, release

    def translate(self, prompt: str, *, prompt_version: str) -> ProviderResponse:
        self.started.set()
        self.release.wait(5)
        return super().translate(prompt, prompt_version=prompt_version)


def setup_workflow(tmp_path: Path):
    database = create_database(tmp_path / "translations.db")
    upgrade_database(database.path)
    repositories = RepositorySet(database.sessions)
    countries = CountryService(repositories.countries)
    th = countries.create(
        CountryProfileCreate(
            code="TH",
            country_name="Thailand",
            language_code="th-TH",
            language_name="Thai",
            timezone="Asia/Bangkok",
            default_comment_template="รายละเอียด: {link}",
        )
    )
    id_country = countries.create(
        CountryProfileCreate(
            code="ID",
            country_name="Indonesia",
            language_code="id-ID",
            language_name="Indonesian",
            timezone="Asia/Jakarta",
            default_comment_template="Detail: {link}",
        )
    )
    campaigns = CampaignService(SqlAlchemyCampaignStore(database.sessions))
    draft = campaigns.save_draft(
        CampaignDraftInput(
            title="Story",
            source_text="Hello world",
            targets=[
                CampaignTargetInput(country_profile_id=th.id),
                CampaignTargetInput(country_profile_id=id_country.id),
            ],
        )
    )
    store = SqlAlchemyTranslationStore(database.sessions)
    workflow = TranslationWorkflow(
        store, lambda: TranslationService(MockTranslationProvider()), max_concurrency=2
    )
    return workflow, draft.campaign.id, campaigns


def test_multi_country_edit_approve_regenerate_and_stale(tmp_path: Path) -> None:
    workflow, campaign_id, campaigns = setup_workflow(tmp_path)
    results = workflow.generate(campaign_id)
    assert len(results) == 2
    assert all(item.translation_status is TranslationStatus.NEEDS_REVIEW for item in results)
    assert workflow.store.get_campaign(campaign_id).status is CampaignStatus.READY_FOR_REVIEW
    item = results[0]
    workflow.save_edit(item.id, "Edited post", "Edited comment", "#edited")
    edited = workflow.store.list_for_campaign(campaign_id)[0]
    assert edited.manually_edited
    workflow.approve(campaign_id, item.id)
    assert (
        workflow.store.list_for_campaign(campaign_id)[0].translation_status
        is TranslationStatus.APPROVED
    )

    details = campaigns.get(campaign_id)
    details.campaign.source_text = "Changed source"
    campaigns._store.save(details)
    other = workflow.store.list_for_campaign(campaign_id)[1]
    with pytest.raises(ValueError, match="Source changed"):
        workflow.approve(campaign_id, other.id)


def test_recovery_marks_interrupted_retryable(tmp_path: Path) -> None:
    workflow, campaign_id, _ = setup_workflow(tmp_path)
    jobs = workflow.store.prepare(campaign_id)
    workflow.store.mark_started(jobs[0].localized_id)
    assert workflow.store.recover_interrupted() == 1
    item = workflow.store.list_for_campaign(campaign_id)[0]
    assert item.translation_status is TranslationStatus.FAILED
    assert item.failure_code == "interrupted"


def test_partial_failure_retry_and_regenerate_no_duplicate(tmp_path: Path) -> None:
    workflow, campaign_id, _ = setup_workflow(tmp_path)
    provider = FailIndonesiaOnceProvider()
    workflow.service_factory = lambda: TranslationService(provider)
    first = workflow.generate(campaign_id)
    assert {item.translation_status for item in first} == {
        TranslationStatus.NEEDS_REVIEW,
        TranslationStatus.FAILED,
    }
    second = workflow.retry_failed(campaign_id)
    assert all(item.translation_status is TranslationStatus.NEEDS_REVIEW for item in second)
    original_ids = {item.id for item in second}
    workflow.regenerate(campaign_id, second[0].id)
    assert {item.id for item in workflow.store.list_for_campaign(campaign_id)} == original_ids


def test_cancel_keeps_completed_records_and_marks_late_results(tmp_path: Path) -> None:
    workflow, campaign_id, _ = setup_workflow(tmp_path)
    started, release = Event(), Event()
    workflow.service_factory = lambda: TranslationService(BlockingProvider(started, release))
    thread = Thread(target=lambda: workflow.generate(campaign_id))
    thread.start()
    assert started.wait(3)
    workflow.cancel()
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert all(
        item.translation_status is TranslationStatus.CANCELLED
        for item in workflow.store.list_for_campaign(campaign_id)
    )
