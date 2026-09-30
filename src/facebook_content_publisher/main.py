"""Application bootstrap and process entry point."""

import argparse
import os
import sys
from collections.abc import Sequence

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from facebook_content_publisher.application.services import CampaignService, CountryService
from facebook_content_publisher.config import AppConfig
from facebook_content_publisher.infrastructure.database.campaign_store import (
    SqlAlchemyCampaignStore,
)
from facebook_content_publisher.infrastructure.database.engine import create_database
from facebook_content_publisher.infrastructure.database.migrations import upgrade_database
from facebook_content_publisher.infrastructure.database.repositories import RepositorySet
from facebook_content_publisher.infrastructure.database.seed import seed_development_data
from facebook_content_publisher.ui.main_window import MainWindow


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
    window = MainWindow(
        AppConfig.from_environment(),
        CountryService(repositories.countries),
        CampaignService(SqlAlchemyCampaignStore(database.sessions)),
    )
    window.show()
    if args.smoke_test:
        QTimer.singleShot(100, application.quit)

    return application.exec()


def main() -> int:
    """Console-script entry point."""

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
