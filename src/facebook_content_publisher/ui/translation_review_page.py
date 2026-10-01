"""Database-backed translation review page."""

from contextlib import suppress
from uuid import UUID

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from facebook_content_publisher.application.translation.workflow import (
    TranslationWorkflow,
    source_hash,
)
from facebook_content_publisher.domain.enums import TranslationStatus


class _ReviewSignals(QObject):
    done = Signal(object)


class _ReviewTask(QRunnable):
    def __init__(self, action) -> None:
        super().__init__()
        self.action = action
        self.signals = _ReviewSignals()

    def run(self) -> None:
        try:
            self.action()
            self.signals.done.emit(None)
        except Exception as error:
            self.signals.done.emit(str(error))


class TranslationReviewPage(QWidget):
    back_requested = Signal()
    prepare_requested = Signal(object)

    def __init__(self, workflow: TranslationWorkflow, countries_service) -> None:
        super().__init__()
        self.setObjectName("translationReviewPage")
        self.workflow = workflow
        self.countries_service = countries_service
        self.campaign_id: UUID | None = None
        self.summary = QLabel("No campaign selected")
        self.tabs = QTabWidget()
        retry = QPushButton("Retry Failed")
        approve_all = QPushButton("Approve All")
        prepare = QPushButton("Prepare Publications")
        back = QPushButton("Back to Campaigns")
        retry.clicked.connect(self._retry)
        approve_all.clicked.connect(self._approve_all)
        prepare.clicked.connect(
            lambda: self.campaign_id and self.prepare_requested.emit(self.campaign_id)
        )
        back.clicked.connect(self.back_requested.emit)
        actions = QHBoxLayout()
        actions.addWidget(retry)
        actions.addWidget(approve_all)
        actions.addWidget(prepare)
        actions.addWidget(back)
        actions.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Translation Review"))
        layout.addWidget(self.summary)
        layout.addLayout(actions)
        layout.addWidget(self.tabs)

    def load(self, campaign_id: UUID) -> None:
        self.campaign_id = campaign_id
        campaign = self.workflow.store.get_campaign(campaign_id)
        contents = self.workflow.store.list_for_campaign(campaign_id)
        countries = {item.id: item for item in self.countries_service.list()}
        self.summary.setText(
            f"{campaign.title} | {campaign.source_language} | {len(contents)} targets | "
            f"{sum(item.translation_status is TranslationStatus.APPROVED for item in contents)} "
            "approved"
        )
        self.tabs.clear()
        for content in contents:
            country = countries.get(content.country_profile_id)
            page = QWidget()
            form = QFormLayout(page)
            status = QLabel(content.translation_status.value)
            post = QTextEdit(content.translated_text)
            comment = QTextEdit(content.comment_text)
            hashtags = QTextEdit(content.hashtags)
            stale = content.source_text_hash != source_hash(campaign.source_text)
            metadata = QLabel(
                f"{country.language_name if country else content.language_code} "
                f"({content.language_code}) | "
                f"model: {content.model_name or '-'} | prompt: {content.prompt_version or '-'} | "
                f"tokens: {content.input_tokens or 0}/{content.output_tokens or 0} "
                f"cached: {content.cached_input_tokens or 0} | "
                f"request: {content.provider_request_id or '-'}"
            )
            warning = QLabel(
                ("STALE SOURCE | " if stale else "")
                + (content.failure_message or content.quality_warnings)
            )
            save = QPushButton("Save Edit")
            approve = QPushButton("Approve")
            reject = QPushButton("Reject")
            regenerate = QPushButton("Regenerate")
            copy_post = QPushButton("Copy Post")
            copy_comment = QPushButton("Copy Comment")
            save.clicked.connect(
                lambda _=False, item=content, p=post, c=comment, h=hashtags: self._save(
                    item.id, p, c, h
                )
            )
            approve.clicked.connect(lambda _=False, item=content: self._approve(item.id))
            reject.clicked.connect(lambda _=False, item=content: self._reject(item.id))
            regenerate.clicked.connect(lambda _=False, item=content: self._regenerate(item.id))
            copy_post.clicked.connect(lambda _=False, p=post: self._copy(p.toPlainText()))
            copy_comment.clicked.connect(lambda _=False, c=comment: self._copy(c.toPlainText()))
            buttons = QHBoxLayout()
            for button in (save, approve, reject, regenerate, copy_post, copy_comment):
                buttons.addWidget(button)
            form.addRow("Status", status)
            form.addRow("Metadata", metadata)
            form.addRow("Post", post)
            form.addRow("Comment", comment)
            form.addRow("Hashtags", hashtags)
            form.addRow("Warnings/error", warning)
            form.addRow(buttons)
            self.tabs.addTab(page, country.code if country else content.language_code)

    def _save(self, item_id, post, comment, hashtags) -> None:
        try:
            self.workflow.save_edit(
                item_id, post.toPlainText(), comment.toPlainText(), hashtags.toPlainText()
            )
        except Exception as error:
            QMessageBox.warning(self, "Save failed", str(error))
            return
        self.load(self.campaign_id)

    def _approve(self, item_id) -> None:
        try:
            self.workflow.approve(self.campaign_id, item_id)
        except Exception as error:
            QMessageBox.warning(self, "Approve failed", str(error))
            return
        self.load(self.campaign_id)

    def _reject(self, item_id) -> None:
        if (
            QMessageBox.question(self, "Reject", "Reject this translation?")
            == QMessageBox.StandardButton.Yes
        ):
            self.workflow.reject(item_id)
            self.load(self.campaign_id)

    def _regenerate(self, item_id) -> None:
        if (
            QMessageBox.question(
                self,
                "Regenerate",
                "Regenerate this translation? Any manual edits will be replaced.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._run_async(
            lambda: self.workflow.regenerate(self.campaign_id, item_id),
            "Regenerate failed",
        )

    def _retry(self) -> None:
        if self.campaign_id:
            self._run_async(lambda: self.workflow.retry_failed(self.campaign_id), "Retry failed")

    def _run_async(self, action, title: str) -> None:
        task = _ReviewTask(action)
        task.signals.done.connect(lambda error: self._async_done(error, title))
        self._review_task = task
        QThreadPool.globalInstance().start(task)

    def _async_done(self, error, title: str) -> None:
        if error:
            QMessageBox.warning(self, title, str(error))
        elif self.campaign_id:
            self.load(self.campaign_id)

    def _approve_all(self) -> None:
        if not self.campaign_id:
            return
        if (
            QMessageBox.question(self, "Approve all", "Approve all valid, non-stale translations?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        for item in self.workflow.store.list_for_campaign(self.campaign_id):
            with suppress(ValueError):
                self.workflow.approve(self.campaign_id, item.id)
        self.load(self.campaign_id)

    @staticmethod
    def _copy(text: str) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(text)
