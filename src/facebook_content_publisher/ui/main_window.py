"""Main application window and navigation shell."""

from PySide6.QtCore import Qt, QTimer
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
from facebook_content_publisher.ui.settings_page import SettingsPage
from facebook_content_publisher.ui.translation_review_page import TranslationReviewPage

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
        translation_workflow=None,
        settings_page: SettingsPage | None = None,
        scheduler=None,
        facebook_pages_page=None,
    ) -> None:
        super().__init__()
        self.config = config
        self.country_service = country_service
        self.campaign_service = campaign_service
        self.translation_workflow = translation_workflow
        self.settings_page = settings_page
        self.scheduler = scheduler
        self.facebook_pages_page = facebook_pages_page
        self.minimize_to_tray = False
        self.force_exit = False
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
            if self.scheduler:
                from facebook_content_publisher.ui.scheduled_jobs_page import ScheduledJobsPage

                self.jobs_page = ScheduledJobsPage(self.scheduler)
                pages.addWidget(self.jobs_page)
            else:
                pages.addWidget(self._build_placeholder("Scheduled Jobs"))
            pages.addWidget(countries)
            pages.addWidget(self.facebook_pages_page or self._build_placeholder("Facebook Pages"))
            pages.addWidget(self.settings_page or self._build_placeholder("Settings"))
            if self.scheduler:
                from facebook_content_publisher.ui.logs_page import LogsPage

                pages.addWidget(LogsPage(self.scheduler.sessions))
            else:
                pages.addWidget(self._build_placeholder("Logs"))
            if self.translation_workflow:
                self.review_page = TranslationReviewPage(
                    self.translation_workflow, self.country_service
                )
                pages.addWidget(self.review_page)
                campaign_form.generate_requested.connect(self._generate_translations)
                campaign_form.cancel_requested.connect(self.translation_workflow.cancel)
                self.review_page.back_requested.connect(lambda: navigation.setCurrentRow(2))
                if self.scheduler:
                    self.review_page.prepare_requested.connect(self._prepare_publications)
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
        self.dashboard_metrics = QLabel("Scheduler metrics unavailable")
        self.dashboard_metrics.setObjectName("dashboardMetrics")
        card_layout.addWidget(self.dashboard_metrics)
        if self.scheduler:
            controls = QHBoxLayout()
            jobs = QPushButton("Open Scheduled Jobs")
            jobs.clicked.connect(lambda: self.navigation and self.navigation.setCurrentRow(3))
            due = QPushButton("Run Due Jobs")
            due.clicked.connect(lambda: self.scheduler._wake.set())
            pause = QPushButton("Pause / Resume")
            pause.clicked.connect(self._toggle_scheduler)
            controls.addWidget(jobs)
            controls.addWidget(due)
            controls.addWidget(pause)
            card_layout.addLayout(controls)
            self.dashboard_timer = QTimer(self)
            self.dashboard_timer.setInterval(5000)
            self.dashboard_timer.timeout.connect(self._refresh_dashboard)
            self.dashboard_timer.start()
            QTimer.singleShot(0, self._refresh_dashboard)

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

    def _generate_translations(self, campaign_id) -> None:
        from facebook_content_publisher.ui.translation_worker import TranslationTask

        task = TranslationTask(self.translation_workflow, campaign_id)
        task.signals.finished.connect(lambda error: self._translation_finished(campaign_id, error))
        task.signals.progress.connect(
            lambda completed, total: self.statusBar().showMessage(
                f"Translating: {completed}/{total} | MOCK MODE may be active"
            )
        )
        self._translation_task = task
        from PySide6.QtCore import QThreadPool

        QThreadPool.globalInstance().start(task)

    def _translation_finished(self, campaign_id, error) -> None:
        if error:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Translation batch", str(error))
            return
        self.review_page.load(campaign_id)
        self.pages.setCurrentWidget(self.review_page)

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
            f"Scheduler: {'RUNNING' if self.scheduler else 'NOT STARTED'}  |  "
            "Network: NOT REQUIRED  |  MOCK FACEBOOK MODE"
        )

    def _refresh_dashboard(self) -> None:
        if not self.scheduler:
            return
        metrics = self.scheduler.metrics()
        pubs = metrics["publications"]
        comments = metrics["comments"]
        self.dashboard_metrics.setText(
            f"Scheduler: {'Paused' if metrics['paused'] else 'Running'} | "
            f"Active: {metrics['active_publications']} publications, "
            f"{metrics['active_comments']} comments | "
            f"Retry: {pubs.get('RETRY_WAIT', 0) + comments.get('RETRY_WAIT', 0)} | "
            f"Failed: {pubs.get('FAILED', 0) + comments.get('FAILED', 0)} | "
            f"Unknown: {pubs.get('UNKNOWN_RESULT', 0) + comments.get('UNKNOWN_RESULT', 0)}"
        )

    def _toggle_scheduler(self) -> None:
        if self.scheduler.paused:
            self.scheduler.resume()
        else:
            self.scheduler.pause()
        self._refresh_dashboard()

    def closeEvent(self, event) -> None:
        if self.minimize_to_tray and not self.force_exit:
            event.ignore()
            self.hide()
            return
        super().closeEvent(event)

    def _prepare_publications(self, campaign_id) -> None:
        from PySide6.QtWidgets import QMessageBox

        try:
            created = self.scheduler.prepare_publications(campaign_id)
        except Exception as error:
            QMessageBox.warning(self, "Prepare publications", str(error))
            return
        self.jobs_page.refresh()
        self.navigation.setCurrentRow(3)
        self.statusBar().showMessage(
            f"Prepared {len(created)} publication job(s) | MOCK FACEBOOK MODE"
        )
