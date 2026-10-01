"""Read-only-first scheduled job monitor with guarded actions."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ScheduledJobsPage(QWidget):
    def __init__(self, scheduler) -> None:
        super().__init__()
        self.setObjectName("scheduledJobsPage")
        self.scheduler = scheduler
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search jobs")
        self.filter = QComboBox()
        self.filter.addItems(
            [
                "All",
                "Scheduled/Pending",
                "Running",
                "Retry Wait",
                "Completed",
                "Failed",
                "Unknown Result",
                "Cancelled",
            ]
        )
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Type",
                "Country / Page",
                "Status",
                "UTC time",
                "Attempts",
                "Next retry",
                "Last error",
                "Updated",
                "ID",
            ]
        )
        refresh = QPushButton("Refresh")
        run = QPushButton("Run Now")
        retry = QPushButton("Retry")
        cancel = QPushButton("Cancel")
        complete = QPushButton("Mark Completed")
        details = QPushButton("View Details")
        reschedule = QPushButton("Reschedule")
        refresh.clicked.connect(self.refresh)
        run.clicked.connect(lambda: self._action("run"))
        retry.clicked.connect(lambda: self._action("retry", True))
        cancel.clicked.connect(lambda: self._action("cancel", True))
        complete.clicked.connect(lambda: self._action("complete", True))
        details.clicked.connect(self._details)
        reschedule.clicked.connect(self._reschedule)
        self.search.textChanged.connect(self.refresh)
        self.filter.currentTextChanged.connect(self.refresh)
        top = QHBoxLayout()
        top.addWidget(QLabel("MOCK FACEBOOK MODE"))
        top.addWidget(self.search)
        top.addWidget(self.filter)
        top.addWidget(refresh)
        actions = QHBoxLayout()
        for button in (run, retry, cancel, complete, reschedule, details):
            actions.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Scheduled Jobs"))
        layout.addLayout(top)
        layout.addWidget(self.table)
        layout.addLayout(actions)
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def _selected(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        from uuid import UUID

        kind = "publication" if self.table.item(row, 0).text() == "Publication" else "comment"
        return kind, UUID(self.table.item(row, 8).text())

    def _details(self):
        selected = self._selected()
        if selected:
            from facebook_content_publisher.ui.job_dialogs import JobDetailsDialog

            JobDetailsDialog(self.scheduler, *selected, self).exec()

    def _reschedule(self):
        selected = self._selected()
        if selected:
            from facebook_content_publisher.ui.job_dialogs import RescheduleDialog

            if RescheduleDialog(self.scheduler, *selected, self).exec():
                self.refresh()

    def refresh(self, *_):
        query = self.search.text().lower()
        selected = self.filter.currentText().upper().replace(" ", "_")
        aliases = {
            "SCHEDULED/PENDING": {"SCHEDULED", "PENDING", "READY"},
            "COMPLETED": {"PUBLISHED", "COMPLETED"},
        }
        jobs = []
        for kind, job in self.scheduler.list_jobs():
            status = job.status.value
            if selected != "ALL" and status not in aliases.get(selected, {selected}):
                continue
            haystack = (
                f"{kind} {status} {getattr(job, 'facebook_page_id', '')} "
                f"{getattr(job, 'country_code_snapshot', '')} {job.id}"
            ).lower()
            if query not in haystack:
                continue
            jobs.append((kind, job))
        self.table.setRowCount(len(jobs))
        for row, (kind, job) in enumerate(jobs):
            due = getattr(job, "scheduled_at_utc", None) or getattr(job, "execute_at_utc", None)
            values = [
                kind,
                getattr(job, "country_code_snapshot", "") or getattr(job, "page_id_snapshot", ""),
                job.status.value,
                due.isoformat() if due else "Now",
                f"{job.attempt_count}/{job.max_attempts}",
                job.next_retry_at_utc.isoformat() if job.next_retry_at_utc else "",
                job.last_error_message or "",
                job.updated_at.isoformat(),
                str(job.id),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.setColumnHidden(8, True)

    def _action(self, action, confirm=False):
        row = self.table.currentRow()
        if row < 0:
            return
        if (
            confirm
            and QMessageBox.question(self, "Confirm action", f"{action.title()} this job?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        kind = "publication" if self.table.item(row, 0).text() == "Publication" else "comment"
        from uuid import UUID

        try:
            self.scheduler.action(kind, UUID(self.table.item(row, 8).text()), action)
        except Exception as error:
            QMessageBox.warning(self, "Action rejected", str(error))
        self.refresh()
