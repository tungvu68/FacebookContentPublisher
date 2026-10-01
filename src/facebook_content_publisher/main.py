"""Application bootstrap and process entry point."""

import argparse
import os
import sys
import time
from collections.abc import Sequence

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from facebook_content_publisher.application.facebook_connection import PageCredentialStore
from facebook_content_publisher.application.scheduler import SchedulerService
from facebook_content_publisher.application.services import CampaignService, CountryService
from facebook_content_publisher.application.settings import SettingsStore
from facebook_content_publisher.application.startup import WindowsStartupManager
from facebook_content_publisher.application.translation.prompt import PromptBuilder
from facebook_content_publisher.application.translation.service import TranslationService
from facebook_content_publisher.application.translation.workflow import TranslationWorkflow
from facebook_content_publisher.config import AppConfig
from facebook_content_publisher.domain.models import CountryProfile
from facebook_content_publisher.infrastructure.database.campaign_store import (
    SqlAlchemyCampaignStore,
)
from facebook_content_publisher.infrastructure.database.engine import create_database
from facebook_content_publisher.infrastructure.database.migrations import upgrade_database
from facebook_content_publisher.infrastructure.database.repositories import RepositorySet
from facebook_content_publisher.infrastructure.database.seed import seed_development_data
from facebook_content_publisher.infrastructure.database.translation_store import (
    SqlAlchemyTranslationStore,
)
from facebook_content_publisher.infrastructure.facebook import create_facebook_publisher
from facebook_content_publisher.infrastructure.openai.adapter import OpenAIResponsesProvider
from facebook_content_publisher.infrastructure.openai.mock import MockTranslationProvider
from facebook_content_publisher.infrastructure.security import WindowsCredentialSecretStore
from facebook_content_publisher.ui.facebook_pages_page import FacebookPagesPage
from facebook_content_publisher.ui.main_window import MainWindow
from facebook_content_publisher.ui.settings_page import SettingsPage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Facebook Content Publisher")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Start Qt offscreen, construct the main window, and exit successfully.",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    """Create and run the Qt application."""

    args = build_parser().parse_args(argv)
    if args.smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    application = QApplication.instance() or QApplication([sys.argv[0]])
    application.setApplicationName("Facebook Content Publisher")

    database = create_database()
    upgrade_database(database.path)
    seed_development_data(database.sessions)
    repositories = RepositorySet(database.sessions)
    settings_store = SettingsStore(database.path.parent.parent / "settings.json")
    secrets = WindowsCredentialSecretStore()
    translation_store = SqlAlchemyTranslationStore(database.sessions)
    translation_store.recover_interrupted()

    def translation_service() -> TranslationService:
        settings = settings_store.load()
        provider = (
            MockTranslationProvider()
            if settings.translation_mode == "mock"
            else OpenAIResponsesProvider(settings, secrets)
        )
        return TranslationService(provider, PromptBuilder(settings.global_translation_prompt))

    workflow = TranslationWorkflow(
        translation_store,
        translation_service,
        settings_store.load().max_concurrent_translations,
    )
    settings = settings_store.load()
    providers = {"mock": create_facebook_publisher("mock")}
    providers["production"] = create_facebook_publisher(
        "graph_api",
        credential_store=PageCredentialStore(secrets),
        version=settings.graph_api_version,
        timeout=settings.facebook_timeout_seconds,
        production_enabled=settings.enable_production_publishing,
    )
    scheduler = SchedulerService(database.sessions, providers, settings)

    def test_connection(settings) -> None:
        if settings.translation_mode == "mock":
            return
        country = CountryProfile(
            code="EN",
            country_name="United States",
            language_code="en-US",
            language_name="English",
            native_reader_label="English speaker",
            timezone="UTC",
            default_comment_template="Details: {link}",
        )
        TranslationService(OpenAIResponsesProvider(settings, secrets)).translate(
            country, "Reply with a minimal structured translation test."
        )

    openai_settings_page = SettingsPage(
        settings_store, secrets, test_connection, WindowsStartupManager()
    )
    facebook_pages_page = FacebookPagesPage(
        database.sessions, PageCredentialStore(secrets), settings
    )
    openai_settings_page.settings_saved.connect(
        lambda: scheduler.audit("SETTINGS_CHANGED", "Application settings changed", "operator")
    )
    window = MainWindow(
        AppConfig.from_environment(),
        CountryService(repositories.countries),
        CampaignService(SqlAlchemyCampaignStore(database.sessions)),
        workflow,
        openai_settings_page,
        scheduler,
        facebook_pages_page,
    )
    tray = QSystemTrayIcon(QIcon(), application)
    tray.setToolTip("Facebook Content Publisher — MOCK FACEBOOK MODE")
    menu = QMenu()
    open_action = QAction("Open", menu)
    open_action.triggered.connect(lambda: (window.show(), window.raise_(), window.activateWindow()))
    status_action = QAction("Scheduler: Running", menu)
    status_action.setEnabled(False)
    pause_action = QAction("Pause Scheduler", menu)
    pause_action.triggered.connect(
        lambda: (scheduler.pause(), status_action.setText("Scheduler: Paused"))
    )
    resume_action = QAction("Resume Scheduler", menu)
    resume_action.triggered.connect(
        lambda: (scheduler.resume(), status_action.setText("Scheduler: Running"))
    )
    run_action = QAction("Run Due Jobs Now", menu)
    run_action.triggered.connect(lambda: scheduler._wake.set())
    exit_action = QAction("Exit", menu)
    exit_action.triggered.connect(application.quit)
    for action in (
        open_action,
        status_action,
        pause_action,
        resume_action,
        run_action,
        exit_action,
    ):
        menu.addAction(action)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: (
            open_action.trigger()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
    )
    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    window.minimize_to_tray = settings.minimize_to_tray and tray_available
    if tray_available:
        tray.show()
    if settings.notifications_enabled:
        last_notification = {"time": 0.0}

        def notify(title, message):
            now = time.monotonic()
            if tray_available and now - last_notification["time"] >= 5:
                tray.showMessage(title, message)
                last_notification["time"] = now

        scheduler.listeners.append(notify)

    def exit_application():
        metrics = scheduler.metrics()
        waiting = sum(
            metrics[group].get(status, 0)
            for group in ("publications", "comments")
            for status in ("READY", "SCHEDULED", "PENDING", "RUNNING", "RETRY_WAIT")
        )
        if (
            not args.smoke_test
            and waiting
            and QMessageBox.question(
                window,
                "Exit scheduler",
                f"{waiting} job(s) are pending or running. Exit anyway?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        window.force_exit = True
        application.quit()

    exit_action.triggered.disconnect()
    exit_action.triggered.connect(exit_application)
    application.aboutToQuit.connect(scheduler.stop)
    if settings.scheduler_enabled:
        scheduler.start()
    window.show()
    if args.smoke_test:
        QTimer.singleShot(100, application.quit)

    return application.exec()


def main() -> int:
    """Console-script entry point."""

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
