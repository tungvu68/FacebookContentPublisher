"""Country management page."""

from uuid import UUID

from PySide6.QtCore import Qt
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

from facebook_content_publisher.application.services import CountryService
from facebook_content_publisher.ui.country_dialog import CountryDialog


class CountriesPage(QWidget):
    def __init__(self, service: CountryService, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("countriesPage")
        self._service = service
        self._countries = []
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search code, country, language or locale")
        self.filter = QComboBox()
        self.filter.addItems(["All", "Enabled", "Disabled"])
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Enabled",
                "Code",
                "Country",
                "Language",
                "Locale",
                "Timezone",
                "Facebook Page",
                "Default link",
                "Updated",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.empty = QLabel("No countries found.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        add = QPushButton("Add country")
        edit = QPushButton("Edit")
        toggle = QPushButton("Enable / Disable")
        delete = QPushButton("Delete")
        refresh = QPushButton("Refresh")
        add.clicked.connect(self._add)
        edit.clicked.connect(self._edit)
        toggle.clicked.connect(self._toggle)
        delete.clicked.connect(self._delete)
        refresh.clicked.connect(self.refresh)
        self.search.textChanged.connect(self._render)
        self.filter.currentTextChanged.connect(self._render)

        controls = QHBoxLayout()
        controls.addWidget(self.search, 1)
        controls.addWidget(self.filter)
        for button in (add, edit, toggle, delete, refresh):
            controls.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Countries"))
        layout.addLayout(controls)
        layout.addWidget(self.table)
        layout.addWidget(self.empty)
        self.refresh()

    def refresh(self) -> None:
        self._countries = self._service.list()
        self._render()

    def _render(self) -> None:
        query = self.search.text().strip().casefold()
        enabled_filter = self.filter.currentText()
        rows = [
            country
            for country in self._countries
            if (
                not query
                or query
                in " ".join(
                    (
                        country.code,
                        country.country_name,
                        country.language_name,
                        country.language_code,
                    )
                ).casefold()
            )
            and (enabled_filter == "All" or country.enabled == (enabled_filter == "Enabled"))
        ]
        self.table.setRowCount(len(rows))
        for row, country in enumerate(rows):
            values = [
                "Yes" if country.enabled else "No",
                country.code,
                country.country_name,
                country.language_name,
                country.language_code,
                country.timezone,
                country.facebook_page_name or country.facebook_page_id or "",
                country.default_link or "",
                country.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, str(country.id))
                self.table.setItem(row, column, item)
        self.empty.setVisible(not rows)
        self.table.setVisible(bool(rows))

    def _selected_id(self) -> UUID | None:
        row = self.table.currentRow()
        return UUID(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)) if row >= 0 else None

    def _add(self) -> None:
        dialog = CountryDialog(parent=self)
        if dialog.exec():
            self._run(lambda: self._service.create(dialog.value()), "Country created.")

    def _edit(self) -> None:
        country_id = self._selected_id()
        country = next((item for item in self._countries if item.id == country_id), None)
        if country is None:
            return
        dialog = CountryDialog(country, self)
        if dialog.exec():
            self._run(lambda: self._service.update(country.id, dialog.value()), "Country updated.")

    def _toggle(self) -> None:
        country_id = self._selected_id()
        country = next((item for item in self._countries if item.id == country_id), None)
        if country:
            self._run(
                lambda: self._service.set_enabled(country.id, not country.enabled),
                "Status updated.",
            )

    def _delete(self) -> None:
        country_id = self._selected_id()
        if country_id is None:
            return
        answer = QMessageBox.question(self, "Delete country", "Delete this country permanently?")
        if answer == QMessageBox.StandardButton.Yes:
            self._run(lambda: self._service.delete(country_id), "Country deleted.")

    def _run(self, action, success: str) -> None:
        try:
            action()
        except Exception as error:
            QMessageBox.warning(
                self, "Unable to save", f"{error}\nDisable the country if it is in use."
            )
            return
        self.refresh()
        QMessageBox.information(self, "Success", success)
