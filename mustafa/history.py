"""Persistent chat history (SQLite) so the assistant remembers prior turns
across restarts and the UI can show a full chat log.
"""

import os
import sqlite3
from datetime import datetime, timezone

_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "history.db")

_conn = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL
            )"""
        )
        _conn.commit()
    return _conn


def add_turn(role: str, text: str) -> None:
    """role: "user" or "assistant"."""
    if not text:
        return
    conn = _get_conn()
    conn.execute(
        "INSERT INTO turns (ts, role, text) VALUES (?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), role, text),
    )
    conn.commit()


def recent(limit: int = 6) -> list[tuple[str, str]]:
    """Last `limit` turns, oldest first — used as conversation context for the brain."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, text FROM turns ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return list(reversed(rows))


def all_turns(limit: int = 200) -> list[tuple[str, str]]:
    """Last `limit` turns, oldest first — used to repopulate the chat view on startup."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, text FROM turns ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return list(reversed(rows))
