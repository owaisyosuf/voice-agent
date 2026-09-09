"""Action engine: open and close Windows applications."""

import os
import subprocess

# Keep console windows from flashing up when we shell out.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

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
    "settings": ("ms-settings:", "SystemSettings.exe"),
    "task manager": ("taskmgr.exe", "Taskmgr.exe"),
}

_start_menu_index = None  # lazily built {lowercased shortcut name: full .lnk path}


def _build_start_menu_index() -> dict:
    """Index every Start Menu shortcut once, so we can open apps we never hard-coded.

    Without this, anything outside APP_MAP ("open whatsapp", "open zoom") just fails,
    which is most of what a user actually asks for.
    """
    index = {}
    roots = [
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
    ]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if filename.lower().endswith((".lnk", ".url")):
                    stem = os.path.splitext(filename)[0].lower()
                    index.setdefault(stem, os.path.join(dirpath, filename))
    return index


# Start Menu folders are full of these; none of them is the app the user meant.
_NOISE_WORDS = (
    "uninstall", "readme", "read me", "help", "documentation", "release notes",
    "reset", "repair", "website", "web site", "manual", "license", "changelog",
)


def find_shortcut(name: str):
    """Best-effort Start Menu lookup: exact name, then prefix, then substring.

    Among several matches the shortest name wins ("VLC media player" over "VLC
    media player - reset preferences"), and support shortcuts are ignored.
    """
    global _start_menu_index
    if _start_menu_index is None:
        try:
            _start_menu_index = _build_start_menu_index()
        except Exception as exc:
            print(f"[actions] start menu scan failed: {exc}")
            _start_menu_index = {}
    if name in _start_menu_index:
        return _start_menu_index[name]

    candidates = [
        (stem, path) for stem, path in _start_menu_index.items()
        if name in stem and not any(word in stem for word in _NOISE_WORDS)
    ]
    if not candidates:
        return None
    # Prefer a shortcut that starts with the spoken name, then the shortest one.
    candidates.sort(key=lambda item: (not item[0].startswith(name), len(item[0])))
    return candidates[0][1]


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
            # Only ever a string from APP_MAP above — never user/LLM text.
            subprocess.Popen(launch, shell=True, creationflags=_NO_WINDOW)
        else:
            shortcut = find_shortcut(name)
            os.startfile(shortcut or name)  # shortcut, else a raw command or file path
        return True, "کھول رہا ہوں۔", f"{name} khol raha hoon."
    except Exception as exc:
        print(f"[actions] open error: {exc}")
        return False, "معاف کیجیے، یہ کھول نہیں پایا۔", f"{name} khol nahi paya."


def _running_image(name: str):
    """Find a running process whose image name matches `name` (for apps not in APP_MAP)."""
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, text=True, creationflags=_NO_WINDOW,
        )
    except Exception:
        return None
    for line in result.stdout.splitlines():
        image = line.split('","')[0].lstrip('"').strip()
        if image and name in image.lower():
            return image
    return None


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
        if _kill(image):
            return True, "بند کر دیا۔", f"{name} band kar diya."
        # Not a process by that name — see if something similar is actually running.
        alternative = _running_image(name)
        if alternative and _kill(alternative):
            return True, "بند کر دیا۔", f"{name} band kar diya."
        return False, "وہ تو چل ہی نہیں رہا تھا۔", f"{name} chal nahi raha tha."
    except Exception as exc:
        print(f"[actions] close error: {exc}")
        return False, "معاف کیجیے، بند نہیں کر پایا۔", f"{name} band nahi kar paya."


def _kill(image: str) -> bool:
    result = subprocess.run(
        ["taskkill", "/F", "/IM", image],
        capture_output=True, text=True, creationflags=_NO_WINDOW,
    )
    return result.returncode == 0


if __name__ == "__main__":
    # Quick manual test: python -m mustafa.actions open notepad
    import sys

    verb = sys.argv[1] if len(sys.argv) > 1 else "open"
    tgt = " ".join(sys.argv[2:]) or "notepad"
    fn = open_target if verb == "open" else close_target
    print(fn(tgt))
