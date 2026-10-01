"""Detached job details and UTC-safe rescheduling dialogs."""

import json
from datetime import UTC
from uuid import UUID

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def safe_diagnostics(job: dict, activity: list[dict]) -> str:
    excluded = {
        "post_text_snapshot",
        "comment_text",
        "comment_text_snapshot",
        "media_snapshot_json",
    }
    safe = {key: str(value) for key, value in job.items() if key not in excluded}
    safe["activity"] = [
        {key: str(value) for key, value in row.items() if key not in {"metadata_json"}}
        for row in activity
    ]
    return json.dumps(safe, indent=2, ensure_ascii=False)


class JobDetailsDialog(QDialog):
    def __init__(self, scheduler, kind: str, job_id: UUID, parent=None):
        super().__init__(parent)
        self.scheduler, self.kind, self.job_id = scheduler, kind, job_id
        self.setWindowTitle("Job Details — MOCK FACEBOOK MODE")
        self.resize(760, 650)
        self.content = QWidget()
        self.form = QFormLayout(self.content)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.content)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        copy = QPushButton("Copy Safe Diagnostics")
        copy.clicked.connect(self.copy_diagnostics)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addWidget(refresh)
        layout.addWidget(copy)
        layout.addWidget(close)
        self.refresh()

    def refresh(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        job = self.scheduler.get_job(self.kind, self.job_id)
        for key, value in job.items():
            widget = (
                QTextEdit(str(value))
                if key
                in {
                    "post_text_snapshot",
                    "comment_text",
                    "comment_text_snapshot",
                    "media_snapshot_json",
                }
                else QLabel(str(value))
            )
            if isinstance(widget, QTextEdit):
                widget.setReadOnly(True)
                widget.setMaximumHeight(100)
            self.form.addRow(key.replace("_", " ").title(), widget)
        timeline = QTextEdit()
        timeline.setReadOnly(True)
        timeline.setPlainText(
            "\n".join(
                f"{row['created_at']} · {row['event_type']} · {row['safe_message']}"
                for row in self.scheduler.activity(self.job_id)
            )
            or "No activity"
        )
        self.form.addRow("Activity Timeline", timeline)

    def copy_diagnostics(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(
            safe_diagnostics(
                self.scheduler.get_job(self.kind, self.job_id), self.scheduler.activity(self.job_id)
            )
        )


class RescheduleDialog(QDialog):
    def __init__(self, scheduler, kind: str, job_id: UUID, parent=None):
        super().__init__(parent)
        self.scheduler, self.kind, self.job_id = scheduler, kind, job_id
        self.job = scheduler.get_job(kind, job_id)
        self.setWindowTitle("Reschedule Job")
        self.when = QDateTimeEdit(QDateTime.currentDateTimeUtc().addSecs(300))
        self.when.setDisplayFormat("yyyy-MM-dd HH:mm:ss 'UTC'")
        self.run_now = QCheckBox("Run Now")
        self.utc = QLabel()
        self.when.dateTimeChanged.connect(self._update)
        self._update()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.addRow("Timezone", QLabel("UTC"))
        form.addRow("Date/time", self.when)
        form.addRow("UTC", self.utc)
        form.addRow(self.run_now)
        form.addRow(buttons)

    def _update(self):
        self.utc.setText(self.when.dateTime().toUTC().toString(Qt.ISODate))

    def _save(self):
        if self.run_now.isChecked():
            try:
                self.scheduler.action(self.kind, self.job_id, "run")
            except Exception as error:
                QMessageBox.warning(self, "Reschedule", str(error))
                return
        else:
            when = self.when.dateTime().toPython().replace(tzinfo=UTC)
            try:
                self.scheduler.reschedule(self.kind, self.job_id, when, self.job["version"])
            except Exception as error:
                QMessageBox.warning(self, "Reschedule", str(error))
                return
        self.accept()
