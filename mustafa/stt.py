"""Speech-to-text using a local Whisper model (faster-whisper)."""

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from .config import INPUT_DEVICE, SAMPLE_RATE, WHISPER_MODEL

_model = None
_input_device = "unset"  # cached resolved mic index (None once resolved to "none found")


def _get_model():
    global _model
    if _model is None:
        # CPU + int8 keeps it light and GPU-free. First load downloads the model.
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def resolve_input_device():
    """Return a usable microphone index, auto-detecting if Windows has no default."""
    global _input_device
    if _input_device != "unset":
        return _input_device

    if INPUT_DEVICE is not None:
        _input_device = INPUT_DEVICE
        return _input_device

    # If the system default input is valid, use it.
    try:
        default_in = sd.default.device[0]
    except Exception:
        default_in = -1
    if isinstance(default_in, int) and default_in >= 0:
        _input_device = default_in
        return _input_device

    # Otherwise pick an input device, preferring a real "microphone".
    devices = sd.query_devices()
    inputs = [i for i, d in enumerate(devices) if d["max_input_channels"] > 0]
    if not inputs:
        _input_device = None
        raise RuntimeError(
            "No microphone found. Connect a mic and set it as the default "
            "recording device in Windows Sound settings."
        )
    chosen = next(
        (i for i in inputs if "microphone" in devices[i]["name"].lower()),
        inputs[0],
    )
    _input_device = chosen
    return chosen


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Linear-interpolation resample (good enough for speech STT, no extra deps)."""
    if orig_sr == target_sr or len(audio) == 0:
        return audio
    target_len = int(len(audio) * target_sr / orig_sr)
    x_old = np.linspace(0.0, 1.0, len(audio), endpoint=False)
    x_new = np.linspace(0.0, 1.0, target_len, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def record(seconds: float) -> np.ndarray:
    """Record from the mic at its native rate, resampled to SAMPLE_RATE for Whisper.

    Many Windows audio devices reject 16 kHz directly, so we capture at the
    device's default sample rate and downsample afterwards.
    """
    device = resolve_input_device()
    dev_sr = int(sd.query_devices(device)["default_samplerate"])
    audio = sd.rec(
        int(seconds * dev_sr),
        samplerate=dev_sr,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()
    return _resample(audio.flatten(), dev_sr, SAMPLE_RATE)


def transcribe(audio: np.ndarray) -> str:
    """Transcribe recorded audio to text (auto language: English/Urdu/Hinglish)."""
    segments, _ = _get_model().transcribe(audio, beam_size=1)
    return " ".join(seg.text for seg in segments).strip()


def listen(seconds: float) -> str:
    """Record for `seconds` and return the transcribed text."""
    return transcribe(record(seconds))
