# MUSTAFA — Milestone 1 Implementation Plan

## Context

`G:\JARVIS` is a greenfield project. So far only planning docs exist (`CLAUDE.md`, `SPECIFY.md`)
which fully specify the product: **MUSTAFA**, a Windows voice assistant with a futuristic PyQt UI.

**Milestone 1 (this plan):** the user says **"Hey Mustafa"**, gives a spoken command, and the app
**opens or closes a named application/file**, replying by voice. All engines are free:

- **STT:** Whisper local (`faster-whisper`) — understands English + Urdu + Hinglish
- **TTS:** `pyttsx3` (Windows SAPI voice)
- **Brain:** Google Gemini (`google-generativeai`, free API key)
- **UI:** PyQt6 window with an animated state-reactive orb
- **Wake word:** "Hey Mustafa"

Goal: a working, fully-free desktop app meeting the M1 acceptance criteria in `SPECIFY.md §9`.
Layers stay decoupled so post-M1 roadmap items slot in without rework.

## Build order (incremental & testable)

Build the text-only brain + actions first (testable by typing, no mic needed), then add audio, then UI.

### Phase 0 — Scaffold & config
- `requirements.txt`: `google-generativeai`, `faster-whisper`, `pyttsx3`, `PyQt6`,
  `sounddevice`, `numpy`, `python-dotenv`, `pvporcupine` (wake word).
- `.env.example` (`GEMINI_API_KEY=`) and `.gitignore` (`.env`, `__pycache__/`, models).
- Package `mustafa/` with `__init__.py` and `config.py` (loads `GEMINI_API_KEY` via
  `python-dotenv`; clear error if missing).
- `README.md` with setup steps (get free Gemini key, `pip install -r requirements.txt`, run).

### Phase 1 — Brain (`mustafa/brain.py`)
- `parse_intent(text) -> {"action": "open"|"close"|"unknown", "target": str}`.
- Gemini prompt returns JSON only; maps Hinglish/Urdu ("kholo", "chalao", "band karo") to
  `open`/`close` and normalizes the app name.
- Robust JSON parsing; on failure return `action: "unknown"`.
- Standalone testable: run with a typed string, print the intent.

### Phase 2 — Action engine (`mustafa/actions.py`)
- `open_target(name)`: map common names (notepad, chrome, calculator…) → executables; launch via
  `os.startfile` / `subprocess.Popen`. Fallback: try the raw name.
- `close_target(name)`: resolve to a process image name, run `taskkill /F /IM <exe>`. Return
  success/failure so the caller speaks the right response.
- Editable app-name → exe map (dict) for easy extension.
- Standalone testable without any audio.

### Phase 3 — Voice output (`mustafa/tts.py`)
- Thin `pyttsx3` wrapper: `speak(text)` (init once, select a Windows voice, adjustable rate).

### Phase 4 — Speech-to-text (`mustafa/stt.py`)
- `faster-whisper` model (`base`/`small` for speed); load once at startup.
- `record_command(seconds)` via `sounddevice`; `transcribe(audio)` returns text.
- Language auto so Hinglish/Urdu works.

### Phase 5 — Wake word (`mustafa/wakeword.py`)
- Fallback first (zero extra accounts): lightweight always-listening loop running short Whisper
  transcriptions, triggers when "mustafa" is heard.
- Upgrade path: `pvporcupine` continuous listener for "Hey Mustafa" (free Picovoice key + custom
  `.ppn`), behind the same `wait_for_wake()` interface.

### Phase 6 — UI (`mustafa/ui/orb_window.py`)
- PyQt6 window: dark theme, neon-blue accents, "MUSTAFA" wordmark, status label, and a
  custom-painted **animated orb** (QTimer-driven) with states:
  `Idle` (slow pulse), `Listening` (ripple), `Processing` (spin), `Speaking` (pulse), `Error` (red).
- `set_state(state)` + transcript line showing the last recognized command.
- Manual "Listen" button as a backup trigger.

### Phase 7 — Wire it together (`mustafa/main.py`)
- Assistant loop on a **QThread** (keeps PyQt UI responsive); state to UI via Qt signals.
- Loop: `Idle` → `wait_for_wake()` → `Listening` → `record_command()` → `Processing` →
  `transcribe()` → `parse_intent()` → `open/close` → `Speaking` + `speak(confirmation)` → `Idle`.
  Unknown intent → speak a graceful "samajh nahi aaya / didn't understand", return to Idle.

## Proposed structure
```
G:\JARVIS\
  mustafa/
    __init__.py
    config.py        # env / API key
    brain.py         # Gemini intent parsing
    actions.py       # open/close apps
    stt.py           # Whisper local
    tts.py           # pyttsx3
    wakeword.py      # "Hey Mustafa"
    main.py          # entry point, assistant loop + UI wiring
    ui/
      __init__.py
      orb_window.py  # PyQt window + animated orb
  requirements.txt
  .env.example
  .gitignore
  README.md
```

## Prerequisite (user)
- A **free Gemini API key** from https://aistudio.google.com → put it in `.env` as `GEMINI_API_KEY`.
- (Optional, best wake word) a free Picovoice access key + "Hey Mustafa" `.ppn`; otherwise the
  Whisper fallback is used automatically.

## Verification (against SPECIFY.md §9)
- **Brain/actions (no mic):** run `brain.py` / `actions.py` with typed strings — confirm
  "open Notepad" and "Notepad kholo" both yield `open/notepad`, and Notepad launches/closes.
- **Voice path:** launch app, say "Hey Mustafa" → orb Listening → "open Notepad" → Notepad opens +
  spoken confirmation; repeat with "close Notepad".
- **Hinglish:** "Notepad kholo" / "Chrome band karo".
- **Error path:** gibberish → graceful spoken "didn't understand", no crash.
- **UI states:** orb transitions Idle → Listening → Processing → Speaking.

## Notes / risks
- First `faster-whisper` run downloads a model (~1–2 GB) — one-time, offline afterward.
- Whisper-based wake word is heavier/less snappy than Porcupine; fine for M1, upgrade later.
- Everything post-M1 (memory, chat view, system control) is intentionally **out of scope**.
