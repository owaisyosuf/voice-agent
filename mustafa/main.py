"""MUSTAFA entry point: PyQt UI + a worker that handles typed and voice commands.

Commands arrive three ways:
  - typing in the text box (works with no microphone),
  - clicking "Listen" (or Ctrl+Space) to speak one command, or
  - saying "Hey Mustafa" (background wake-word listener).
Everything is queued and processed off the UI thread so the window stays responsive.
"""

import queue
import sys
import threading

from PyQt6 import QtCore, QtGui, QtWidgets

from . import actions, brain, history, stt, tts, wakeword
from .config import WAKE_CHUNK_SECONDS, WAKE_WORD_ENABLED
from .ui.orb_window import MainWindow

# Spoken feedback for capture failures. (Urdu script for the voice, Roman for screen.)
NO_SPEECH = ("کچھ سنائی نہیں دیا۔ لسٹن دبا کر دوبارہ بولیے۔",
             "Kuch sunai nahi diya. Listen daba kar dobara boliye.")
TOO_SHORT = ("آواز بہت مختصر تھی۔ ذرا پوری بات کہیے۔",
             "Awaz bohot mukhtasar thi. Zara poori baat kahiye.")
# The mic opened but delivered nothing at all — a Windows problem, not a user problem.
NO_AUDIO = ("مائیکروفون سے کوئی آواز نہیں آ رہی۔ ونڈوز کی ساؤنڈ سیٹنگز میں مائیک منتخب کیجیے۔",
            "Mic se koi awaz nahi aa rahi. Windows Settings > System > Sound > Input "
            "mein apna microphone default set kijiye.")
MIC_BUSY = ("مائیکروفون ابھی مصروف ہے۔ ایک لمحے بعد دوبارہ کوشش کیجیے۔",
            "Mic abhi busy hai. Ek lamha baad dobara Listen dabaiye.")
# Said once at startup when the machine simply has no working microphone, so the
# Listen button never becomes a mystery.
NO_MIC_AT_START = ("مائیکروفون نہیں ملا۔ آواز کے بغیر بھی میں حاضر ہوں، نیچے لکھ کر بھیجیے۔",
                   "Koi kaam karne wala microphone nahi mila — Listen kaam nahi karega. "
                   "Neeche likh kar hukum dijiye.")
NOT_UNDERSTOOD = ("سمجھ نہیں آیا۔ دوبارہ لکھیں یا بولیں۔",
                  "Samajh nahi aaya. Dobara likhein ya boliye.")
# A rate-limited or unreachable brain is not the same thing as not understanding —
# saying "samajh nahi aaya" there is what made it feel broken.
BRAIN_BUSY = ("معاف کیجیے، ابھی رابطہ نہیں ہو پا رہا۔ ایک منٹ بعد دوبارہ کہیے۔",
              "Abhi Gemini se rabta nahi ho pa raha (rate limit). Ek minute baad dobara kahiye.")
BRAIN_FAILED = ("معاف کیجیے، دماغ تک بات نہیں پہنچی۔ انٹرنیٹ چیک کیجیے۔",
                "Brain tak baat nahi pahunchi. Internet ya API key check kijiye.")


