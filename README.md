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
| Text-to-speech | pyttsx3 (Windows voice) | free / offline |
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

## Using it

- Say **"Hey Mustafa"**, wait for the orb to turn to *Listening*, then say your command:
  - "open notepad" / "notepad kholo"
  - "close chrome" / "chrome band karo"
  - "calculator chalao"
- Or click the **Listen** button to skip the wake word.

Add more apps by editing `APP_MAP` in `mustafa/actions.py`.

## Testing pieces individually

```
python -m mustafa.brain "notepad kholo"      # see the parsed intent
python -m mustafa.actions open notepad       # test opening
python -m mustafa.actions close notepad      # test closing
python -m mustafa.tts                        # test the voice
```

## Project docs

- `SPECIFY.md` — full product specification
- `plan.md` — implementation plan
- `task.md` — build checklist
- `CLAUDE.md` — guidance + post-M1 roadmap
