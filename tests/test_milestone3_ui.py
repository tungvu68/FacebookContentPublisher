from PySide6.QtWidgets import QTableWidget
from pytestqt.qtbot import QtBot

from facebook_content_publisher.application.dto import CountryProfileCreate
from facebook_content_publisher.application.services import CampaignService, CountryService
from facebook_content_publisher.config import AppConfig
from facebook_content_publisher.infrastructure.database.campaign_store import (
    SqlAlchemyCampaignStore,
)
from facebook_content_publisher.infrastructure.database.engine import create_database
from facebook_content_publisher.infrastructure.database.migrations import upgrade_database
from facebook_content_publisher.infrastructure.database.repositories import RepositorySet
from facebook_content_publisher.ui.campaign_page import CampaignPage
from facebook_content_publisher.ui.countries_page import CountriesPage
from facebook_content_publisher.ui.country_dialog import CountryDialog
from facebook_content_publisher.ui.main_window import MainWindow


def test_milestone3_pages_and_country_dialog_open(qtbot: QtBot, tmp_path) -> None:
    database = create_database(tmp_path / "ui.db")
    upgrade_database(database.path)
    repositories = RepositorySet(database.sessions)
    countries = CountryService(repositories.countries)
    campaigns = CampaignService(SqlAlchemyCampaignStore(database.sessions))
    countries.create(
        CountryProfileCreate(
            code="TH",
            country_name="Thailand",
            language_code="th-TH",
            language_name="Thai",
            timezone="Asia/Bangkok",
            default_comment_template="Details: {link}",
        )
    )

    window = MainWindow(AppConfig(), countries, campaigns)
    qtbot.addWidget(window)
    window.show()

    country_page = window.findChild(CountriesPage, "countriesPage")
    campaign_page = window.findChild(CampaignPage, "newcampaignPage")
    assert country_page is not None
    assert campaign_page is not None
    assert country_page.findChild(QTableWidget).rowCount() == 1
    assert campaign_page.targets.rowCount() == 1

    dialog = CountryDialog(parent=window)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.isVisible()
