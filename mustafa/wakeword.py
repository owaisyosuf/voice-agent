"""Wake-word detection for "Hey Mustafa" (Whisper-based, fully free/offline).

This listens in short chunks and triggers when the wake word appears in the
transcription. It is heavier than a dedicated engine like Porcupine, but needs
no extra account or key. Porcupine can later replace this behind wait_for_wake().
"""

from .config import WAKE_CHUNK_SECONDS, WAKE_WORD
from .stt import listen


def heard_wake_word(text: str) -> bool:
    return WAKE_WORD in (text or "").lower()


def wait_for_wake(should_stop=None) -> bool:
    """Block until the wake word is heard.

    should_stop: optional callable; if it returns True, abort and return False.
    """
    while True:
        if should_stop and should_stop():
            return False
        if heard_wake_word(listen(WAKE_CHUNK_SECONDS)):
            return True
