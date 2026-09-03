# MUSTAFA — Project Specification

**Project:** MUSTAFA — Voice-Controlled Desktop Assistant for Windows
**Owner:** owais.piaic@gmail.com
**Date:** 2026-09-03
**Status:** Specification (pre-development)

---

## 1. Overview

MUSTAFA is a "Iron Man"-style voice assistant for Windows. The user speaks to it through a
microphone; it understands natural-language commands (English + Roman-Urdu/Hinglish), replies
by voice, and performs actions on the computer. It presents a polished, futuristic, "robotic"
interface.

- **Assistant name:** Mustafa
- **Wake word:** "Hey Mustafa"

**Milestone 1 goal (this spec's focus):** open and close applications/files by voice.

---

## 2. Goals & Non-Goals

### Goals (Milestone 1)
- Activate on the wake word **"Hey Mustafa."**
- Understand spoken commands to **open** a named app/file.
- Understand spoken commands to **close/kill** a named app.
- Reply by voice to confirm each action.
- Show a live, professional UI with a state-reactive orb.
- Tolerate mixed English + Roman-Urdu input.

### Non-Goals (Milestone 1)
- System control (volume, brightness, shutdown), web search, vision, messaging — **later**.
- Multi-view UI, memory database, browser automation — **later**.
- Cross-platform support — **Windows only** for now.

---

## 3. User Stories

| # | As a user, I want to… | So that… |
|---|------------------------|----------|
| U1 | say "Hey Mustafa" | the assistant starts listening hands-free |
| U2 | say "Notepad kholo" / "open Notepad" | the app launches without touching the keyboard |
| U3 | say "Chrome band karo" / "close Chrome" | the app closes hands-free |
| U4 | see the assistant's state (listening/thinking/speaking) | I know it heard me |
| U5 | hear a spoken confirmation | I trust the action happened |
| U6 | hear a spoken error when a command is unclear | I can retry instead of guessing |

---

## 4. Functional Requirements

- **FR1 — Wake word:** Continuously listen for **"Hey Mustafa"**; only then capture a command.
- **FR2 — Audio capture:** After the wake word, capture the microphone audio for the command.
- **FR3 — Speech-to-text:** Convert speech to text via **Whisper (local)**; tolerate Hinglish/Roman-Urdu + English.
- **FR4 — Intent parsing (Gemini):** Send recognized text to Google Gemini; get back a
  structured intent: `{ action: open | close, target: "<app/file name>" }`.
- **FR5 — Action execution:**
  - `open` → launch the app/file (`os.startfile`, `subprocess`).
  - `close` → terminate the process (`taskkill` / process kill).
- **FR6 — Voice response:** Speak a confirmation or error via **pyttsx3 / Windows SAPI**.
- **FR7 — UI state:** Reflect `Idle / Listening / Processing / Speaking / Error` visually.
- **FR8 — Unknown command handling:** If intent is unclear, respond by voice ("I didn't
  understand that") instead of failing silently.

---

## 5. Non-Functional Requirements

- **Cost:** Fully free — no paid services. Only Gemini calls leave the machine (free API tier).
- **Latency:** Aim for a responsive feel (target sub-second STT→reply where practical).
- **Robustness:** A failed action must not crash the app; surface it as an error state + voice.
- **Look & feel:** Dark theme, electric-blue/neon accents, animated orb (see §7).
- **Privacy:** STT, TTS, and wake word run offline; only the Gemini text call uses the internet.
- **Platform:** Windows 10+.

---

## 6. Architecture (5 layers)

Keep layers decoupled so any engine (STT, TTS, LLM, UI) can be swapped independently.

```
 mic → [1] wake-word "Hey Mustafa" → [2] STT (Whisper) → [3] Gemini (intent) → [4] Action engine → result
                                                                                       ↓
                                                     [5] UI update + TTS voice reply (pyttsx3)
```

1. **UI shell** — window with animated orb + state indicator.
2. **Audio input (STT)** — mic capture, wake word "Hey Mustafa", speech→text (Whisper local).
3. **Brain (Gemini)** — text → structured intent (`google-generativeai` SDK).
4. **Action engine** — executes intent against Windows (open/close).
5. **Audio output (TTS)** — speaks responses (pyttsx3 / Windows SAPI).

---

## 7. UI / UX Specification

- **Centerpiece:** an animated glowing orb / particle sphere that reacts to state:
  - `Idle` — slow calm pulse
  - `Listening` — active ripple/expansion
  - `Processing` — spinning / swirling
  - `Speaking` — pulse synced to voice
  - `Error` — red flash
- **Theme:** dark background, electric-blue / neon accents, glassmorphism panels.
- **Status text:** current state label + last recognized command (small transcript line).
- **Branding:** "MUSTAFA" wordmark; wake-word hint "Say 'Hey Mustafa'".

---

## 8. Tech Stack (finalized — all free)

| Layer | Choice | Cost |
|-------|--------|------|
| Core | Python 3.10+ | free |
| UI | **PyQt/PySide** | free |
| STT | **Whisper (local, e.g. `faster-whisper`)** | free (offline; ~1–2 GB model download) |
| Wake word | **"Hey Mustafa"** (Porcupine custom keyword or Whisper-based) | free |
| TTS | **pyttsx3 / Windows SAPI** | free (offline) |
| Brain (LLM) | **Google Gemini** (`google-generativeai`) | free API key (aistudio.google.com) |

No purchases required. A natural human-voice TTS (ElevenLabs) is an optional paid upgrade for later.

---

## 9. Acceptance Criteria (Milestone 1 "done")

- [ ] Saying "Hey Mustafa" starts a listening state.
- [ ] Speaking "open Notepad" (or Hinglish equivalent) launches Notepad.
- [ ] Speaking "close Notepad" terminates it.
- [ ] Each action gets a spoken confirmation.
- [ ] An unclear command produces a spoken "didn't understand" response, no crash.
- [ ] The orb visibly changes across Idle → Listening → Processing → Speaking.
- [ ] Works with at least a few mixed English/Roman-Urdu phrasings.

---

## 10. Resolved Decisions

1. **Assistant name:** Mustafa ✅
2. **Wake word:** "Hey Mustafa" ✅
3. **UI framework:** PyQt/PySide (native Python) ✅
4. **Voice engines:** offline & free — Whisper (STT) + pyttsx3 (TTS) ✅
5. **Brain:** Google Gemini, free API key ✅
6. **Activation:** wake word "Hey Mustafa" (a manual button/hotkey may be added later as backup) ✅

---

_See `CLAUDE.md` for working guidance and the post-M1 roadmap._
