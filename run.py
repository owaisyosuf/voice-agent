"""Launch MUSTAFA:  python run.py"""

import ctypes
import os
import sys

# The windowed desktop build has no console, so stdout/stderr are None — and the
# progress bar of a first-run Whisper model download writes to stderr and would crash.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Urdu text in log lines must not blow up on a cp1252 console.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Hide the console window if one got attached (e.g. launched via python.exe
# instead of pythonw.exe) — MUSTAFA is a GUI app, it shouldn't show a terminal.
_console = ctypes.windll.kernel32.GetConsoleWindow()
if _console:
    ctypes.windll.user32.ShowWindow(_console, 0)  # SW_HIDE

from mustafa.main import main

if __name__ == "__main__":
    main()
