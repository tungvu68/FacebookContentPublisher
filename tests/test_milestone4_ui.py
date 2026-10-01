from pathlib import Path

from pytestqt.qtbot import QtBot

from facebook_content_publisher.application.dto import CountryProfileCreate
from facebook_content_publisher.application.dto.schemas import (
    CampaignDraftInput,
    CampaignTargetInput,
)
from facebook_content_publisher.application.secrets import InMemorySecretStore
from facebook_content_publisher.application.services import CampaignService, CountryService
from facebook_content_publisher.application.settings import SettingsStore
from facebook_content_publisher.application.translation.service import TranslationService
from facebook_content_publisher.application.translation.workflow import TranslationWorkflow
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
from facebook_content_publisher.ui.settings_page import SettingsPage
from facebook_content_publisher.ui.translation_review_page import TranslationReviewPage


def test_settings_and_review_pages_work_offline(qtbot: QtBot, tmp_path: Path) -> None:
    settings_store = SettingsStore(tmp_path / "settings.json")
    settings_page = SettingsPage(settings_store, InMemorySecretStore(), lambda settings: None)
    qtbot.addWidget(settings_page)
    settings_page.show()
    settings_page.mode.setCurrentText("openai")
    settings_page._save()
    assert settings_store.load().translation_mode == "openai"
    assert not settings_page.key_input.text()

    database = create_database(tmp_path / "review.db")
    upgrade_database(database.path)
    repositories = RepositorySet(database.sessions)
    countries = CountryService(repositories.countries)
    country = countries.create(
        CountryProfileCreate(
            code="TH",
            country_name="Thailand",
            language_code="th-TH",
            language_name="Thai",
            timezone="Asia/Bangkok",
            default_comment_template="รายละเอียด: {link}",
        )
    )
    campaigns = CampaignService(SqlAlchemyCampaignStore(database.sessions))
    campaign = campaigns.save_draft(
        CampaignDraftInput(
            title="Review",
            source_text="Hello",
            targets=[CampaignTargetInput(country_profile_id=country.id)],
        )
    )
    workflow = TranslationWorkflow(
        SqlAlchemyTranslationStore(database.sessions),
        lambda: TranslationService(MockTranslationProvider()),
    )
    workflow.generate(campaign.campaign.id)
    review = TranslationReviewPage(workflow, countries)
    qtbot.addWidget(review)
    review.load(campaign.campaign.id)
    review.show()
    assert review.tabs.count() == 1
    assert "Review" in review.summary.text()
