"""Speech-to-text using a local Whisper model (faster-whisper).

Capture is *voice-activity driven*, not a fixed window: recording opens the
moment you ask for it and closes as soon as you stop talking. That is what makes
the assistant feel responsive — it never waits out a timer after you finish, and
it never cuts you off mid-sentence the way a hard 4-second window did.
"""

import queue
import threading
import time

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from .config import (
    BEEP_ENABLED,
    CALIBRATION_SECONDS,
    INPUT_DEVICE,
    LISTEN_START_TIMEOUT,
    MAX_COMMAND_SECONDS,
    MIN_SPEECH_SECONDS,
    SAMPLE_RATE,
    SILENCE_MARGIN,
    SILENCE_TAIL,
    WAKE_WORD_ENABLED,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
    WHISPER_WAKE_MODEL,
)

_models: dict[str, WhisperModel] = {}
_model_lock = threading.Lock()
_input_device = "unset"  # cached resolved mic index (None once resolved to "none found")

# Only one recording at a time: the wake-word thread and the command thread share
# one microphone, and on Windows a second capture stream can fail outright.
mic_lock = threading.RLock()

# Absolute floor under which no mic is ever considered "speaking", so a dead-quiet
# room can't calibrate the threshold down onto its own noise.
_ABS_SPEECH_FLOOR = 0.006

# Consecutive ~20 ms frames of sound needed before we call it speech.
_ONSET_BLOCKS = 3

# Highest room-noise level we will believe during calibration.
_MAX_NOISE_FLOOR = 0.015

# Nudges Whisper towards this app's vocabulary and mixed Urdu/English style.
_INITIAL_PROMPT = (
    "Hey Mustafa. Open notepad. Chrome band karo. Notepad kholo. "
    "Calculator kholo. YouTube open karo. Kya haal hai?"
)


def preload() -> None:
    """Load the Whisper models now (call at startup so the first command isn't slow)."""
    _get_model(WHISPER_MODEL)
    if WAKE_WORD_ENABLED and WHISPER_WAKE_MODEL != WHISPER_MODEL:
        _get_model(WHISPER_WAKE_MODEL)


