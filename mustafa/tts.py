"""Text-to-speech via pyttsx3 (offline Windows SAPI voice).

pyttsx3's SAPI5 driver is known to go silent after the first call if a single
engine instance is reused across calls, especially from a background thread
(COM apartment state gets stuck). The reliable fix is to initialize COM on the
calling thread and create a fresh engine for every utterance.
"""

import pythoncom
import pyttsx3


def speak(text: str) -> None:
    if not text:
        return
    try:
        pythoncom.CoInitialize()
    except Exception:
        pass  # already initialized on this thread — fine
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as exc:
        print(f"[tts] error: {exc}")
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


if __name__ == "__main__":
    speak("Mustafa online hai.")
