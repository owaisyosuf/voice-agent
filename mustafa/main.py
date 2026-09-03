"""MUSTAFA entry point: PyQt UI + a worker that handles typed and voice commands.

Commands arrive two ways:
  - typing in the text box (works with no microphone), or
  - clicking "Listen" to speak one command.
Both are queued and processed off the UI thread so the window stays responsive.
"""

import queue
import sys

from PyQt6 import QtCore, QtWidgets

from . import actions, brain, stt, tts
from .config import COMMAND_SECONDS
from .ui.orb_window import MainWindow


class CommandWorker(QtCore.QThread):
    """Processes commands one at a time: brain -> action -> voice reply."""

    state = QtCore.pyqtSignal(str)
    transcript = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._running = True
        self._queue: "queue.Queue" = queue.Queue()

    # --- called from the UI thread ---
    def submit_text(self, text: str):
        self._queue.put(("text", text))

    def submit_voice(self):
        self._queue.put(("voice", None))

    def stop(self):
        self._running = False
        self._queue.put(("stop", None))

    # --- worker thread ---
    def run(self):
        self.state.emit("Idle")
        while self._running:
            kind, payload = self._queue.get()
            if kind == "stop" or not self._running:
                break
            try:
                self._handle(kind, payload)
            except Exception as exc:  # never let one command crash the app
                print(f"[worker] error: {exc}")
                self.state.emit("Error")
                self.transcript.emit(str(exc))
            self.state.emit("Idle")

    def _handle(self, kind: str, payload):
        if kind == "voice":
            self.state.emit("Listening")
            command = stt.listen(COMMAND_SECONDS)
        else:
            command = payload
        self.transcript.emit(command or "...")

        self.state.emit("Processing")
        intent = brain.parse_intent(command)

        if intent["action"] == "open":
            _, message = actions.open_target(intent["target"])
        elif intent["action"] == "close":
            _, message = actions.close_target(intent["target"])
        else:
            message = "Samajh nahi aaya. Dobara likhein ya boliye."

        self.state.emit("Speaking")
        self.transcript.emit(message)
        tts.speak(message)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    worker = CommandWorker()

    worker.state.connect(window.set_state)
    worker.transcript.connect(window.set_transcript)

    def submit_typed():
        text = window.input_box.text().strip()
        if text:
            worker.submit_text(text)
            window.input_box.clear()

    window.input_box.returnPressed.connect(submit_typed)
    window.listen_btn.clicked.connect(worker.submit_voice)
    app.aboutToQuit.connect(worker.stop)

    worker.start()
    window.show()
    exit_code = app.exec()
    worker.stop()
    worker.wait(2000)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
