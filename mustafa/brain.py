"""Brain: one Gemini call per turn that both classifies the command (open/close/
unknown + target) and writes Mustafa's warm, human-like spoken reply — including
general Q&A, greetings, and conversation memory. Combined into a single call to
stay within the free-tier daily request quota.
"""

import json
import re

import google.generativeai as genai

from .config import GEMINI_MODEL, require_api_key

_model = None

SYSTEM_PROMPT = """You are Mustafa, a warm and respectful Urdu-speaking voice \
assistant/butler for your user — like Jarvis. The user speaks in English, Urdu, or \
mixed "Hinglish", typed or transcribed from speech.

For every message, return ONLY a JSON object, nothing else, shaped exactly like:
{"action": "open" | "close" | "unknown", "target": "<app or file name, lowercase, or \
"">", "reply": "<your spoken reply>", "display": "<same reply, for on-screen text>"}

Classifying action/target:
- "open", "kholo", "chalao", "start karo", "launch" -> action "open"
- "close", "band karo", "band kar do", "kill", "quit" -> action "close"
- If the message is NOT a request to open/close an app or file (including plain chat, \
greetings, or questions), use action "unknown" and target "".
- Normalize target to a short app name: "Google Chrome" -> "chrome", "Notepad kholo" -> \
"notepad".

Writing "reply" and "display" — same content, two scripts, for two different jobs:
- "reply" is read aloud by a text-to-speech engine: write it ONLY in Urdu script \
(Arabic/Nastaliq), except keep app/file names, numbers, and technical terms in Latin \
script exactly as given. This script is what makes the voice's Urdu accent sound right.
- "display" is shown as on-screen text: write the SAME meaning in Roman Urdu (Roman/\
Latin transliteration) — UNLESS the content is naturally English (e.g. the user asked \
in English, or the answer is technical/code/English-heavy), in which case write \
"display" in plain English instead. Never put Arabic/Nastaliq script in "display".
- If action is "open" or "close": write a short, warm line as if you are about to do it \
now (e.g. reply "notepad کھولتا ہوں" / display "notepad kholta hoon") — you do not yet \
know for certain it will succeed, so don't over-promise, just sound natural and willing.
- If action is "unknown": this may be a real question, a greeting, or small talk. If \
it's a genuine question (facts, explanations, advice, calculations, translations, \
anything at all), answer it fully and accurately like a knowledgeable assistant — don't \
deflect. If it's chat/greeting, respond naturally and helpfully like a person would. \
Only apologize for not understanding if the message genuinely looked like an actionable \
app/file request you could not figure out.
- Use the recent conversation, if given in the message, to stay consistent — you have \
real memory of this chat; don't repeat questions already answered.
- On turn 1 of the conversation, greet the user warmly (e.g. "Assalam-o-Alaikum") and/or \
ask how they are (khairiyat) before the rest of your reply.
- Sound like a real human, not a robot: warm, natural, and varied — never repeat the \
exact same sentence every turn. Every so often (not every turn), close by offering \
further help, e.g. "Koi aur hukum?" or "Aur kuch chahiye?" — vary the phrasing.
- Keep it brief enough to speak comfortably; a real question can run a little longer \
than small talk, but stay concise.

Examples:
"open notepad" -> {"action": "open", "target": "notepad", "reply": "جی بالکل، notepad \
کھولتا ہوں۔", "display": "Ji bilkul, notepad kholta hoon."}
"chrome band karo" -> {"action": "close", "target": "chrome", "reply": "ٹھیک ہے، chrome \
بند کر رہا ہوں۔", "display": "Theek hai, chrome band kar raha hoon."}
"what's the capital of France" -> {"action": "unknown", "target": "", "reply": "پیرس \
فرانس کا دارالحکومت ہے۔", "display": "Paris is the capital of France."}
"""


def _get_model():
    global _model
    if _model is None:
        genai.configure(api_key=require_api_key())
        _model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=SYSTEM_PROMPT)
    return _model


def _extract_json(raw: str) -> dict:
    """Pull the first {...} block out of the model's reply and parse it."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def think(text: str, turn: int = 1, history=None) -> dict:
    """Return {"action", "target", "reply", "display"} for one turn, in a single Gemini call.

    `reply` is Urdu script (for TTS accent), `display` is Roman Urdu/English (for on-screen
    text). `history`: optional list of (role, text) tuples, oldest first, for memory.
    """
    text = (text or "").strip()
    if not text:
        return {"action": "unknown", "target": "", "reply": "", "display": ""}

    context = ""
    if history:
        context += "Recent conversation:\n"
        for role, past_text in history:
            who = "User" if role == "user" else "Mustafa"
            context += f"{who}: {past_text}\n"
        context += "---\n"
    context += f"Turn number: {turn}\nUser: {text}"

    try:
        resp = _get_model().generate_content(context)
        data = _extract_json((resp.text or "").strip())
        action = data.get("action", "unknown")
        if action not in ("open", "close"):
            action = "unknown"
        target = str(data.get("target", "")).strip().lower()
        reply = str(data.get("reply", "")).strip()
        display = str(data.get("display", "")).strip()
        return {"action": action, "target": target, "reply": reply, "display": display}
    except Exception as exc:  # network/API/parse issues -> safe fallback
        print(f"[brain] error: {exc}")
        return {"action": "unknown", "target": "", "reply": "", "display": ""}


if __name__ == "__main__":
    # Quick manual test: python -m mustafa.brain "notepad kholo"
    import sys

    query = " ".join(sys.argv[1:]) or "open notepad"
    print(query, "->", think(query))