def _get_model(name: str) -> WhisperModel:
    with _model_lock:
        if name not in _models:
            # CPU + int8 keeps it light and GPU-free. First load downloads the model.
            _models[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _models[name]


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

    # Otherwise score every input and take the best one. Windows exposes the same
    # mic several times through different host APIs, plus traps like "Stereo Mix"
    # (records the speakers, not you) and Bluetooth "Hands-Free" (8 kHz, unusable
    # for speech recognition) — picking the first match got those wrong.
    devices = sd.query_devices()
    inputs = [i for i, d in enumerate(devices) if d["max_input_channels"] > 0]
    if not inputs:
        _input_device = None
        raise RuntimeError(
            "No microphone found. Connect a mic and set it as the default "
            "recording device in Windows Sound settings."
        )
    chosen = max(inputs, key=lambda i: _score_input(devices[i]))
    print(f"[stt] using microphone: {devices[chosen]['name'].strip()}")
    _input_device = chosen
    return chosen


# Host APIs, best first for microphone capture. WDM-KS is last: it opens the device
# in exclusive kernel-streaming mode, bypassing Windows' mic boost and AGC, which
# makes recordings very quiet — a common cause of "it didn't hear me".
_HOST_API_RANK = ("wasapi", "mme", "directsound", "wdm-ks")


def _score_input(device) -> int:
    name = device["name"].lower()
    score = 0
    if "microphone" in name or "mic " in name or name.endswith("mic"):
        score += 100
    if "headset" in name and "hands-free" not in name:
        score += 40
    if "stereo mix" in name or "line in" in name or name.startswith("line"):
        score -= 200  # records the speakers / an unplugged jack, never the user
    if "hands-free" in name or "hf audio" in name:
        score -= 150  # 8 kHz Bluetooth telephony mode: terrible for STT
    if float(device.get("default_samplerate", 0)) >= 16000:
        score += 20
    try:
        host = sd.query_hostapis(device["hostapi"])["name"].lower()
        for rank, key in enumerate(_HOST_API_RANK):
            if key in host:
                score += (len(_HOST_API_RANK) - rank) * 8
                break
    except Exception:
        pass
    return score


def _device_rate(device) -> int:
    return int(sd.query_devices(device)["default_samplerate"])


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Linear-interpolation resample (good enough for speech STT, no extra deps)."""
    if orig_sr == target_sr or len(audio) == 0:
        return audio
    target_len = int(len(audio) * target_sr / orig_sr)
    x_old = np.linspace(0.0, 1.0, len(audio), endpoint=False)
    x_new = np.linspace(0.0, 1.0, target_len, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def _normalize(audio: np.ndarray) -> np.ndarray:
    """Lift a quiet mic to a comfortable level — quiet input is a top cause of
    garbled transcriptions. Gain is capped so room hiss isn't blown up."""
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak < 1e-5:
        return audio
    return (audio * min(0.95 / peak, 8.0)).astype(np.float32)


def beep(kind: str = "start") -> None:
    """Short tone so you know exactly when to start and when it stopped listening.

    Played through the normal output device: winsound.Beep goes to the PC-speaker
    path, which is silent on plenty of machines. That one falls back on it.
    """
    if not BEEP_ENABLED:
        return
    freq = 880 if kind == "start" else 560
    try:
        rate, duration = 44100, 0.09
        samples = np.arange(int(rate * duration), dtype=np.float32) / rate
        tone = 0.25 * np.sin(2 * np.pi * freq * samples)
        fade = int(rate * 0.008)          # ramp the ends or it clicks
        envelope = np.ones_like(tone)
        envelope[:fade] = np.linspace(0.0, 1.0, fade)
        envelope[-fade:] = np.linspace(1.0, 0.0, fade)
        sd.play((tone * envelope).astype(np.float32), rate, blocking=True)
    except Exception:
        try:
            import winsound

            winsound.Beep(freq, 90)
        except Exception:
            pass


# Capture as int16, not float32. Not every Windows backend can hand PortAudio
# float samples (the WDM-KS one returns garbage for them), but every backend
# supports 16-bit PCM — so we convert ourselves.
_DTYPE = "int16"
_INT16_SCALE = 32768.0


def _to_float(audio: np.ndarray) -> np.ndarray:
    return (audio.astype(np.float32) / _INT16_SCALE).astype(np.float32)


def record(seconds: float) -> np.ndarray:
    """Record a fixed-length chunk (used by the background wake-word listener).

    Returns an EMPTY array if the device delivered nothing in time — meaning the
    microphone is dead. This used to be `sd.rec()` + `sd.wait()`, which waits for
    a recording that a dead device never finishes: it blocked forever while
    holding the microphone lock, so pressing Listen hung in Listening for good.
    Every wait here is bounded.
    """
    device = resolve_input_device()
    dev_sr = _device_rate(device)
    block = max(160, int(dev_sr * 0.02))
    wanted = int(seconds * dev_sr)

    frames: "queue.Queue[np.ndarray]" = queue.Queue()

    def on_audio(indata, _frames, _time_info, _status):
        frames.put(_to_float(indata[:, 0].copy()))

    if not mic_lock.acquire(timeout=0.5):
        return np.zeros(0, dtype=np.float32)   # a capture is in progress; skip this chunk
    try:
        collected: list[np.ndarray] = []
        got = 0
        with sd.InputStream(
            samplerate=dev_sr, channels=1, dtype=_DTYPE,
            device=device, blocksize=block, callback=on_audio,
        ):
            deadline = time.monotonic() + seconds + 1.5
            while got < wanted and time.monotonic() < deadline:
                try:
                    frame = frames.get(timeout=0.25)
                except queue.Empty:
                    continue
                collected.append(frame)
                got += len(frame)
    finally:
        mic_lock.release()

    if not collected:
        return np.zeros(0, dtype=np.float32)
    return _resample(np.concatenate(collected), dev_sr, SAMPLE_RATE)


def record_utterance(on_speech_start=None, should_stop=None, on_level=None):
    """Record one spoken utterance, ending on silence.

    Returns (audio, reason) where reason is "ok", "no_speech" (nothing was said
    within LISTEN_START_TIMEOUT), "too_short", "no_audio" (the device delivered
    nothing — muted or misconfigured), "mic_busy" (another thread is stuck on the
    device), or "cancelled".
    `on_speech_start` is called the instant speech is detected, and `on_level`
    receives the loudness as 0..1 a few times a second — both exist so the UI can
    show that the microphone is genuinely hearing something.
    """
    device = resolve_input_device()
    dev_sr = _device_rate(device)
    block = max(160, int(dev_sr * 0.02))  # ~20 ms frames
    block_secs = block / dev_sr

    blocks: list[np.ndarray] = []
    noise_samples: list[float] = []
    threshold = None
    started = False
    loud_run = 0
    speech_start_block = 0
    speech_secs = 0.0
    silence_secs = 0.0
    began = time.monotonic()

    # Frames arrive on PortAudio's callback thread. (A blocking stream.read() would
    # be simpler, but PortAudio's WDM-KS backend — which is what Windows exposes when
    # no default recording device is set — rejects the blocking API outright.)
    frames: "queue.Queue[np.ndarray]" = queue.Queue()

    def on_audio(indata, _frames, _time_info, _status):
        frames.put(_to_float(indata[:, 0].copy()))

    # Beep before anything can block, so pressing Listen always makes a sound.
    beep("start")
    # Bounded: if the wake-word thread is stuck on a bad device, fail loudly in a
    # couple of seconds instead of sitting in Listening forever.
    if not mic_lock.acquire(timeout=2.5):
        return None, "mic_busy"
    try:
        with sd.InputStream(
            samplerate=dev_sr, channels=1, dtype=_DTYPE,
            device=device, blocksize=block, callback=on_audio,
        ):
            while True:
                if should_stop and should_stop():
                    return None, "cancelled"
                try:
                    frame = frames.get(timeout=0.5)
                except queue.Empty:
                    # The stream opened but the driver is delivering nothing at all —
                    # a dead/disabled input. Say so instead of timing out silently.
                    if not blocks and time.monotonic() - began >= 2.0:
                        return None, "no_audio"
                    if time.monotonic() - began >= MAX_COMMAND_SECONDS:
                        break
                    continue
                blocks.append(frame)
                rms = float(np.sqrt(np.mean(np.square(frame))))
                elapsed = time.monotonic() - began

                # 1. Learn the room's noise floor from the first fraction of a second.
                if threshold is None:
                    noise_samples.append(rms)
                    if elapsed >= CALIBRATION_SECONDS:
                        # Cap the floor: if the user starts talking during calibration,
                        # an uncapped floor would set the bar above their own voice and
                        # nothing would ever register as speech.
                        floor = min(float(np.median(noise_samples)), _MAX_NOISE_FLOOR)
                        threshold = max(floor * SILENCE_MARGIN, _ABS_SPEECH_FLOOR)
                    continue

                # A keyboard click or a door is loud for one frame; speech isn't.
                # Requiring a short run of loud frames stops single spikes from both
                # starting a capture and from holding one open forever.
                loud_run = loud_run + 1 if rms > threshold else 0

                # Feed the UI meter ~12x a second: often enough to look live,
                # rare enough not to flood the signal queue.
                if on_level and len(blocks) % 4 == 0:
                    on_level(min(1.0, rms / max(threshold * 4.0, 1e-6)))

                # 2. Wait for the user to actually start talking.
                if not started:
                    if loud_run >= _ONSET_BLOCKS:
                        started = True
                        speech_start_block = len(blocks) - loud_run
                        if on_speech_start:
                            on_speech_start()
                    elif elapsed - CALIBRATION_SECONDS >= LISTEN_START_TIMEOUT:
                        # Perfectly flat input for the whole window means a muted or
                        # misrouted device, not a user who stayed quiet.
                        flat = float(np.max(np.abs(np.concatenate(blocks)))) < 1e-6
                        return None, "no_audio" if flat else "no_speech"
                    continue

                # 3. Talking: stop once they have been quiet long enough.
                if loud_run >= 2:
                    speech_secs += block_secs
                    silence_secs = 0.0
                else:
                    silence_secs += block_secs
                    if silence_secs >= SILENCE_TAIL:
                        break
                if elapsed >= MAX_COMMAND_SECONDS:
                    break
    finally:
        mic_lock.release()

    beep("end")

    if speech_secs < MIN_SPEECH_SECONDS:
        return None, "too_short"

    # Keep ~0.25 s of lead-in so the first syllable isn't clipped, drop the rest.
    lead = max(0, speech_start_block - int(0.25 / block_secs))
    audio = np.concatenate(blocks[lead:])
    return _normalize(_resample(audio, dev_sr, SAMPLE_RATE)), "ok"


def is_silent(audio: np.ndarray, threshold: float = _ABS_SPEECH_FLOOR) -> bool:
    """Cheap energy check — lets the wake-word loop skip Whisper on empty audio.

    Running Whisper on every silent chunk is what pegs the CPU and makes the rest
    of the app feel sluggish, so this gate matters more than it looks.
    """
    if audio is None or len(audio) == 0:
        return True
    return float(np.max(np.abs(audio))) < threshold * 2.5


def transcribe(audio: np.ndarray, model: str = "", beam_size: int = 5) -> str:
    """Transcribe recorded audio to text (English/Urdu/Hinglish)."""
    if audio is None or len(audio) == 0:
        return ""
    segments, _info = _get_model(model or WHISPER_MODEL).transcribe(
        audio,
        language=WHISPER_LANGUAGE,      # None = auto-detect
        beam_size=beam_size,            # better accuracy; audio is short so it stays cheap
        temperature=0.0,
        vad_filter=True,                # drop non-speech before decoding
        vad_parameters={"min_silence_duration_ms": 300},
        condition_on_previous_text=False,  # stops one bad guess poisoning the next
        initial_prompt=_INITIAL_PROMPT,
        no_speech_threshold=0.6,
    )
    return " ".join(seg.text for seg in segments).strip()


def listen(seconds: float):
    """Record a fixed window and transcribe it (wake-word path).

    Returns (text, mic_ok). `mic_ok` is False when the device handed back nothing,
    which lets the caller stop hammering a microphone that isn't there.

    Uses the smaller, faster wake model with greedy decoding: this runs every couple
    of seconds in the background, and it only has to spot one name — spending the
    accurate model's CPU here would slow down everything else.
    """
    audio = record(seconds)
    if len(audio) == 0:
        return "", False
    if is_silent(audio):
        return "", True
    return transcribe(audio, model=WHISPER_WAKE_MODEL, beam_size=1), True


def probe_microphone() -> bool:
    """Is there a microphone that actually delivers audio? Checked once at startup
    so a machine without one can say so up front instead of hanging on Listen."""
    try:
        return len(record(0.4)) > 0
    except Exception as exc:
        print(f"[stt] microphone probe failed: {exc}")
        return False


def listen_once(on_speech_start=None, should_stop=None, on_level=None):
    """Capture one utterance and transcribe it. Returns (text, reason)."""
    audio, reason = record_utterance(on_speech_start, should_stop, on_level)
    if reason != "ok":
        return "", reason
    return transcribe(audio), "ok"


if __name__ == "__main__":
    # Microphone check:  python -m mustafa.stt
    # Lists every input, shows which one MUSTAFA picked, then records you once.
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    all_devices = sd.query_devices()
    print("Input devices:")
    for index, dev in enumerate(all_devices):
        if dev["max_input_channels"] > 0:
            host = sd.query_hostapis(dev["hostapi"])["name"]
            print(f"  [{index:2}] {dev['name'].strip()[:55]:<55} {host}"
                  f"  score={_score_input(dev)}")
    print()
    picked = resolve_input_device()
    print(f"picked device index: {picked}")
    print(f"Loading Whisper '{WHISPER_MODEL}' (first run downloads it)...")
    preload()
    print("Speak after the beep...")
    heard, why = listen_once(on_speech_start=lambda: print("  ...hearing you"))
    print(f"result ({why}): {heard!r}")
