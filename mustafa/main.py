"""MUSTAFA entry point: assistant loop on a worker thread + PyQt UI."""

import sys

from PyQt6 import QtCore, QtWidgets

from . import actions, brain, stt, tts
from .config import COMMAND_SECONDS, WAKE_CHUNK_SECONDS, WAKE_WORD
from .ui.orb_window import MainWindow


class AssistantWorker(QtCore.QThread):
    """Runs the listen -> think -> act -> speak loop off the UI thread."""

    state = QtCore.pyqtSignal(str)
    transcript = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._running = True
        self._manual = False

    def stop(self):
        self._running = False

    def trigger_manual(self):
        """Called when the user clicks the Listen button (skips wake word)."""
        self._manual = True

    def _await_trigger(self) -> bool:
        """Return True when woken (wake word or button), False if stopping."""
        while self._running and not self._manual:
            if WAKE_WORD in stt.listen(WAKE_CHUNK_SECONDS).lower():
                return True
        if self._manual:
            self._manual = False
            return True
        return False

    def run(self):
        while self._running:
            try:
                self._cycle()
            except Exception as exc:
                # Never let a background error kill the whole app.
                print(f"[worker] error: {exc}")
                self.state.emit("Error")
                self.transcript.emit(str(exc))
                self.msleep(1500)
        self.state.emit("Idle")

    def _cycle(self):
        self.state.emit("Idle")
        if not self._await_trigger():
            self._running = False
            return

        self.state.emit("Listening")
        command = stt.listen(COMMAND_SECONDS)
        self.transcript.emit(command or "...")

        self.state.emit("Processing")
        intent = brain.parse_intent(command)

        if intent["action"] == "open":
            _, message = actions.open_target(intent["target"])
        elif intent["action"] == "close":
            _, message = actions.close_target(intent["target"])
        else:
            message = "Samajh nahi aaya. Dobara boliye."

        self.state.emit("Speaking")
        self.transcript.emit(message)
        tts.speak(message)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    worker = AssistantWorker()

    worker.state.connect(window.set_state)
    worker.transcript.connect(window.set_transcript)
    window.listen_btn.clicked.connect(worker.trigger_manual)
    app.aboutToQuit.connect(worker.stop)

    worker.start()
    window.show()
    exit_code = app.exec()
    worker.stop()
    worker.wait(2000)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
