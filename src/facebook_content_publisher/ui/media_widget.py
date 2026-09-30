"""Non-blocking media selection widget."""

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from facebook_content_publisher.application.media import ValidatedMedia, validate_media


class _WorkerSignals(QObject):
    finished = Signal(object, object)


class _MediaWorker(QRunnable):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = validate_media(self.path)
            self.signals.finished.emit(result, None)
        except Exception as error:
            self.signals.finished.emit(None, str(error))


class MediaWidget(QWidget):
    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._media: dict[Path, ValidatedMedia] = {}
        self._pending = 0
        self.list = QListWidget()
        browse = QPushButton("Browse media")
        remove = QPushButton("Remove selected")
        browse.clicked.connect(self._browse)
        remove.clicked.connect(self._remove)
        buttons = QHBoxLayout()
        buttons.addWidget(browse)
        buttons.addWidget(remove)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Images/video (JPG, JPEG, PNG, WEBP, MP4)"))
        layout.addWidget(self.list)
        layout.addLayout(buttons)

    def paths(self) -> list[Path]:
        return list(self._media)

    def set_paths(self, paths: list[Path]) -> None:
        self._media.clear()
        self.list.clear()
        for path in paths:
            self.add_path(path)

    def add_path(self, path: Path) -> None:
        worker = _MediaWorker(path)
        worker.signals.finished.connect(self._finished)
        self._pending += 1
        QThreadPool.globalInstance().start(worker)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.add_path(Path(url.toLocalFile()))

    def _browse(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select media", "", "Media (*.jpg *.jpeg *.png *.webp *.mp4)"
        )
        for path in paths:
            self.add_path(Path(path))

    def _finished(self, result: ValidatedMedia | None, error: str | None) -> None:
        self._pending -= 1
        if error:
            QMessageBox.warning(self, "Invalid media", error)
            return
        if result is None or result.path in self._media:
            return
        self._media[result.path] = result
        size = f"{result.file_size / 1024:.1f} KB"
        item = QListWidgetItem(f"{result.path.name}  |  {result.media_type.value}  |  {size}")
        item.setData(Qt.ItemDataRole.UserRole, str(result.path))
        item.setToolTip(str(result.path))
        self.list.addItem(item)
        self.changed.emit()

    def _remove(self) -> None:
        for item in self.list.selectedItems():
            path = Path(item.data(Qt.ItemDataRole.UserRole))
            self._media.pop(path, None)
            self.list.takeItem(self.list.row(item))
        self.changed.emit()
