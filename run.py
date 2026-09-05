"""Launch MUSTAFA:  python run.py"""

import ctypes

# Hide the console window if one got attached (e.g. launched via python.exe
# instead of pythonw.exe) — MUSTAFA is a GUI app, it shouldn't show a terminal.
_console = ctypes.windll.kernel32.GetConsoleWindow()
if _console:
    ctypes.windll.user32.ShowWindow(_console, 0)  # SW_HIDE

from mustafa.main import main

if __name__ == "__main__":
    main()
