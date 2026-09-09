"""Brain: one Gemini call per turn that both classifies the command (open/close/
unknown + target) and writes Mustafa's warm, human-like spoken reply — including
general Q&A, greetings, and conversation memory. Combined into a single call to
stay within the free-tier daily request quota.
"""

import json
import re

from .config import GEMINI_FALLBACK_MODEL, GEMINI_MODEL, require_api_key

_client = None

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
- Normalize target to a short app name in Latin letters: "Google Chrome" -> "chrome", \
"Notepad kholo" -> "notepad". If the user says an app name in Urdu script, write the \
target in Latin letters anyway ("نوٹ پیڈ" -> "notepad").
- The speech-to-text is imperfect: if a word is close to a known app name \
(e.g. "not pad", "no pad" -> notepad; "crome", "chorme" -> chrome), assume that app.

Writing "reply" and "display" — same content, two scripts, for two different jobs:
- "reply" is read aloud by an Urdu neural text-to-speech voice. Write it ENTIRELY in \
Urdu script (Arabic/Nastaliq) — INCLUDING app and file names, transliterated into Urdu \
script ("notepad" -> "نوٹ پیڈ", "chrome" -> "کروم", "calculator" -> "کیلکولیٹر", \
"YouTube" -> "یوٹیوب"). NEVER leave Latin letters, digits, emojis, markdown (* _ # `) \
or bullet lists inside "reply": the voice mispronounces Latin words with a broken \
accent, and that single detail is what makes it sound robotic instead of human. Write \
numbers as Urdu words ("5" -> "پانچ").
- Write "reply" the way a person actually talks: short sentences, natural commas so \
the voice can breathe, no lists, no headings, no parentheses.
- "display" is shown as on-screen text: write the SAME meaning in Roman Urdu (Roman/\
Latin transliteration) — UNLESS the content is naturally English (e.g. the user asked \
in English, or the answer is technical/code/English-heavy), in which case write \
"display" in plain English instead. Never put Arabic/Nastaliq script in "display".
- If action is "open" or "close": write a short, warm line as if you are about to do it \
now (e.g. reply "نوٹ پیڈ کھولتا ہوں" / display "notepad kholta hoon") — you do not yet \
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
- Keep it short enough to speak comfortably — one or two sentences for commands and \
small talk. A real question may run a little longer, but never more than a few lines: \
the user is waiting while it is spoken aloud.

Examples:
"open notepad" -> {"action": "open", "target": "notepad", "reply": "جی بالکل، نوٹ پیڈ \
کھولتا ہوں۔", "display": "Ji bilkul, notepad kholta hoon."}
"chrome band karo" -> {"action": "close", "target": "chrome", "reply": "ٹھیک ہے، کروم \
بند کر رہا ہوں۔", "display": "Theek hai, chrome band kar raha hoon."}
"what's the capital of France" -> {"action": "unknown", "target": "", "reply": "پیرس \
فرانس کا دارالحکومت ہے۔", "display": "Paris is the capital of France."}
"""

# Ask for JSON directly instead of hoping it shows up inside prose. A plain dict
# rather than types.GenerateContentConfig, so google.genai.types never has to load.
_CONFIG = {
    "system_instruction": SYSTEM_PROMPT,
    "response_mime_type": "application/json",
    "temperature": 0.7,      # some variety in phrasing, without going off-script
    "max_output_tokens": 500,
}


def _get_client():
    """Build the Gemini client on first use.

    google.genai is imported here rather than at module scope because it costs
    several seconds to load, and at module scope that delay lands before the window
    can even appear.
    """
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=require_api_key())
    return _client


def preload() -> None:
    """Open the Gemini connection at startup.

    The first call pays the library import plus auth/channel setup. Doing it while the
    app is warming up means the user's first real command answers in about a second.
    count_tokens is used because it costs no generation quota.
    """
    try:
        _get_client().models.count_tokens(model=GEMINI_MODEL, contents="hi")
    except Exception as exc:
        print(f"[brain] preload skipped: {exc}")


def _is_quota_error(exc: Exception) -> bool:
    if getattr(exc, "code", None) == 429:
        return True
    text = str(exc).lower()
    return "429" in text or "quota" in text or "rate limit" in text


def _should_try_fallback(exc: Exception) -> bool:
    """Rate-limited, or the model isn't available on this key — both are worth a retry."""
    return _is_quota_error(exc) or getattr(exc, "code", None) == 404 or "404" in str(exc)


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
    """Return {"action", "target", "reply", "display", "error"} for one turn.

    `reply` is Urdu script (for TTS accent), `display` is Roman Urdu/English (for on-screen
    text). `error` is "" normally, or "quota"/"failed" so the caller can say something
    truthful instead of pretending it didn't understand.
    `history`: optional list of (role, text) tuples, oldest first, for memory.
    """
    text = (text or "").strip()
    if not text:
        return _empty()

    context = ""
    if history:
        context += "Recent conversation:\n"
        for role, past_text in history:
            who = "User" if role == "user" else "Mustafa"
            context += f"{who}: {past_text}\n"
        context += "---\n"
    context += f"Turn number: {turn}\nUser: {text}"

    for model_name in (GEMINI_MODEL, GEMINI_FALLBACK_MODEL):
        try:
            resp = _get_client().models.generate_content(
                model=model_name, contents=context, config=_CONFIG
            )
            return _parse(_extract_json((resp.text or "").strip()))
        except Exception as exc:  # network/API/parse issues
            print(f"[brain] {model_name} error: {exc}")
            if _should_try_fallback(exc) and model_name != GEMINI_FALLBACK_MODEL:
                continue  # rate-limited / unavailable: try the fallback model once
            return _empty("quota" if _is_quota_error(exc) else "failed")
    return _empty("quota")


def _parse(data: dict) -> dict:
    action = data.get("action", "unknown")
    if action not in ("open", "close"):
        action = "unknown"
    return {
        "action": action,
        "target": str(data.get("target", "")).strip().lower(),
        "reply": str(data.get("reply", "")).strip(),
        "display": str(data.get("display", "")).strip(),
        "error": "",
    }


def _empty(error: str = "") -> dict:
    return {"action": "unknown", "target": "", "reply": "", "display": "", "error": error}


if __name__ == "__main__":
    # Quick manual test: python -m mustafa.brain "notepad kholo"
    import sys

    query = " ".join(sys.argv[1:]) or "open notepad"
    print(query, "->", think(query))