class CommandWorker(QtCore.QThread):
    """Processes commands one at a time: capture -> brain -> action -> voice reply."""

    state = QtCore.pyqtSignal(str)
    transcript = QtCore.pyqtSignal(str)
    chat_turn = QtCore.pyqtSignal(str, str)  # (role, text)
    level = QtCore.pyqtSignal(float)         # 0..1 mic loudness while listening
    mic_missing = QtCore.pyqtSignal()        # no working microphone on this machine

    def __init__(self):
        super().__init__()
        self._running = True
        self._queue: "queue.Queue" = queue.Queue()
        # Set by the Stop button; cleared when the next command starts. Every slow
        # step in _handle checks it, so a stop lands within one step rather than
        # after the whole turn has played out.
        self._cancel = threading.Event()
        # Continue the turn count across restarts so it doesn't greet every launch.
        self._turn = history.count() // 2

    # --- called from the UI thread ---
    def submit_text(self, text: str):
        self._queue.put(("text", text))

    def submit_voice(self):
        # Ignore a second click while a capture is already queued or running.
        if self._queue.empty():
            self._queue.put(("voice", None))

    def request_stop(self):
        """Abandon the command in flight and fall back to Idle."""
        self._cancel.set()
        tts.stop()  # cuts playback mid-sentence; the rest unwinds on its own

    def reset_turns(self):
        """Called when the user clears the thread, so it greets afresh."""
        self._turn = 0

    def stop(self):
        self._running = False
        self._queue.put(("stop", None))

    # --- worker thread ---
    def run(self):
        self.state.emit("Warming up")
        brain.preload()  # opens the Gemini connection (first call is otherwise slow)
        try:
            stt.preload()  # load Whisper now, so the first command isn't slow
        except Exception as exc:
            print(f"[worker] whisper preload failed: {exc}")

        # Check the microphone once, up front. On a machine without one, this is
        # what stops the wake-word thread from poking a dead device forever.
        if not stt.probe_microphone():
            print("[worker] no working microphone detected")
            self.mic_missing.emit()
            self._say(*NO_MIC_AT_START)

        self.state.emit("Idle")

        while self._running:
            kind, payload = self._queue.get()
            if kind == "stop" or not self._running:
                break
            self._cancel.clear()
            try:
                self._handle(kind, payload)
            except Exception as exc:  # never let one command crash the app
                print(f"[worker] error: {exc}")
                self.state.emit("Error")
                self.transcript.emit(str(exc))
                self.msleep(1500)  # let the Error state be seen before returning to Idle
            if self._cancel.is_set():
                self.transcript.emit("Roka gaya.")
            self.state.emit("Idle")

    def _stopped(self) -> bool:
        return self._cancel.is_set() or not self._running

    def _say(self, speak_text: str, display_text: str):
        if self._stopped():
            return
        self.state.emit("Speaking")
        self.transcript.emit(display_text)
        self.chat_turn.emit("assistant", display_text)
        tts.speak(speak_text, display_text)

    def _capture_voice(self):
        """Record one utterance. Returns the text, or None if nothing usable was said."""
        self.state.emit("Listening")
        self.transcript.emit("")
        # Record and transcribe as two steps so the orb can switch to Processing the
        # moment you stop talking, instead of showing "Listening" while it thinks.
        audio, reason = stt.record_utterance(
            on_speech_start=None,
            should_stop=self._stopped,
            on_level=self.level.emit,
        )
        self.level.emit(0.0)
        if reason == "cancelled":
            return None
        text = ""
        if reason == "ok":
            self.state.emit("Processing")
            text = stt.transcribe(audio)
            if self._stopped():  # Whisper can run for seconds; don't act on stale audio
                return None
        if reason == "no_speech" or (reason == "ok" and not text):
            self._say(*NO_SPEECH)
            return None
        if reason == "too_short":
            self._say(*TOO_SHORT)
            return None
        if reason == "no_audio":
            self.state.emit("Error")
            self._say(*NO_AUDIO)
            return None
        if reason == "mic_busy":
            self.state.emit("Error")
            self._say(*MIC_BUSY)
            return None
        return text

    def _handle(self, kind: str, payload):
        if kind == "voice":
            command = self._capture_voice()
            if command is None:
                return
        else:
            command = payload
        if not command:
            return

        self.transcript.emit(command)
        self.chat_turn.emit("user", command)

        self.state.emit("Processing")
        self._turn += 1
        intent = brain.think(command, self._turn, history.recent())
        # Stopped while Gemini was thinking: drop the answer before it can launch
        # anything, so Stop during Processing never fires an action behind your back.
        if self._stopped():
            return

        if intent["error"]:
            self.state.emit("Error")
            self._say(*(BRAIN_BUSY if intent["error"] == "quota" else BRAIN_FAILED))
            return

        ok = None
        if intent["action"] == "open":
            ok, speak_fallback, display_fallback = actions.open_target(intent["target"])
        elif intent["action"] == "close":
            ok, speak_fallback, display_fallback = actions.close_target(intent["target"])
        else:
            speak_fallback, display_fallback = NOT_UNDERSTOOD

        # Trust Gemini's warm reply when the action succeeded (or none was needed);
        # fall back to the deterministic message so a failure is never misreported.
        if ok is False:
            speak_message, display_message = speak_fallback, display_fallback
        else:
            speak_message = intent["reply"] or speak_fallback
            display_message = intent["display"] or display_fallback

        history.add_turn("user", command)
        history.add_turn("assistant", display_message)

        self._say(speak_message, display_message)


