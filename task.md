# MUSTAFA — Task Checklist (Milestone 1)

Legend: [ ] todo · [~] in progress · [x] done

## Phase 0 — Scaffold & config
- [x] `requirements.txt`
- [x] `.env` (user pastes `GEMINI_API_KEY`)
- [x] `.gitignore`
- [x] `mustafa/` package + `config.py`
- [x] `README.md`

## Phase 1 — Brain (Gemini)
- [x] `mustafa/brain.py` — `parse_intent(text) -> {action, target}`

## Phase 2 — Action engine
- [x] `mustafa/actions.py` — `open_target()` / `close_target()`

## Phase 3 — Voice output (TTS)
- [x] `mustafa/tts.py` — `speak(text)`

## Phase 4 — Speech-to-text (Whisper)
- [x] `mustafa/stt.py` — `record()` / `transcribe()` / `listen()`

## Phase 5 — Wake word
- [x] `mustafa/wakeword.py` — "Hey Mustafa" (Whisper-based)

## Phase 6 — UI
- [x] `mustafa/ui/orb_window.py` — PyQt6 window + animated orb

## Phase 7 — Wire together
- [x] `mustafa/main.py` — assistant loop on QThread + UI signals
- [x] `run.py` — entry point

## Verification
- [x] Paste free Gemini API key into `.env`
- [x] `pip install -r requirements.txt` (exit 0)
- [x] Brain works (English + Hinglish + unknown) — model set to `gemini-flash-latest`
- [x] Actions work (notepad open + close)
- [x] TTS runs without error
- [ ] Full app `python run.py` with mic — **user to test** (needs microphone + speakers)
