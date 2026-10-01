"""Offline-safe Facebook Page connection management UI."""

from datetime import UTC, datetime
from uuid import uuid4

from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from facebook_content_publisher.application.facebook_connection import PageCredentialStore
from facebook_content_publisher.infrastructure.database.orm import FacebookPageConnectionRecord


class FacebookPagesPage(QWidget):
    def __init__(self, sessions, credentials: PageCredentialStore, settings):
        super().__init__()
        self.setObjectName("facebookPagesPage")
        self.sessions, self.credentials, self.settings = sessions, credentials, settings
        mode = QLabel(
            f"FACEBOOK PROVIDER: {settings.facebook_provider_mode.upper()} | "
            f"Graph {settings.graph_api_version}"
        )
        self.status = QLabel(
            "OAuth broker is not configured — live Connect is disabled in Phase 7A"
        )
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Page ID", "Name", "Status", "Publish", "Comment", "Last validation", "Safe error"]
        )
        mock = QPushButton("Mock Connect Page")
        mock.clicked.connect(self.mock_connect)
        connect = QPushButton("Connect Facebook — Phase 7B")
        connect.setEnabled(False)
        disconnect = QPushButton("Disconnect Selected")
        disconnect.clicked.connect(self.disconnect)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        layout = QVBoxLayout(self)
        layout.addWidget(mode)
        layout.addWidget(self.status)
        layout.addWidget(self.table)
        for button in (mock, connect, disconnect, refresh):
            layout.addWidget(button)
        self.refresh()

    def mock_connect(self):
        page_id = "MOCK-PAGE-OFFLINE"
        alias = self.credentials.save(page_id, "mock-page-token")
        now = datetime.now(UTC)
        with self.sessions.begin() as session:
            existing = session.scalar(
                select(FacebookPageConnectionRecord).where(
                    FacebookPageConnectionRecord.page_id == page_id
                )
            )
            if not existing:
                session.add(
                    FacebookPageConnectionRecord(
                        id=uuid4(),
                        page_id=page_id,
                        page_name="Offline Mock Page",
                        credential_alias=alias,
                        status="CONNECTED",
                        permissions_json='["MOCK"]',
                        can_publish=True,
                        can_comment=True,
                        connected_at=now,
                        last_validated_at=now,
                        version=1,
                        created_at=now,
                        updated_at=now,
                    )
                )
        self.refresh()

    def disconnect(self):
        row = self.table.currentRow()
        if row < 0:
            return
        page_id = self.table.item(row, 0).text()
        if (
            QMessageBox.question(
                self, "Disconnect", f"Disconnect {page_id} and delete its credential?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.credentials.delete(page_id)
        with self.sessions.begin() as session:
            record = session.scalar(
                select(FacebookPageConnectionRecord).where(
                    FacebookPageConnectionRecord.page_id == page_id
                )
            )
            if record:
                record.status = "DISCONNECTED"
                record.updated_at = datetime.now(UTC)
                record.version += 1
        self.refresh()

    def refresh(self):
        with self.sessions() as session:
            rows = session.scalars(
                select(FacebookPageConnectionRecord).order_by(
                    FacebookPageConnectionRecord.page_name
                )
            ).all()
        self.table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            values = [
                item.page_id,
                item.page_name,
                item.status,
                str(item.can_publish),
                str(item.can_comment),
                item.last_validated_at.isoformat() if item.last_validated_at else "",
                item.last_error_message or "",
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
