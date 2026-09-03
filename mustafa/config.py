"""Configuration and environment loading for MUSTAFA."""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Identity ---
ASSISTANT_NAME = "Mustafa"
WAKE_WORD = "mustafa"  # matched inside recognized speech (case-insensitive)

# --- Gemini (brain) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# Free-tier friendly model. "gemini-flash-latest" always maps to the current
# fast Flash model. Change here if you prefer another (see genai.list_models()).
GEMINI_MODEL = "gemini-flash-latest"

# --- Speech-to-text (Whisper) ---
# "base" balances speed/accuracy on CPU. Options: tiny, base, small, medium.
WHISPER_MODEL = "base"
SAMPLE_RATE = 16000
# Microphone device index. None = auto-detect (picks a "Microphone" input if the
# Windows default is unset). Set to a number from sd.query_devices() to force one.
INPUT_DEVICE = None

# --- Timing (seconds) ---
WAKE_CHUNK_SECONDS = 3     # length of each wake-word listening chunk
COMMAND_SECONDS = 4        # how long to record the actual command


def require_api_key() -> str:
    """Return the Gemini key or raise a clear, user-friendly error."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Open the .env file and paste your free "
            "key from https://aistudio.google.com after 'GEMINI_API_KEY='."
        )
    return GEMINI_API_KEY
