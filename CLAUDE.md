# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**Milestone 1 shipped and iterating.** The app runs: PyQt6 UI, voice-activity-driven Whisper
capture, Gemini brain with SQLite conversation memory, Edge neural TTS, and an open/close action
engine with Start Menu lookup. What follows describes the product; see "Layout of the code" for
where each layer actually lives.

## What This Project Is

**MUSTAFA** — a "Jarvis"-style voice assistant for Windows. The user speaks to it through a
microphone; it understands natural-language commands and takes actions on the machine. The first
milestone is narrow: **open and close applications/files by voice.** It must present a polished,
futuristic ("robotic") UI/UX.

- **Assistant name:** Mustafa
- **Wake word:** "Hey Mustafa"

Primary user communicates in Urdu/Hindi (Roman script) and English — speech recognition and command
parsing must tolerate mixed-language ("Hinglish") input. (The repo folder is still named `JARVIS`;
that's cosmetic — the product/brand is Mustafa.)

## Target Architecture

Five decoupled layers. Keep them separated so each (STT engine, TTS voice, LLM brain, UI skin) can be
swapped without touching the others.

1. **UI shell** — desktop window with an animated status orb/waveform, dark theme, neon accents.
   States to surface: `Idle`, `Listening`, `Processing`, `Speaking`, `Error`.
2. **Audio input (STT)** — microphone capture + wake-word detection ("Hey Mustafa") + speech-to-text.
3. **Audio output (TTS)** — speaks responses back.
4. **Brain (NLU)** — converts recognized text into a structured intent + action, via an LLM.
5. **Action engine** — executes intents against the OS (launch apps, close/kill processes, open files).

Data flow: `mic → wake-word ("Hey Mustafa") → STT → Brain (intent) → Action engine → result → TTS + UI update`.

## Milestone 1 — Scope

- Voice command → open a named application or file (`os.startfile`, `subprocess`).
- Voice command → close/kill a named application (`taskkill` / process termination).
- UI reflects live state; assistant confirms each action by voice.
- Everything else (reminders, web search, system control) is out of scope for M1 — do not build it unless asked.

## Future Roadmap (post-M1)

Based on how mature Jarvis assistants are built (e.g. bertrandmbanwi/Jarvis, AnubhavChaturvedi/jarvis-ai-assistant).
Build M1's UI and layer boundaries so these can be added later without rework — do **not** implement them in M1.

**High priority (add soon after M1):**
- **Chat / transcript view** — show recognized text and replies next to the orb; allow text input too.
- **Conversation memory** — persist context (e.g. SQLite) so Gemini answers with awareness of prior turns.
- **Error / fallback voice feedback** — when a command isn't understood, say so gracefully; never fail silently.
- **Hinglish / Urdu support** — STT and parsing must tolerate mixed Roman-Urdu + English (primary user's language).

**Medium priority:**
- **Global hotkey activation** — trigger listening via a keyboard shortcut, in addition to the wake word.
- **Background / system-tray mode** — keep listening while minimized.
- **Low latency** — target sub-second STT→reply.

**Later / optional:**
- System control (volume, brightness, screenshot, shutdown).
- Live web search (info beyond the model's training data).
- Multi-view UI: separate **Voice** (orb), **Chat**, and **System** (metrics) screens.
- Computer vision / camera, image generation, messaging automation.
- Natural human-voice TTS (e.g. ElevenLabs) as a paid upgrade over the free Windows voice.

### UI reference (target look)

Mature Jarvis UIs converge on: a central **animated glowing orb / particle sphere** that reacts to state
(idle, listening, thinking, speaking, error); **dark theme with electric-blue / neon accents**; glassmorphism
panels, floating particles, glowing hover buttons. In PyQt this is a 2D animated widget (pulse/ripple/glow);
a 3D particle orb would require Electron/Three.js. M1 should establish the dark + neon orb aesthetic even if
the orb starts simple.

## Tech Stack (finalized — all free)

| Layer | Choice | Notes |
|-------|--------|-------|
| Core | Python 3.10+ | single language for the whole app |
| UI | **PyQt/PySide** | native Python window + animated orb |
| STT | **Whisper (local, e.g. `faster-whisper`)** | offline, free, multilingual — handles English + Urdu + Hinglish; first run downloads a model (~1–2 GB) |
| Wake word | **"Hey Mustafa"** (e.g. Porcupine custom keyword, or Whisper-based) | hands-free activation |
| TTS | **edge-tts neural voice** (`ur-PK-AsadNeural`), pyttsx3/SAPI fallback | free, no key; needs internet |
| Brain (LLM) | **Google Gemini** (`google-genai`), Flash-Lite | free API key from Google AI Studio (aistudio.google.com) |

STT and the wake word run offline; the Gemini call and the neural voice need the network (both free,
and the voice falls back to the offline SAPI one). No paid services required.

## Build / Run / Test

```
pip install -r requirements.txt
python run.py                       # launch the app

python -m mustafa.stt               # mic diagnostic: list inputs, record + transcribe once
python -m mustafa.tts               # audition the voice
python -m mustafa.brain "notepad kholo"   # see the parsed intent
python -m mustafa.actions open notepad    # test the action engine
```

There is no test suite yet; the `python -m` entry points above are the manual checks.

## Layout of the code

| Layer | File | Notes |
|---|---|---|
| Config | `mustafa/config.py` | every tunable, each overridable from `.env` |
| UI tokens | `mustafa/ui/theme.py` | colours, type scale, spacing, per-state colour + copy |
| UI components | `mustafa/ui/widgets.py` | orb, backdrop, level meter, chat bubbles, state pill |
| UI layout | `mustafa/ui/orb_window.py` | window composition only, no painting |
| STT | `mustafa/stt.py` | device scoring, VAD capture, Whisper models (command + wake) |
| Wake word | `mustafa/wakeword.py` | energy-gated Whisper match on "mustafa" + variants |
| Brain | `mustafa/brain.py` | one Gemini call returns action + target + spoken/display reply |
| TTS | `mustafa/tts.py` | edge-tts neural voice, offline SAPI fallback |
| Actions | `mustafa/actions.py` | `APP_MAP` plus Start Menu shortcut lookup, taskkill |
| Memory | `mustafa/history.py` | SQLite turns, used for context and the chat view |
| Orchestration | `mustafa/main.py` | Qt threads: command worker + wake-word worker |

Conventions worth keeping: capture audio as **int16** (some Windows backends return garbage for
float32), keep the Gemini model pinned to a **Flash-Lite** id (the "latest" alias has a ~5 req/min
free tier), and write anything spoken aloud in **Urdu script including app names** — Latin words
inside an Urdu voice are what made it sound robotic.

## Platform Notes

- Target OS is **Windows** (Windows 10). Action-engine code uses Windows-specific mechanisms
  (`os.startfile`, `taskkill`, SAPI) — keep platform assumptions explicit.
- Handle unrecognized commands gracefully: the assistant should say it didn't understand rather than failing silently.
- The Gemini API key is required to run the brain — store it outside source (e.g. env var / `.env`), never hard-code it.

_See `SPECIFY.md` for the full product specification._
