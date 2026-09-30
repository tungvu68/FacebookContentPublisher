"""Campaign list and lifecycle actions."""

from uuid import UUID

from PySide6.QtCore import Qt, Signal
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

from facebook_content_publisher.application.services import CampaignDetails, CampaignService
from facebook_content_publisher.domain.enums import CampaignStatus


class CampaignsPage(QWidget):
    edit_requested = Signal(object)

    def __init__(self, service: CampaignService, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("campaignsPage")
        self._service = service
        self._campaigns: list[CampaignDetails] = []
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search title or source text")
        self.status = QComboBox()
        self.status.addItem("All")
        self.status.addItems([item.value for item in CampaignStatus])
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Title", "Status", "Language", "Countries", "Media", "Created", "Updated"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._edit)
        self.empty = QLabel("No campaigns found.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        edit = QPushButton("Edit / View")
        duplicate = QPushButton("Duplicate")
        archive = QPushButton("Archive")
        delete = QPushButton("Delete Draft")
        refresh = QPushButton("Refresh")
        edit.clicked.connect(self._edit)
        duplicate.clicked.connect(self._duplicate)
        archive.clicked.connect(self._archive)
        delete.clicked.connect(self._delete)
        refresh.clicked.connect(self.refresh)
        self.search.textChanged.connect(self._render)
        self.status.currentTextChanged.connect(self._render)

        controls = QHBoxLayout()
        controls.addWidget(self.search, 1)
        controls.addWidget(self.status)
        for button in (edit, duplicate, archive, delete, refresh):
            controls.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Campaigns"))
        layout.addLayout(controls)
        layout.addWidget(self.table)
        layout.addWidget(self.empty)
        self.refresh()

    def refresh(self) -> None:
        self._campaigns = self._service.list()
        self._render()

    def _render(self) -> None:
        query = self.search.text().strip().casefold()
        status = self.status.currentText()
        rows = [
            item
            for item in self._campaigns
            if (
                not query
                or query in f"{item.campaign.title} {item.campaign.source_text}".casefold()
            )
            and (status == "All" or item.campaign.status.value == status)
        ]
        self.table.setRowCount(len(rows))
        for row, details in enumerate(rows):
            campaign = details.campaign
            values = [
                campaign.title,
                campaign.status.value,
                campaign.source_language,
                str(len(details.targets)),
                str(len(details.media)),
                campaign.created_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                campaign.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, str(campaign.id))
                self.table.setItem(row, column, item)
        self.table.setVisible(bool(rows))
        self.empty.setVisible(not rows)

    def _selected_id(self) -> UUID | None:
        row = self.table.currentRow()
        return UUID(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)) if row >= 0 else None

    def _edit(self) -> None:
        campaign_id = self._selected_id()
        if campaign_id:
            self.edit_requested.emit(campaign_id)

    def _duplicate(self) -> None:
        campaign_id = self._selected_id()
        if campaign_id:
            self._action(lambda: self._service.duplicate(campaign_id), "Campaign duplicated.")

    def _archive(self) -> None:
        campaign_id = self._selected_id()
        if campaign_id:
            self._action(lambda: self._service.archive(campaign_id), "Campaign archived.")

    def _delete(self) -> None:
        campaign_id = self._selected_id()
        if (
            campaign_id
            and QMessageBox.question(
                self, "Delete draft", "Delete this draft? Media files will not be deleted."
            )
            == QMessageBox.StandardButton.Yes
        ):
            self._action(lambda: self._service.delete_draft(campaign_id), "Draft deleted.")

    def _action(self, action, message: str) -> None:
        try:
            action()
        except Exception as error:
            QMessageBox.warning(self, "Action failed", str(error))
            return
        self.refresh()
        QMessageBox.information(self, "Success", message)
