"""Safe scheduler activity log viewer."""

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from facebook_content_publisher.infrastructure.database.orm import ActivityLogRecord


class LogsPage(QWidget):
    def __init__(self, sessions):
        super().__init__()
        self.setObjectName("logsPage")
        self.sessions = sessions
        self.level = QComboBox()
        self.level.addItems(["All", "DEBUG", "INFO", "WARNING", "ERROR"])
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search safe messages, events, correlation IDs")
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        bar = QHBoxLayout()
        bar.addWidget(self.level)
        bar.addWidget(self.search)
        bar.addWidget(refresh)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["UTC", "Level", "Event", "Entity", "Correlation", "Actor", "Safe message"]
        )
        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self.table)
        self.level.currentTextChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        with self.sessions() as session:
            rows = session.scalars(
                select(ActivityLogRecord).order_by(ActivityLogRecord.created_at.desc()).limit(500)
            ).all()
        query = self.search.text().lower()
        level = self.level.currentText()
        filtered = [
            r
            for r in rows
            if (level == "All" or r.level.value == level)
            and query
            in (
                f"{r.event_type} {r.entity_type} {r.entity_id} {r.correlation_id} {r.safe_message}"
            ).lower()
        ]
        self.table.setRowCount(len(filtered))
        for row, item in enumerate(filtered):
            values = [
                item.created_at.isoformat(),
                item.level.value,
                item.event_type,
                f"{item.entity_type or ''}:{item.entity_id or ''}",
                item.correlation_id,
                item.actor,
                item.safe_message,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
