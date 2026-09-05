"""Action engine: open and close Windows applications."""

import os
import subprocess

# app name -> (launch command, process image name for taskkill)
APP_MAP = {
    "notepad": ("notepad.exe", "notepad.exe"),
    "calculator": ("calc.exe", "CalculatorApp.exe"),
    "calc": ("calc.exe", "CalculatorApp.exe"),
    "chrome": ("chrome", "chrome.exe"),
    "google chrome": ("chrome", "chrome.exe"),
    "edge": ("msedge", "msedge.exe"),
    "microsoft edge": ("msedge", "msedge.exe"),
    "firefox": ("firefox", "firefox.exe"),
    "paint": ("mspaint.exe", "mspaint.exe"),
    "explorer": ("explorer.exe", "explorer.exe"),
    "file explorer": ("explorer.exe", "explorer.exe"),
    "cmd": ("cmd.exe", "cmd.exe"),
    "command prompt": ("cmd.exe", "cmd.exe"),
    "terminal": ("wt.exe", "WindowsTerminal.exe"),
    "word": ("winword", "WINWORD.EXE"),
    "excel": ("excel", "EXCEL.EXE"),
    "vlc": ("vlc", "vlc.exe"),
    "spotify": ("spotify", "Spotify.exe"),
    "vs code": ("code", "Code.exe"),
    "vscode": ("code", "Code.exe"),
}


def open_target(name: str):
    """Launch an app/file. Returns (ok: bool, speak_message: str, display_message: str).

    `speak_message` is Urdu script (correct TTS accent); `display_message` is the same
    thing in Roman Urdu, for on-screen text.
    """
    name = (name or "").strip().lower()
    if not name:
        return False, "کیا کھولنا ہے سمجھ نہیں آیا۔", "Kya kholna hai samajh nahi aaya."

    launch = APP_MAP.get(name, (None,))[0]
    try:
        if launch:
            subprocess.Popen(launch, shell=True)
        else:
            os.startfile(name)  # try as a raw command or file path
        return True, f"{name} کھول رہا ہوں۔", f"{name} khol raha hoon."
    except Exception as exc:
        print(f"[actions] open error: {exc}")
        return False, f"{name} کھول نہیں پایا۔", f"{name} khol nahi paya."


def close_target(name: str):
    """Terminate an app by name. Returns (ok: bool, speak_message: str, display_message: str).

    `speak_message` is Urdu script (correct TTS accent); `display_message` is the same
    thing in Roman Urdu, for on-screen text.
    """
    name = (name or "").strip().lower()
    if not name:
        return False, "کیا بند کرنا ہے سمجھ نہیں آیا۔", "Kya band karna hai samajh nahi aaya."

    mapped = APP_MAP.get(name, (None, None))[1]
    image = mapped or (name if name.endswith(".exe") else name + ".exe")
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", image],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return True, f"{name} بند کر دیا۔", f"{name} band kar diya."
        return False, f"{name} چل نہیں رہا تھا۔", f"{name} chal nahi raha tha."
    except Exception as exc:
        print(f"[actions] close error: {exc}")
        return False, f"{name} بند نہیں کر پایا۔", f"{name} band nahi kar paya."


if __name__ == "__main__":
    # Quick manual test: python -m mustafa.actions open notepad
    import sys

    verb = sys.argv[1] if len(sys.argv) > 1 else "open"
    tgt = " ".join(sys.argv[2:]) or "notepad"
    fn = open_target if verb == "open" else close_target
    print(fn(tgt))
