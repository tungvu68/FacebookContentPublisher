"""Main application window and navigation shell."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from facebook_content_publisher.application.services import CampaignService, CountryService
from facebook_content_publisher.config import AppConfig
from facebook_content_publisher.ui.campaign_page import CampaignPage
from facebook_content_publisher.ui.campaigns_page import CampaignsPage
from facebook_content_publisher.ui.countries_page import CountriesPage

NAVIGATION_ITEMS = (
    "Dashboard",
    "New Campaign",
    "Campaigns",
    "Scheduled Jobs",
    "Countries",
    "Facebook Pages",
    "Settings",
    "Logs",
)


class MainWindow(QMainWindow):
    """Application shell; business features arrive in later milestones."""

    def __init__(
        self,
        config: AppConfig,
        country_service: CountryService | None = None,
        campaign_service: CampaignService | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.country_service = country_service
        self.campaign_service = campaign_service
        self.navigation: QListWidget | None = None
        self.pages: QStackedWidget | None = None
        self.setObjectName("mainWindow")
        self.setWindowTitle(config.app_name)
        self.resize(1100, 700)
        self.setMinimumSize(800, 520)
        self.setCentralWidget(self._build_content())
        self._build_status_bar()

    def _build_content(self) -> QWidget:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        navigation = QListWidget()
        navigation.setObjectName("navigation")
        navigation.addItems(NAVIGATION_ITEMS)
        navigation.setCurrentRow(0)
        navigation.setFixedWidth(210)
        pages = QStackedWidget()
        pages.setObjectName("pages")
        pages.addWidget(self._build_dashboard())
        if self.country_service and self.campaign_service:
            campaign_form = CampaignPage(self.country_service, self.campaign_service)
            campaigns = CampaignsPage(self.campaign_service)
            countries = CountriesPage(self.country_service)
            campaign_form.saved.connect(campaigns.refresh)
            campaigns.edit_requested.connect(
                lambda campaign_id: self._open_campaign(campaign_id, campaign_form)
            )
            pages.addWidget(campaign_form)
            pages.addWidget(campaigns)
            pages.addWidget(self._build_placeholder("Scheduled Jobs"))
            pages.addWidget(countries)
            for item in NAVIGATION_ITEMS[5:]:
                pages.addWidget(self._build_placeholder(item))
        else:
            for item in NAVIGATION_ITEMS[1:]:
                pages.addWidget(self._build_placeholder(item))
        navigation.currentRowChanged.connect(pages.setCurrentIndex)
        self.navigation = navigation
        self.pages = pages

        layout.addWidget(navigation)
        layout.addWidget(pages, 1)
        return root

    def _build_dashboard(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(18)

        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.DemiBold))

        mode = QLabel("MOCK MODE")
        mode.setObjectName("mockModeBanner")
        mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode.setStyleSheet(
            "background: #fff3cd; color: #664d03; border: 1px solid #ffecb5;"
            "border-radius: 6px; padding: 12px; font-weight: 700;"
        )

        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(QLabel("Bootstrap is ready"))
        card_layout.addWidget(
            QLabel(
                "OpenAI and Facebook use local mock adapters by default. "
                "No API key or Facebook token is required."
            )
        )

        create_button = QPushButton("Create campaign")
        create_button.setEnabled(self.campaign_service is not None)
        create_button.clicked.connect(lambda: self.navigation and self.navigation.setCurrentRow(1))
        create_button.setMaximumWidth(180)

        layout.addWidget(title)
        layout.addWidget(mode)
        layout.addWidget(card)
        layout.addWidget(create_button)
        layout.addStretch()
        return page

    def _open_campaign(self, campaign_id, form: CampaignPage) -> None:
        if self.campaign_service is None or self.navigation is None:
            return
        form.load(self.campaign_service.get(campaign_id))
        self.navigation.setCurrentRow(1)

    def _build_placeholder(self, title_text: str) -> QWidget:
        page = QWidget()
        page.setObjectName(title_text.replace(" ", "").lower() + "Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 32, 36, 32)
        title = QLabel(title_text)
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.DemiBold))
        message = QLabel("This feature is reserved for a later milestone.")
        message.setStyleSheet("color: #667085;")
        layout.addWidget(title)
        layout.addWidget(message)
        layout.addStretch()
        return page

    def _build_status_bar(self) -> None:
        self.statusBar().showMessage(
            f"OpenAI: {self.config.openai_mode.value.upper()}  |  "
            f"Facebook: {self.config.facebook_mode.value.upper()}  |  "
            "Scheduler: NOT STARTED  |  Pending jobs: 0  |  Network: NOT REQUIRED"
        )
