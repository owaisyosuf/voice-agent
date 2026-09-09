"""Text-to-speech: Microsoft Edge's free neural voice, with an offline fallback.

edge-tts calls Microsoft's free Read Aloud service (no API key, but needs internet)
and gives a real Urdu neural voice that pronounces Roman Urdu/Hinglish far more
naturally than the robotic English SAPI voices. Rate/pitch come from config —
dropping the pitch is most of what makes it read as a calm person.

Playback is interruptible: `stop()` cuts the current line off mid-sentence, which
is what the UI's Stop button needs.

If the online call fails (no network), we fall back to the offline pyttsx3/SAPI
voice, speaking the Roman-script version of the line — SAPI cannot pronounce
Urdu script at all and would otherwise go silent or spell it out.
"""

import asyncio
import ctypes
import itertools
import os
import re
import tempfile
import threading

import edge_tts

from .config import TTS_PITCH, TTS_RATE, TTS_VOICE, TTS_VOLUME

_winmm = ctypes.windll.winmm
_alias_counter = itertools.count()
_speak_lock = threading.Lock()  # never let two replies overlap on the speakers

# Interruption. `_stopped` is set by stop() and stays set until the next speak(),
# so a stop landing in the gap before playback starts still suppresses the line.
_stopped = threading.Event()
_playing_lock = threading.Lock()
_playing_alias = None
_offline_engine = None

# Characters that are meant to be read, not spoken (Gemini occasionally emits
# markdown); speaking them aloud is an instant "this is a robot" tell.
_STRIP = re.compile(r"[*_`#>\[\]]+")


def _clean(text: str) -> str:
    return _STRIP.sub("", text or "").strip()


def _play_mp3(path: str) -> None:
    global _playing_alias
    alias = f"mustafa_tts_{next(_alias_counter)}"
    _winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
    try:
        with _playing_lock:
            if _stopped.is_set():
                return
            _playing_alias = alias
        # "wait" blocks until the clip ends — or until stop() sends `stop <alias>`
        # from the UI thread, which makes this return early.
        _winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
    finally:
        with _playing_lock:
            _playing_alias = None
        _winmm.mciSendStringW(f"close {alias}", None, 0, None)


def _speak_online(text: str) -> None:
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        communicate = edge_tts.Communicate(
            text,
            voice=TTS_VOICE,
            rate=TTS_RATE,
            pitch=TTS_PITCH,
            volume=TTS_VOLUME,
        )
        asyncio.run(communicate.save(path))
        if os.path.getsize(path) == 0:
            raise RuntimeError("edge-tts returned empty audio")
        _play_mp3(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _pick_sapi_voice(engine):
    """Prefer an installed Urdu/Hindi SAPI voice over the default English one."""
    try:
        for voice in engine.getProperty("voices"):
            name = f"{voice.id} {voice.name}".lower()
            if any(tag in name for tag in ("urdu", "hindi", "-ur", "-hi", "india", "pakistan")):
                engine.setProperty("voice", voice.id)
                return
    except Exception:
        pass


def _speak_offline(text: str) -> None:
    try:
        import pythoncom
        import pyttsx3
    except ImportError as exc:  # offline voice unavailable — stay quiet, don't crash
        print(f"[tts] offline voice not installed: {exc}")
        return

    global _offline_engine
    com_initialized = False
    try:
        pythoncom.CoInitialize()
        com_initialized = True
    except Exception:
        pass  # already initialized on this thread — fine, leave its ownership alone
    try:
        if _stopped.is_set():
            return
        engine = pyttsx3.init()
        _pick_sapi_voice(engine)
        engine.setProperty("rate", 195)  # brisk; the 175 default drags in Roman Urdu
        _offline_engine = engine
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as exc:
        print(f"[tts] offline fallback error: {exc}")
    finally:
        _offline_engine = None
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def stop() -> None:
    """Cut off whatever is being spoken. Safe to call from any thread, any time."""
    _stopped.set()
    with _playing_lock:
        alias = _playing_alias
    if alias:
        _winmm.mciSendStringW(f"stop {alias}", None, 0, None)
    engine = _offline_engine
    if engine is not None:
        try:
            engine.stop()
        except Exception:
            pass


def speak(text: str, roman_fallback: str = "") -> None:
    """Speak `text` with the neural voice.

    `roman_fallback` is the same line in Roman script; it is what the offline SAPI
    voice gets, since SAPI cannot read Urdu script.
    """
    text = _clean(text)
    if not text:
        return
    with _speak_lock:
        _stopped.clear()
        try:
            _speak_online(text)
        except Exception as exc:
            if _stopped.is_set():
                return  # interrupted, not broken — don't repeat the line offline
            print(f"[tts] edge-tts unavailable ({exc}), falling back to offline voice")
            _speak_offline(_clean(roman_fallback) or text)


if __name__ == "__main__":
    # Quick voice audition:  python -m mustafa.tts
    speak("السلام علیکم، میں مصطفیٰ ہوں۔ بتائیے، کیا خدمت کروں؟", "Assalam-o-Alaikum.")
