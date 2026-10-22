"""Freeze Mustafa into a Windows desktop build with PyInstaller.

Run from the project root, inside the venv:

    .venv\\Scripts\\python.exe build_desktop.py

The result is `dist/Mustafa/Mustafa.exe`. Make a desktop shortcut to that .exe;
the folder beside it holds the Python runtime and libraries and has to travel
with it. A folder build (onedir) rather than a single .exe, because onefile
unpacks ~300MB of Qt, CTranslate2 and onnxruntime to a temp dir on every launch.

Things PyInstaller cannot work out on its own:

- faster-whisper ships the Silero VAD model as a data file, and CTranslate2
  loads its native DLLs at runtime, so both are collected whole.
- pyttsx3 picks its SAPI driver by name with importlib, which no import graph
  reveals.

The Whisper models themselves are not bundled: faster-whisper downloads them to
the user's Hugging Face cache on first run, exactly as it does from source.

The project's .env (the Gemini key) is copied beside Mustafa.exe, which is
where mustafa/config.py looks for it in the frozen app.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "Mustafa"


def main() -> None:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", APP_NAME,
        "--collect-all", "faster_whisper",
        "--collect-all", "ctranslate2",
        "--hidden-import", "pyttsx3.drivers",
        "--hidden-import", "pyttsx3.drivers.sapi5",
        "--exclude-module", "tkinter",
        str(ROOT / "run.py"),
    ]
    print("Building — this takes a few minutes.\n", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)

    out = ROOT / "dist" / APP_NAME
    env = ROOT / ".env"
    if env.exists():
        shutil.copy2(env, out / ".env")
    else:
        print("\nNo .env found: put one with GEMINI_API_KEY beside the .exe.")

    print(f"\nBuilt: {out / (APP_NAME + '.exe')}")
    print("Make a desktop shortcut to that .exe. Keep the folder it sits in.")


if __name__ == "__main__":
    main()
