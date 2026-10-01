"""OpenAI settings and credential management UI."""

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from facebook_content_publisher.application.secrets import SecretStore, mask_secret
from facebook_content_publisher.application.settings import ApplicationSettings, SettingsStore
from facebook_content_publisher.infrastructure.openai.adapter import OPENAI_API_KEY


class _Signals(QObject):
    done = Signal(object)


class _Task(QRunnable):
    def __init__(self, action) -> None:
        super().__init__()
        self.action = action
        self.signals = _Signals()

    def run(self) -> None:
        try:
            self.action()
            self.signals.done.emit(None)
        except Exception as error:
            self.signals.done.emit(str(error))


class SettingsPage(QWidget):
    settings_saved = Signal()

    def __init__(
        self,
        settings_store: SettingsStore,
        secrets: SecretStore,
        test_connection,
        startup_manager=None,
    ) -> None:
        super().__init__()
        self.setObjectName("settingsPage")
        self.store, self.secrets, self.test_connection = settings_store, secrets, test_connection
        self.startup_manager = startup_manager
        self.mode = QComboBox()
        self.mode.addItems(["mock", "openai"])
        self.key_status = QLabel()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("Enter a new key (never displayed again)")
        self.model = QLineEdit()
        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(5, 600)
        self.concurrency = QSpinBox()
        self.concurrency.setRange(1, 10)
        self.retry_attempts = QSpinBox()
        self.retry_attempts.setRange(1, 10)
        self.retry_initial = QDoubleSpinBox()
        self.retry_initial.setRange(0.1, 1800)
        self.retry_max = QDoubleSpinBox()
        self.retry_max.setRange(1, 7200)
        self.global_prompt = QTextEdit()
        self.scheduler_enabled = QCheckBox()
        self.poll_interval = QDoubleSpinBox()
        self.poll_interval.setRange(0.2, 300)
        self.publication_workers = QSpinBox()
        self.publication_workers.setRange(1, 10)
        self.comment_workers = QSpinBox()
        self.comment_workers.setRange(1, 10)
        self.lease_duration = QSpinBox()
        self.lease_duration.setRange(30, 3600)
        self.heartbeat_interval = QSpinBox()
        self.heartbeat_interval.setRange(5, 600)
        self.shutdown_timeout = QSpinBox()
        self.shutdown_timeout.setRange(0, 120)
        self.overdue_grace = QSpinBox()
        self.overdue_grace.setRange(0, 10080)
        self.confirm_overdue = QCheckBox()
        self.notifications = QCheckBox()
        self.minimize_tray = QCheckBox()
        self.start_windows = QCheckBox()
        self.start_windows.setEnabled(startup_manager is not None)
        self.facebook_mode = QComboBox()
        self.facebook_mode.addItems(["mock", "production"])
        self.graph_version = QLineEdit()
        self.meta_app_id = QLineEdit()
        self.oauth_broker = QLineEdit()
        self.production_safety = QCheckBox()
        self.prompt_version = QLabel()
        self.status = QLabel()
        set_key = QPushButton("Set / Replace Key")
        delete_key = QPushButton("Delete Key")
        save = QPushButton("Save Settings")
        test = QPushButton("Test Connection")
        set_key.clicked.connect(self._set_key)
        delete_key.clicked.connect(self._delete_key)
        save.clicked.connect(self._save)
        test.clicked.connect(lambda: self._test(test))
        form = QFormLayout()
        for label, widget in (
            ("Translation mode", self.mode),
            ("API key status", self.key_status),
            ("New API key", self.key_input),
            ("Model", self.model),
            ("Timeout seconds", self.timeout),
            ("Max concurrent", self.concurrency),
            ("Retry attempts", self.retry_attempts),
            ("Initial delay", self.retry_initial),
            ("Max delay", self.retry_max),
            ("Global prompt", self.global_prompt),
            ("Prompt version", self.prompt_version),
            ("Scheduler enabled", self.scheduler_enabled),
            ("Poll seconds", self.poll_interval),
            ("Publication workers", self.publication_workers),
            ("Comment workers", self.comment_workers),
            ("Lease seconds", self.lease_duration),
            ("Heartbeat seconds", self.heartbeat_interval),
            ("Shutdown timeout", self.shutdown_timeout),
            ("Overdue grace minutes", self.overdue_grace),
            ("Confirm overdue jobs", self.confirm_overdue),
            ("Notifications", self.notifications),
            ("Minimize to tray", self.minimize_tray),
            ("Start with Windows (packaged)", self.start_windows),
            ("Facebook provider", self.facebook_mode),
            ("Graph API version", self.graph_version),
            ("Meta App ID (not secret)", self.meta_app_id),
            ("HTTPS OAuth broker", self.oauth_broker),
            ("Enable production publishing", self.production_safety),
        ):
            form.addRow(label, widget)
        key_actions = QHBoxLayout()
        key_actions.addWidget(set_key)
        key_actions.addWidget(delete_key)
        actions = QHBoxLayout()
        actions.addWidget(save)
        actions.addWidget(test)
        actions.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Settings — OpenAI"))
        layout.addLayout(form)
        layout.addLayout(key_actions)
        layout.addLayout(actions)
        layout.addWidget(self.status)
        layout.addStretch()
        self.reload()

    def reload(self) -> None:
        value = self.store.load()
        self.mode.setCurrentText(value.translation_mode)
        self.model.setText(value.openai_model)
        self.timeout.setValue(value.openai_timeout_seconds)
        self.concurrency.setValue(value.max_concurrent_translations)
        self.retry_attempts.setValue(value.retry_max_attempts)
        self.retry_initial.setValue(value.retry_initial_delay_seconds)
        self.retry_max.setValue(value.retry_max_delay_seconds)
        self.global_prompt.setPlainText(value.global_translation_prompt)
        self.prompt_version.setText(value.prompt_version)
        self.scheduler_enabled.setChecked(value.scheduler_enabled)
        self.poll_interval.setValue(value.scheduler_poll_seconds)
        self.publication_workers.setValue(value.publication_concurrency)
        self.comment_workers.setValue(value.comment_concurrency)
        self.lease_duration.setValue(value.lease_duration_seconds)
        self.heartbeat_interval.setValue(value.heartbeat_interval_seconds)
        self.shutdown_timeout.setValue(value.graceful_shutdown_timeout_seconds)
        self.overdue_grace.setValue(value.overdue_grace_minutes)
        self.confirm_overdue.setChecked(value.require_confirmation_after_overdue)
        self.notifications.setChecked(value.notifications_enabled)
        self.minimize_tray.setChecked(value.minimize_to_tray)
        self.start_windows.setChecked(value.start_with_windows)
        self.facebook_mode.setCurrentText(value.facebook_provider_mode)
        self.graph_version.setText(value.graph_api_version)
        self.meta_app_id.setText(value.meta_app_id)
        self.oauth_broker.setText(value.oauth_broker_url)
        self.production_safety.setChecked(value.enable_production_publishing)
        self.key_status.setText(mask_secret(self.secrets.has_secret(OPENAI_API_KEY)))
        self.key_input.clear()

    def _settings(self) -> ApplicationSettings:
        return ApplicationSettings(
            translation_mode=self.mode.currentText(),
            openai_model=self.model.text(),
            openai_timeout_seconds=self.timeout.value(),
            max_concurrent_translations=self.concurrency.value(),
            retry_max_attempts=self.retry_attempts.value(),
            retry_initial_delay_seconds=self.retry_initial.value(),
            retry_max_delay_seconds=self.retry_max.value(),
            global_translation_prompt=self.global_prompt.toPlainText(),
            prompt_version=self.prompt_version.text(),
            scheduler_enabled=self.scheduler_enabled.isChecked(),
            scheduler_poll_seconds=self.poll_interval.value(),
            publication_concurrency=self.publication_workers.value(),
            comment_concurrency=self.comment_workers.value(),
            lease_duration_seconds=self.lease_duration.value(),
            heartbeat_interval_seconds=self.heartbeat_interval.value(),
            graceful_shutdown_timeout_seconds=self.shutdown_timeout.value(),
            overdue_grace_minutes=self.overdue_grace.value(),
            require_confirmation_after_overdue=self.confirm_overdue.isChecked(),
            notifications_enabled=self.notifications.isChecked(),
            minimize_to_tray=self.minimize_tray.isChecked(),
            start_with_windows=self.start_windows.isChecked(),
            facebook_provider_mode=self.facebook_mode.currentText(),
            graph_api_version=self.graph_version.text(),
            meta_app_id=self.meta_app_id.text().strip(),
            oauth_broker_url=self.oauth_broker.text().strip(),
            enable_production_publishing=self.production_safety.isChecked(),
        )

    def _save(self) -> None:
        try:
            settings = self._settings()
            previous = self.store.load()
            enabling_production = (
                settings.enable_production_publishing and not previous.enable_production_publishing
            )
            warning = (
                "This permits real Page publishing when Phase 7B credentials are "
                "configured. Continue?"
            )
            if (
                enabling_production
                and QMessageBox.warning(
                    self,
                    "Enable production publishing",
                    warning,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            if self.startup_manager and settings.start_with_windows != previous.start_with_windows:
                import sys
                from pathlib import Path

                if settings.start_with_windows:
                    self.startup_manager.enable(Path(sys.executable))
                else:
                    self.startup_manager.disable()
            self.store.save(settings)
        except Exception as error:
            QMessageBox.warning(self, "Invalid settings", str(error))
            return
        self.status.setText("Settings saved.")
        self.settings_saved.emit()

    def _set_key(self) -> None:
        try:
            self.secrets.set_secret(OPENAI_API_KEY, self.key_input.text())
        except Exception as error:
            QMessageBox.warning(self, "Credential error", str(error))
            return
        self.reload()
        self.status.setText("API key saved securely.")

    def _delete_key(self) -> None:
        if (
            QMessageBox.question(self, "Delete key", "Delete the OpenAI API key?")
            == QMessageBox.StandardButton.Yes
        ):
            try:
                self.secrets.delete_secret(OPENAI_API_KEY)
            except Exception as error:
                QMessageBox.warning(self, "Credential error", str(error))
                return
            self.reload()

    def _test(self, button: QPushButton) -> None:
        button.setEnabled(False)
        self.status.setText("Testing connection…")
        task = _Task(lambda: self.test_connection(self._settings()))
        task.signals.done.connect(lambda error: self._test_done(button, error))
        QThreadPool.globalInstance().start(task)

    def _test_done(self, button: QPushButton, error) -> None:
        button.setEnabled(True)
        self.status.setText(f"Connection failed: {error}" if error else "Connection successful.")
