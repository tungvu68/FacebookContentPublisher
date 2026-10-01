"""Qt thread-pool translation batch bridge."""

from PySide6.QtCore import QObject, QRunnable, Signal


class TranslationSignals(QObject):
    progress = Signal(int, int)
    finished = Signal(object)


class TranslationTask(QRunnable):
    def __init__(self, workflow, campaign_id) -> None:
        super().__init__()
        self.workflow, self.campaign_id = workflow, campaign_id
        self.signals = TranslationSignals()

    def run(self) -> None:
        try:
            self.workflow.generate(self.campaign_id, self.signals.progress.emit)
            self.signals.finished.emit(None)
        except Exception as error:
            self.signals.finished.emit(str(error))
