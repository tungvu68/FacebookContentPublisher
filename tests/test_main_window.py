from PySide6.QtWidgets import QLabel, QListWidget, QStackedWidget
from pytestqt.qtbot import QtBot

from facebook_content_publisher.config import AppConfig
from facebook_content_publisher.ui.main_window import NAVIGATION_ITEMS, MainWindow


def test_main_window_identifies_mock_mode(qtbot: QtBot) -> None:
    window = MainWindow(AppConfig())
    qtbot.addWidget(window)
    window.show()

    banner = window.findChild(QLabel, "mockModeBanner")

    assert banner is not None
    assert banner.text() == "MOCK MODE"
    assert "OpenAI: MOCK" in window.statusBar().currentMessage()


def test_navigation_contains_required_sections(qtbot: QtBot) -> None:
    window = MainWindow(AppConfig())
    qtbot.addWidget(window)

    navigation = window.findChild(QListWidget, "navigation")

    assert navigation is not None
    assert navigation.count() == len(NAVIGATION_ITEMS)
    assert navigation.item(0).text() == "Dashboard"


def test_navigation_switches_placeholder_pages(qtbot: QtBot) -> None:
    window = MainWindow(AppConfig())
    qtbot.addWidget(window)
    navigation = window.findChild(QListWidget, "navigation")
    pages = window.findChild(QStackedWidget, "pages")

    assert navigation is not None
    assert pages is not None
    assert pages.count() == len(NAVIGATION_ITEMS)

    navigation.setCurrentRow(4)
    assert pages.currentWidget().objectName() == "countriesPage"
