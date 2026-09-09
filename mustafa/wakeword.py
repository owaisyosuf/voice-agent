"""Wake-word detection for "Hey Mustafa" (Whisper-based, fully free/offline).

This listens in short chunks and triggers when the wake word appears in the
transcription. Silent chunks are thrown away by an energy check before Whisper
ever sees them (see stt.is_silent) — otherwise the background listener would run
a full transcription every couple of seconds and starve the rest of the app.
It is heavier than a dedicated engine like Porcupine, but needs no extra account
or key; Porcupine can later replace this behind wait_for_wake().
"""

from .config import WAKE_CHUNK_SECONDS, WAKE_WORD_VARIANTS
from .stt import listen


def heard_wake_word(text: str) -> bool:
    """True if any accepted spelling of the wake word is in the transcript.

    Whisper rarely spells an unfamiliar name the same way twice, so matching only
    "mustafa" exactly made the wake word feel broken.
    """
    lowered = (text or "").lower()
    return any(variant in lowered for variant in WAKE_WORD_VARIANTS)


def wait_for_wake(should_stop=None) -> bool:
    """Block until the wake word is heard.

    should_stop: optional callable; if it returns True, abort and return False.
    """
    while True:
        if should_stop and should_stop():
            return False
        if heard_wake_word(listen(WAKE_CHUNK_SECONDS)):
            return True
