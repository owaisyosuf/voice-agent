# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**Greenfield / not yet started.** As of this writing the repository contains only these planning
docs — no source, build config, or dependencies exist yet. This file captures the intended product
and architecture so work can begin coherently. Update it as real code lands.

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
| TTS | **pyttsx3 / Windows SAPI** | offline, free (robotic voice — fits the theme) |
| Brain (LLM) | **Google Gemini** (`google-generativeai`) | free API key from Google AI Studio (aistudio.google.com) |

Only the Gemini call leaves the machine; STT, TTS, and wake word all run offline. No paid services required.

## Build / Run / Test

_None yet — no toolchain exists. Populate this section with the actual commands (install deps, run app,
run a single test) as soon as the project is scaffolded._

## Platform Notes

- Target OS is **Windows** (Windows 10). Action-engine code uses Windows-specific mechanisms
  (`os.startfile`, `taskkill`, SAPI) — keep platform assumptions explicit.
- Handle unrecognized commands gracefully: the assistant should say it didn't understand rather than failing silently.
- The Gemini API key is required to run the brain — store it outside source (e.g. env var / `.env`), never hard-code it.

_See `SPECIFY.md` for the full product specification._
