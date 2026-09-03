"""Text-to-speech via pyttsx3 (offline Windows SAPI voice)."""

import pyttsx3

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = pyttsx3.init()
        _engine.setProperty("rate", 175)
    return _engine


def speak(text: str) -> None:
    if not text:
        return
    try:
        engine = _get_engine()
        engine.say(text)
        engine.runAndWait()
    except Exception as exc:
        print(f"[tts] error: {exc}")


if __name__ == "__main__":
    speak("Mustafa online hai.")
