"""Brain: turn recognized speech into a structured intent using Google Gemini."""

import json
import re

import google.generativeai as genai

from .config import GEMINI_MODEL, require_api_key

_model = None

SYSTEM_PROMPT = """You are the intent parser for a Windows voice assistant named Mustafa.
The user speaks in English, Urdu, or mixed "Hinglish". Convert their command into JSON.

Return ONLY a JSON object, nothing else, shaped exactly like:
{"action": "open" | "close" | "unknown", "target": "<app or file name, lowercase>"}

Rules:
- "open", "kholo", "chalao", "start karo", "launch"  -> action "open"
- "close", "band karo", "band kar do", "kill", "quit" -> action "close"
- If the command is NOT about opening/closing an app or file, use action "unknown" and target "".
- Normalize target to a short app name: "Google Chrome" -> "chrome", "Notepad kholo" -> "notepad".

Examples:
"open notepad"        -> {"action": "open", "target": "notepad"}
"notepad kholo"       -> {"action": "open", "target": "notepad"}
"chrome band karo"    -> {"action": "close", "target": "chrome"}
"calculator chalao"   -> {"action": "open", "target": "calculator"}
"whats the weather"   -> {"action": "unknown", "target": ""}
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


def parse_intent(text: str) -> dict:
    """Return {"action": "open"|"close"|"unknown", "target": str}."""
    text = (text or "").strip()
    if not text:
        return {"action": "unknown", "target": ""}
    try:
        resp = _get_model().generate_content(text)
        data = _extract_json((resp.text or "").strip())
        action = data.get("action", "unknown")
        target = str(data.get("target", "")).strip().lower()
        if action not in ("open", "close"):
            action = "unknown"
        return {"action": action, "target": target}
    except Exception as exc:  # network/API/parse issues -> safe fallback
        print(f"[brain] error: {exc}")
        return {"action": "unknown", "target": ""}


if __name__ == "__main__":
    # Quick manual test: python -m mustafa.brain "notepad kholo"
    import sys

    query = " ".join(sys.argv[1:]) or "open notepad"
    print(query, "->", parse_intent(query))
