"""New/edit campaign form."""

from pathlib import Path
from uuid import UUID

from pydantic import ValidationError
from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from facebook_content_publisher.application.dto.schemas import (
    CampaignDraftInput,
    CampaignTargetInput,
    MediaInput,
)
from facebook_content_publisher.application.services import (
    CampaignDetails,
    CampaignService,
    CountryService,
)
from facebook_content_publisher.domain.enums import PublishMode
from facebook_content_publisher.ui.media_widget import MediaWidget


class CampaignPage(QWidget):
    saved = Signal()
    generate_requested = Signal(object)
    cancel_requested = Signal()

    def __init__(self, countries: CountryService, campaigns: CampaignService, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("newcampaignPage")
        self._countries_service = countries
        self._campaigns_service = campaigns
        self._editing_id: UUID | None = None
        self._saving = False
        self.title = QLineEdit()
        self.language = QLineEdit("en")
        self.source = QTextEdit()
        self.targets = QTableWidget(0, 3)
        self.targets.setHorizontalHeaderLabels(["Use", "Country / locale", "Link override"])
        self.delay_enabled = QCheckBox("Enable delayed comment")
        self.delay_enabled.setChecked(True)
        self.delay_hours = QSpinBox()
        self.delay_hours.setRange(0, 720)
        self.delay_hours.setValue(5)
        self.delay_minutes = QSpinBox()
        self.delay_minutes.setRange(0, 59)
        self.delay_minutes.setValue(30)
        self.publish_mode = QComboBox()
        self.publish_mode.addItems([mode.value for mode in PublishMode])
        self.scheduled_at = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.scheduled_at.setCalendarPopup(True)
        self.schedule_timezone = QLineEdit("UTC")
        self.media = MediaWidget()
        self.notice = QLabel("")

        select_all = QPushButton("Select all")
        clear_all = QPushButton("Clear all")
        select_all.clicked.connect(lambda: self._set_targets(Qt.CheckState.Checked))
        clear_all.clicked.connect(lambda: self._set_targets(Qt.CheckState.Unchecked))
        target_buttons = QHBoxLayout()
        target_buttons.addWidget(select_all)
        target_buttons.addWidget(clear_all)
        target_buttons.addStretch()

        delay = QHBoxLayout()
        delay.addWidget(self.delay_enabled)
        delay.addWidget(QLabel("Hours"))
        delay.addWidget(self.delay_hours)
        delay.addWidget(QLabel("Minutes"))
        delay.addWidget(self.delay_minutes)
        delay.addStretch()
        schedule = QHBoxLayout()
        schedule.addWidget(self.publish_mode)
        schedule.addWidget(self.scheduled_at)
        schedule.addWidget(self.schedule_timezone)

        form = QFormLayout()
        form.addRow("Campaign title *", self.title)
        form.addRow("Source language *", self.language)
        form.addRow("Source text *", self.source)
        form.addRow("Target countries *", self.targets)
        form.addRow("", target_buttons)
        form.addRow("Comment delay", delay)
        form.addRow("Publish", schedule)
        form.addRow("Media", self.media)

        save = QPushButton("Save Draft")
        reset = QPushButton("Reset Form")
        generate = QPushButton("Generate Translations")
        cancel = QPushButton("Cancel Translations")
        self.save_button = save
        self.generate_button = generate
        save.clicked.connect(lambda: self._save(False, save))
        generate.clicked.connect(lambda: self._save(True, generate))
        cancel.clicked.connect(self.cancel_requested.emit)
        reset.clicked.connect(self.reset)
        actions = QHBoxLayout()
        actions.addWidget(save)
        actions.addWidget(generate)
        actions.addWidget(cancel)
        actions.addWidget(reset)
        actions.addStretch()

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.addWidget(QLabel("New Campaign"))
        body_layout.addLayout(form)
        body_layout.addLayout(actions)
        body_layout.addWidget(self.notice)
        body_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        self.refresh_countries()

    def refresh_countries(self) -> None:
        countries = [item for item in self._countries_service.list() if item.enabled]
        self.targets.setRowCount(len(countries))
        for row, country in enumerate(countries):
            check = QTableWidgetItem()
            check.setFlags(check.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Unchecked)
            check.setData(Qt.ItemDataRole.UserRole, str(country.id))
            self.targets.setItem(row, 0, check)
            self.targets.setItem(
                row, 1, QTableWidgetItem(f"{country.country_name} ({country.language_code})")
            )
            self.targets.setItem(row, 2, QTableWidgetItem(""))

    def load(self, details: CampaignDetails) -> None:
        self.reset()
        self._editing_id = details.campaign.id
        self.title.setText(details.campaign.title)
        self.language.setText(details.campaign.source_language)
        self.source.setPlainText(details.campaign.source_text)
        targets = {item.country_profile_id: item for item in details.targets}
        for row in range(self.targets.rowCount()):
            item = self.targets.item(row, 0)
            target = targets.get(UUID(item.data(Qt.ItemDataRole.UserRole)))
            if target:
                item.setCheckState(Qt.CheckState.Checked)
                self.targets.item(row, 2).setText(target.link_override or "")
                self.delay_hours.setValue(target.comment_delay_minutes // 60)
                self.delay_minutes.setValue(target.comment_delay_minutes % 60)
                self.delay_enabled.setChecked(target.delayed_comment_enabled)
                self.publish_mode.setCurrentText(target.publish_mode.value)
        self.media.set_paths([Path(item.absolute_path) for item in details.media])
        editable = details.campaign.status.value == "DRAFT"
        self.save_button.setEnabled(editable)
        self.generate_button.setEnabled(editable)
        if not editable:
            self.notice.setText("This campaign is read-only because it is no longer a draft.")

    def reset(self) -> None:
        self._editing_id = None
        self.title.clear()
        self.language.setText("en")
        self.source.clear()
        self.delay_enabled.setChecked(True)
        self.delay_hours.setValue(5)
        self.delay_minutes.setValue(30)
        self.publish_mode.setCurrentText(PublishMode.IMMEDIATE.value)
        self.media.set_paths([])
        self.notice.clear()
        self.save_button.setEnabled(True)
        self.generate_button.setEnabled(True)
        self.refresh_countries()

    def _data(self) -> CampaignDraftInput:
        targets = []
        for row in range(self.targets.rowCount()):
            check = self.targets.item(row, 0)
            if check.checkState() != Qt.CheckState.Checked:
                continue
            targets.append(
                CampaignTargetInput(
                    country_profile_id=UUID(check.data(Qt.ItemDataRole.UserRole)),
                    link_override=self.targets.item(row, 2).text() or None,
                    comment_delay_hours=self.delay_hours.value(),
                    comment_delay_minutes=self.delay_minutes.value(),
                    delayed_comment_enabled=self.delay_enabled.isChecked(),
                    publish_mode=PublishMode(self.publish_mode.currentText()),
                    scheduled_at=self.scheduled_at.dateTime().toPython(),
                    scheduled_timezone=self.schedule_timezone.text(),
                )
            )
        return CampaignDraftInput(
            title=self.title.text(),
            source_language=self.language.text(),
            source_text=self.source.toPlainText(),
            targets=targets,
            media=[MediaInput(path=path) for path in self.media.paths()],
        )

    def _save(self, generate: bool, button: QPushButton) -> None:
        if self._saving:
            return
        self._saving = True
        self.save_button.setEnabled(False)
        self.generate_button.setEnabled(False)
        try:
            data = self._data()
            details = self._campaigns_service.save_draft(data, self._editing_id)
            self._editing_id = details.campaign.id
            self.notice.setText(
                "Draft saved. Translation started in background."
                if generate
                else "Draft saved successfully."
            )
            self.saved.emit()
            if generate:
                self.generate_requested.emit(details.campaign.id)
        except (ValidationError, ValueError) as error:
            QMessageBox.warning(self, "Invalid campaign", str(error))
        except Exception as error:
            QMessageBox.critical(self, "Unable to save", str(error))
        finally:
            self._saving = False
            self.save_button.setEnabled(True)
            self.generate_button.setEnabled(True)

    def _set_targets(self, state: Qt.CheckState) -> None:
        for row in range(self.targets.rowCount()):
            self.targets.item(row, 0).setCheckState(state)
