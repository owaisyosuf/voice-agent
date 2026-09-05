"""Text-to-speech: Microsoft Edge's free neural voice, with an offline fallback.

edge-tts calls Microsoft's free Read Aloud service (no API key, but needs internet)
and gives a real Urdu voice (ur-PK-AsadNeural) that pronounces Roman Urdu/Hinglish
far more naturally than the robotic English SAPI voices. If that call fails (no
network), we fall back to the offline pyttsx3/SAPI voice so speaking never goes
silent just because the network is down.
"""

import asyncio
import ctypes
import os
import tempfile

import edge_tts

from .config import TTS_VOICE

_winmm = ctypes.windll.winmm


def _play_mp3(path: str) -> None:
    alias = "mustafa_tts"
    _winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
    try:
        _winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
    finally:
        _winmm.mciSendStringW(f"close {alias}", None, 0, None)


def _speak_online(text: str) -> None:
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        asyncio.run(edge_tts.Communicate(text, voice=TTS_VOICE).save(path))
        _play_mp3(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _speak_offline(text: str) -> None:
    import pythoncom
    import pyttsx3

    com_initialized = False
    try:
        pythoncom.CoInitialize()
        com_initialized = True
    except Exception:
        pass  # already initialized on this thread — fine, leave its ownership alone
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as exc:
        print(f"[tts] offline fallback error: {exc}")
    finally:
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def speak(text: str) -> None:
    if not text:
        return
    try:
        _speak_online(text)
    except Exception as exc:
        print(f"[tts] edge-tts unavailable ({exc}), falling back to offline voice")
        _speak_offline(text)


if __name__ == "__main__":
    speak("مصطفی آن لائن ہے۔")
