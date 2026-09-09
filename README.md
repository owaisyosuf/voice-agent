# MUSTAFA 🔵

A free, voice-controlled desktop assistant for Windows. Say **"Hey Mustafa"**, give a command,
and it opens or closes apps for you — with a futuristic animated orb UI. Understands English,
Urdu, and mixed **Hinglish**.

## How it works

```
mic → "Hey Mustafa" → Whisper (STT) → Gemini (intent) → open/close app → voice reply + orb
```

| Part | Tech | Cost |
|------|------|------|
| UI | PyQt6 (animated orb) | free |
| Speech-to-text | Whisper local (`faster-whisper`) | free / offline |
| Brain | Google Gemini | free API key |
| Text-to-speech | Edge neural voice (`ur-PK-AsadNeural`), pyttsx3 fallback | free |
| Wake word | "Hey Mustafa" (Whisper-based) | free |

## Setup

1. **Get a free Gemini API key** at <https://aistudio.google.com> and paste it into `.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```
2. **Install dependencies** (Python 3.10+ recommended):
   ```
   pip install -r requirements.txt
   ```
   > First run downloads the Whisper model (~1 GB) once, then works offline.
3. **Run:**
   ```
   python run.py
   ```

## The interface

```
┌─ MUSTAFA ──── ● READY ──────────────────────── ─  □  ✕ ┐
│                              │  CONVERSATION  4 messages│
│           ( orb )            │  ┌────────────────────┐  │
│                              │  │ AAP · 14:12        │  │
│          LISTENING           │  │ notepad kholo      │  │
│   Boliye — beep ke baad…     │  └────────────────────┘  │
│      ▁▃▅▇█▇▅▃▁  (mic level)  │  ┌────────────────────┐  │
│   "notepad kholo"            │  │ MUSTAFA · 14:12    │  │
├──────────────────────────────┴──────────────────────────┤
│ [ type a command…              ]  [ Send ]  [ Listen ]  │
└─────────────────────────────────────────────────────────┘
```

- **Left — the stage.** The orb carries the state (colour + motion), with the state
  name, a one-line instruction, a **live microphone level meter**, and the last thing
  heard or answered.
- **Right — the conversation.** Message bubbles with timestamps, restored from the
  SQLite history on every launch. `Clear` wipes both the thread and Mustafa's memory.
- **Bottom — one composer** for both typing and speaking, so neither input is second
  class. Controls grey out while a command is in flight.

The look lives in three files: `mustafa/ui/theme.py` holds every colour, size and
spacing token; `mustafa/ui/widgets.py` holds the painted components (orb, meter,
bubbles, backdrop); `mustafa/ui/orb_window.py` is layout only. Re-skin the app by
editing `theme.py` alone.

## Using it

- Say **"Hey Mustafa"**, wait for the orb to turn to *Listening*, then say your command:
  - "open notepad" / "notepad kholo"
  - "close chrome" / "chrome band karo"
  - "calculator chalao"
- Or click **Listen** (or press **Ctrl+Space**) to skip the wake word.

**How listening works:** after the beep, just talk. Recording stops on its own about
0.8 s after you stop speaking — there is no fixed window to wait out, and no cutting
you off mid-sentence. If you say nothing for 5 s it gives up and tells you so.

Apps outside `APP_MAP` (in `mustafa/actions.py`) are looked up in your Start Menu, so
"open whatsapp" works without hard-coding it. Add an entry to `APP_MAP` when you want
a specific launch command or a different process name for closing.

## Tuning (`.env`)

Nothing here is required — the defaults work — but every knob is an env var:

```
MUSTAFA_TTS_VOICE=ur-PK-AsadNeural   # ur-PK-UzmaNeural (female), hi-IN-MadhurNeural, en-IN-PrabhatNeural
MUSTAFA_TTS_RATE=-8%                 # slower = calmer;  MUSTAFA_TTS_PITCH=-3Hz
MUSTAFA_WHISPER_MODEL=base           # tiny = fastest, small = best Urdu but ~3x slower
MUSTAFA_STT_LANGUAGE=                # empty = auto; "ur" or "en" to force
MUSTAFA_SILENCE_TAIL=0.8             # how long a pause must be before it stops listening
MUSTAFA_LISTEN_START_TIMEOUT=5       # how long it waits for you to start talking
MUSTAFA_MAX_COMMAND=12               # longest single utterance
MUSTAFA_WAKE_WORD=yes                # "no" turns off the background wake-word listener
MUSTAFA_BEEP=yes                     # "no" silences the start/stop tones
GEMINI_MODEL=gemini-3.5-flash-lite   # fast + roomy free quota; fallback is gemini-3.6-flash
```

## Troubleshooting

**"Mic se koi awaz nahi aa rahi" / it never hears you.** Windows has no default
recording device selected. Open *Settings → System → Sound → Input*, pick your
microphone, and check its input level moves when you speak. Then run:

```
python -m mustafa.stt      # lists every input, shows which one is picked, records you once
```

If the list shows only `WDM-KS` devices, Windows has no enabled recording endpoint at
all — that path returns silence or garbage, and nothing else will work until a real
input is enabled.

**Replies take a long time.** Transcription is the slow part on a CPU without a GPU
(~2 s with `base`, ~14 s with `small` on 4 cores). Set `MUSTAFA_WHISPER_MODEL=tiny`
for the fastest response.

**"Abhi rabta nahi ho pa raha (rate limit)".** The free Gemini tier ran out of
requests for this minute. `gemini-flash-latest` allows only ~5/min, which is why the
default is pinned to a Flash-Lite model instead.

## Testing pieces individually

```
python -m mustafa.brain "notepad kholo"      # see the parsed intent
python -m mustafa.actions open notepad       # test opening
python -m mustafa.actions close notepad      # test closing
python -m mustafa.tts                        # test the voice
python -m mustafa.stt                        # list mics + record and transcribe you once
```

## Project docs

- `SPECIFY.md` — full product specification
- `plan.md` — implementation plan
- `task.md` — build checklist
- `CLAUDE.md` — guidance + post-M1 roadmap