class WakeWordWorker(QtCore.QThread):
    """Continuously listens for "Hey Mustafa" and triggers a command capture.

    Paused while CommandWorker is busy (Listening/Processing/Speaking) so the
    two threads never fight over the microphone at the same time.
    """

    heard = QtCore.pyqtSignal()

    MAX_DEAD_READS = 3   # give up on a device that hands back nothing

    def __init__(self):
        super().__init__()
        self._running = True
        self._dead_reads = 0
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
                # stt.listen skips Whisper entirely on a silent chunk, so an empty
                # room costs almost no CPU here.
                text, mic_ok = stt.listen(WAKE_CHUNK_SECONDS)
            except Exception as exc:
                print(f"[wakeword] error: {exc}")
                mic_ok, text = False, ""   # counted once, just below
                self.msleep(500)

            if not mic_ok:
                self._dead_reads += 1
                if self._dead_reads >= self.MAX_DEAD_READS:
                    print("[wakeword] microphone is not delivering audio — listener off")
                    return   # stop the thread; the Listen button still reports properly
                continue
            self._dead_reads = 0
            if not self._active.is_set():
                continue  # paused mid-chunk (e.g. the user clicked Listen) — drop it
            if self._running and wakeword.heard_wake_word(text):
                self.pause()  # stop listening immediately so it can't race the capture
                self.heard.emit()


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    worker = CommandWorker()
    wake_worker = WakeWordWorker()

    def handle_state(state: str):
        window.set_state(state)
        busy = state not in ("Idle",)
        window.set_busy(busy)
        if busy or not WAKE_WORD_ENABLED:
            wake_worker.pause()
        else:
            wake_worker.resume()

    worker.state.connect(handle_state)
    worker.transcript.connect(window.set_transcript)
    worker.chat_turn.connect(window.append_chat)
    worker.level.connect(window.set_level)
    worker.mic_missing.connect(wake_worker.stop)   # nothing to listen to; shut it down
    wake_worker.heard.connect(worker.submit_voice)

    for role, text, ts in history.all_turns():
        window.append_chat(role, text, ts)

    def start_listening():
        # Silence the wake-word thread first so it releases the microphone at once,
        # instead of waiting for the worker thread to reach the Listening state.
        wake_worker.pause()
        window.set_busy(True)
        worker.submit_voice()

    def submit_typed():
        text = window.input_box.text().strip()
        if text:
            worker.submit_text(text)
            window.input_box.clear()

    def clear_history():
        history.clear()
        worker.reset_turns()

    window.input_box.returnPressed.connect(submit_typed)
    window.send_btn.clicked.connect(submit_typed)
    window.listen_btn.clicked.connect(start_listening)
    window.stop_btn.clicked.connect(worker.request_stop)
    window.suggestion.connect(worker.submit_text)   # example chips in the empty state
    window.clear_requested.connect(clear_history)
    QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Space"), window).activated.connect(start_listening)

    app.aboutToQuit.connect(worker.stop)
    app.aboutToQuit.connect(wake_worker.stop)

    worker.start()
    if WAKE_WORD_ENABLED:
        wake_worker.start()
    window.showFilled()
    exit_code = app.exec()
    worker.stop()
    wake_worker.stop()
    worker.wait(3000)
    wake_worker.wait(3000)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
