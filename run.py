"""Launch MUSTAFA:  python run.py"""

import ctypes
import sys

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
