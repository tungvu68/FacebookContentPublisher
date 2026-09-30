"""Country create/edit dialog."""

from pydantic import ValidationError
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from facebook_content_publisher.application.dto import CountryProfileCreate
from facebook_content_publisher.domain.models import CountryProfile


class CountryDialog(QDialog):
    def __init__(self, country: CountryProfile | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit country" if country else "Add country")
        self.setMinimumWidth(520)
        self._fields = {
            name: QLineEdit()
            for name in (
                "code",
                "country_name",
                "language_name",
                "language_code",
                "timezone",
                "facebook_page_id",
                "facebook_page_name",
                "default_link",
                "default_hashtags",
                "native_reader_label",
            )
        }
        self.comment_template = QLineEdit()
        self.prompt_override = QPlainTextEdit()
        self.localization_level = QComboBox()
        self.localization_level.addItems(["conservative", "natural", "strong"])
        self.enabled = QCheckBox("Enabled")
        self.enabled.setChecked(True)

        form = QFormLayout()
        labels = {
            "code": "Country code *",
            "country_name": "Country name *",
            "language_name": "Language name *",
            "language_code": "Language code *",
            "timezone": "IANA timezone *",
            "facebook_page_id": "Facebook Page ID",
            "facebook_page_name": "Facebook Page name",
            "default_link": "Default link",
            "default_hashtags": "Default hashtags",
            "native_reader_label": "Native reader label",
        }
        for name, field in self._fields.items():
            form.addRow(labels[name], field)
        form.addRow("Comment template *", self.comment_template)
        form.addRow("Translation prompt override", self.prompt_override)
        form.addRow("Localization level", self.localization_level)
        form.addRow("", self.enabled)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if country:
            self._load(country)

    def value(self) -> CountryProfileCreate:
        return CountryProfileCreate(
            **{name: field.text() or None for name, field in self._fields.items()},
            default_comment_template=self.comment_template.text(),
            translation_prompt_override=self.prompt_override.toPlainText() or None,
            localization_level=self.localization_level.currentText(),
            enabled=self.enabled.isChecked(),
        )

    def _validate(self) -> None:
        try:
            self.value()
        except ValidationError as error:
            QMessageBox.warning(self, "Invalid country", error.errors()[0]["msg"])
            return
        self.accept()

    def _load(self, country: CountryProfile) -> None:
        for name, field in self._fields.items():
            field.setText(str(getattr(country, name) or ""))
        self.comment_template.setText(country.default_comment_template)
        self.prompt_override.setPlainText(country.translation_prompt_override or "")
        self.localization_level.setCurrentText(country.localization_level)
        self.enabled.setChecked(country.enabled)
