"""MUSTAFA entry point: PyQt UI + a worker that handles typed and voice commands.

Commands arrive three ways:
  - typing in the text box (works with no microphone),
  - clicking "Listen" to speak one command, or
  - saying "Hey Mustafa" (background wake-word listener).
Everything is queued and processed off the UI thread so the window stays responsive.
"""

import queue
import sys
import threading

from PyQt6 import QtCore, QtWidgets

from . import actions, brain, history, stt, tts, wakeword
from .config import COMMAND_SECONDS, WAKE_CHUNK_SECONDS
from .ui.orb_window import MainWindow


class CommandWorker(QtCore.QThread):
    """Processes commands one at a time: brain -> action -> voice reply."""

    state = QtCore.pyqtSignal(str)
    transcript = QtCore.pyqtSignal(str)
    chat_turn = QtCore.pyqtSignal(str, str)  # (role, text)

    def __init__(self):
        super().__init__()
        self._running = True
        self._queue: "queue.Queue" = queue.Queue()
        self._turn = 0

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
                self.msleep(1500)  # let the Error state be seen before returning to Idle
            self.state.emit("Idle")

    def _handle(self, kind: str, payload):
        if kind == "voice":
            self.state.emit("Listening")
            command = stt.listen(COMMAND_SECONDS)
        else:
            command = payload
        self.transcript.emit(command or "...")
        self.chat_turn.emit("user", command or "...")

        self.state.emit("Processing")
        self._turn += 1
        intent = brain.think(command, self._turn, history.recent())

        ok = None
        if intent["action"] == "open":
            ok, speak_fallback, display_fallback = actions.open_target(intent["target"])
        elif intent["action"] == "close":
            ok, speak_fallback, display_fallback = actions.close_target(intent["target"])
        else:
            speak_fallback = "سمجھ نہیں آیا۔ دوبارہ لکھیں یا بولیں۔"
            display_fallback = "Samajh nahi aaya. Dobara likhein ya boliye."

        # Trust Gemini's warm reply when the action succeeded (or none was needed);
        # fall back to the deterministic message so a failure is never misreported.
        if ok is False:
            speak_message, display_message = speak_fallback, display_fallback
        else:
            speak_message = intent["reply"] or speak_fallback
            display_message = intent["display"] or display_fallback

        history.add_turn("user", command)
        history.add_turn("assistant", display_message)

        self.state.emit("Speaking")
        self.transcript.emit(display_message)
        self.chat_turn.emit("assistant", display_message)
        tts.speak(speak_message)


class WakeWordWorker(QtCore.QThread):
    """Continuously listens for "Hey Mustafa" and triggers a command capture.

    Paused while CommandWorker is busy (Listening/Processing/Speaking) so the
    two threads never fight over the microphone at the same time.
    """

    heard = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self._running = True
        self._active = threading.Event()
        self._active.set()

    def pause(self):
        self._active.clear()

    def resume(self):
        self._active.set()

    def stop(self):
        self._running = False
        self._active.set()  # unblock if currently paused/waiting

    def run(self):
        while self._running:
            self._active.wait()
            if not self._running:
                break
            try:
                text = stt.listen(WAKE_CHUNK_SECONDS)
            except Exception as exc:
                print(f"[wakeword] error: {exc}")
                continue
            if self._running and wakeword.heard_wake_word(text):
                self.pause()  # stop listening immediately so it can't race the command capture
                self.heard.emit()


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    worker = CommandWorker()
    wake_worker = WakeWordWorker()

    def handle_state(state: str):
        window.set_state(state)
        if state == "Idle":
            wake_worker.resume()
        else:
            wake_worker.pause()

    worker.state.connect(handle_state)
    worker.transcript.connect(window.set_transcript)
    worker.chat_turn.connect(window.append_chat)
    wake_worker.heard.connect(worker.submit_voice)

    for role, text in history.all_turns():
        window.append_chat(role, text)

    def submit_typed():
        text = window.input_box.text().strip()
        if text:
            worker.submit_text(text)
            window.input_box.clear()

    window.input_box.returnPressed.connect(submit_typed)
    window.listen_btn.clicked.connect(worker.submit_voice)
    app.aboutToQuit.connect(worker.stop)
    app.aboutToQuit.connect(wake_worker.stop)

    worker.start()
    wake_worker.start()
    window.showFilled()
    exit_code = app.exec()
    worker.stop()
    wake_worker.stop()
    worker.wait(2000)
    wake_worker.wait(2000)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
