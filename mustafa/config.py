"""Configuration and environment loading for MUSTAFA.

Everything tunable lives here. The knobs that people actually want to change
(voice, model size, listening timings) can also be overridden from `.env`
without editing code — see the env var name next to each setting.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _env_str(key: str, default: str) -> str:
    return (os.getenv(key) or "").strip() or default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env_str(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    return _env_str(key, "yes" if default else "no").lower() in ("1", "true", "yes", "on")


# --- Identity ---
ASSISTANT_NAME = "Mustafa"
WAKE_WORD = "mustafa"  # matched inside recognized speech (case-insensitive)
# Whisper often mangles the wake word; accept close variants too.
WAKE_WORD_VARIANTS = ("mustafa", "mustapha", "mustufa", "mustaffa", "mostafa", "musttafa")

# --- Gemini (brain) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# NOTE: "gemini-flash-latest" points at the newest Flash model, whose *free* tier
# is only ~5 requests/minute and which takes ~3 s to answer — it starts returning
# 429 after a few turns, and the assistant then looks broken ("samajh nahi aaya")
# when it was really just rate-limited. A Flash-Lite model answers in under a
# second and has a much roomier free quota, which is what a voice UI needs.
GEMINI_MODEL = _env_str("GEMINI_MODEL", "gemini-3.5-flash-lite")
# Tried once if the primary model is rate-limited or unavailable: slower but smarter.
GEMINI_FALLBACK_MODEL = _env_str("GEMINI_FALLBACK_MODEL", "gemini-3.6-flash")

# --- Text-to-speech (env: MUSTAFA_TTS_VOICE / _RATE / _PITCH) ---
# Free Microsoft Edge neural voices (need internet, no API key). These are real
# human recordings-based neural voices — far more natural than offline SAPI.
#   ur-PK-AsadNeural   male, Pakistani Urdu   (default)
#   ur-PK-UzmaNeural   female, Pakistani Urdu
#   ur-IN-SalmanNeural male, Indian Urdu
#   hi-IN-MadhurNeural male, Hindi  (good for heavy Hinglish)
#   en-IN-PrabhatNeural male, Indian English (use if you mostly speak English)
TTS_VOICE = _env_str("MUSTAFA_TTS_VOICE", "ur-PK-AsadNeural")
# Prosody. Dropping the pitch slightly is what makes it read as a calm person
# rather than a machine; the rate is pushed above the stock delivery because a
# reply you have to sit through is worse than one that arrives briskly.
TTS_RATE = _env_str("MUSTAFA_TTS_RATE", "+18%")    # e.g. "+30%" faster, "-10%" slower
TTS_PITCH = _env_str("MUSTAFA_TTS_PITCH", "-3Hz")  # e.g. "-8Hz" deeper, "+5Hz" brighter
TTS_VOLUME = _env_str("MUSTAFA_TTS_VOLUME", "+0%")

# --- Speech-to-text (Whisper) ---
# Model size is a pure speed/accuracy trade (measured on a 4-core CPU, ~3.5 s of
# speech):  tiny ~2.4 s,  base ~4.5 s,  small ~14 s.  "small" understands Urdu
# noticeably better but is far too slow to talk to on a CPU this size, so "base"
# is the default. Change it in .env if your machine says otherwise:
#   MUSTAFA_WHISPER_MODEL=small   -> better Urdu, much slower
#   MUSTAFA_WHISPER_MODEL=tiny    -> fastest, more mistakes
WHISPER_MODEL = _env_str("MUSTAFA_WHISPER_MODEL", "base")
# The background wake-word listener runs every couple of seconds and only has to
# spot one name, so it uses the smallest model — spending the accurate model's CPU
# there is what makes the whole app feel sluggish.
WHISPER_WAKE_MODEL = _env_str("MUSTAFA_WAKE_MODEL", "tiny")
# Leave empty for auto-detect (handles English + Urdu + Hinglish). Force with
# "ur" or "en" if auto-detect keeps guessing wrong (env: MUSTAFA_STT_LANGUAGE).
WHISPER_LANGUAGE = _env_str("MUSTAFA_STT_LANGUAGE", "") or None
SAMPLE_RATE = 16000
# Microphone device index. None = auto-detect (picks a "Microphone" input if the
# Windows default is unset). Set to a number from sd.query_devices() to force one.
INPUT_DEVICE = None

# --- Listening / timing (seconds) ---
# Recording is voice-activity driven, not a fixed window: it starts the moment
# you click Listen and stops as soon as you stop talking. These bound it.
LISTEN_START_TIMEOUT = _env_float("MUSTAFA_LISTEN_START_TIMEOUT", 5.0)  # wait this long for you to begin
SILENCE_TAIL = _env_float("MUSTAFA_SILENCE_TAIL", 0.8)   # end of speech = this much quiet
MAX_COMMAND_SECONDS = _env_float("MUSTAFA_MAX_COMMAND", 12.0)  # hard cap on one utterance
MIN_SPEECH_SECONDS = 0.30   # shorter than this = a cough, not a command
CALIBRATION_SECONDS = 0.30  # measured at the start of each capture to learn room noise
SILENCE_MARGIN = 3.0        # speech = this many times louder than the room floor

# --- Wake word ---
WAKE_WORD_ENABLED = _env_bool("MUSTAFA_WAKE_WORD", True)
WAKE_CHUNK_SECONDS = 2.0    # length of each background wake-word chunk

# --- Feedback ---
BEEP_ENABLED = _env_bool("MUSTAFA_BEEP", True)  # short tone when listening starts/stops


def require_api_key() -> str:
    """Return the Gemini key or raise a clear, user-friendly error."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Open the .env file and paste your free "
            "key from https://aistudio.google.com after 'GEMINI_API_KEY='."
        )
    return GEMINI_API_KEY
