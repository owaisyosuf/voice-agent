"""Action engine: open and close Windows applications."""

import os
import subprocess
import sys
import time

# Keep console windows from flashing up when we shell out.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# How long an app gets to shut down on its own before we report back.
_CLOSE_GRACE_SECONDS = 3.0

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


_shortcut_images = {}  # spoken name -> process image name (None when unresolvable)


def _shortcut_target_image(name: str):
    """Resolve a Start Menu shortcut to the executable it actually launches.

    "registry editor" -> regedit.exe, "snipping tool" -> SnippingTool.exe. Guessing
    "<spoken name>.exe" instead is wrong for every app whose executable is named
    differently from its Start Menu entry, which is most of the interesting ones.
    """
    if name in _shortcut_images:
        return _shortcut_images[name]

    image = None
    shortcut = find_shortcut(name)
    if shortcut and shortcut.lower().endswith(".lnk"):
        try:
            import pythoncom
            import win32com.client
        except ImportError as exc:
            print(f"[actions] shortcut resolve unavailable: {exc}")
            return None

        # We run on a Qt worker thread, so COM needs starting here — same dance as
        # the SAPI voice in tts.py.
        com_initialized = False
        try:
            pythoncom.CoInitialize()
            com_initialized = True
        except Exception:
            pass  # already initialized on this thread — leave its ownership alone
        shell = None
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            target = shell.CreateShortcut(shortcut).TargetPath
            if target and target.lower().endswith(".exe"):
                image = os.path.basename(target)
        except Exception as exc:
            print(f"[actions] shortcut resolve failed for {name}: {exc}")
        finally:
            shell = None  # release it before COM goes away, or pywin32 warns on exit
            if com_initialized:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    _shortcut_images[name] = image
    return image


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
    """Last-resort match of `name` against the running processes.

    Compares both directions with spaces removed, so "snipping tool" still finds
    SnippingTool.exe. Never returns the image we are ourselves running as — otherwise
    "python band karo" would kill Mustafa.
    """
    compact = name.replace(" ", "")
    if len(compact) < 3:  # too short to match on without hitting something unrelated
        return None
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, text=True, creationflags=_NO_WINDOW,
        )
    except Exception:
        return None

    own = os.path.basename(sys.executable).lower()
    partial = None
    for line in result.stdout.splitlines():
        image = line.split('","')[0].lstrip('"').strip()
        if not image or image.lower() == own:
            continue
        stem = os.path.splitext(image)[0].lower()
        if stem == compact:
            return image
        if len(stem) >= 3 and not partial and (compact in stem or stem in compact):
            partial = image
    return partial


def close_target(name: str):
    """Terminate an app by name. Returns (ok: bool, speak_message: str, display_message: str).

    `speak_message` is Urdu script (correct TTS accent); `display_message` is the same
    thing in Roman Urdu, for on-screen text.
    """
    name = (name or "").strip().lower()
    if not name:
        return False, "کیا بند کرنا ہے سمجھ نہیں آیا۔", "Kya band karna hai samajh nahi aaya."

    try:
        for image in _close_candidates(name):
            status = _kill(image)
            if status == "closed":
                return True, "بند کر دیا۔", f"{name} band kar diya."
            if status == "pending":
                # It took the request and stayed up: it is asking the user something,
                # almost always "save changes?". Say so instead of forcing it shut.
                return (
                    False,
                    "میں نے بند کرنے کو کہا ہے، وہ آپ سے محفوظ کرنے کا پوچھ رہا ہے۔",
                    f"{name} band karne ko kaha hai — woh aap se save karne ka pooch raha hai.",
                )
            if status == "denied":
                return (
                    False,
                    "یہ منتظم کے اختیار سے چل رہا ہے، میں اسے بند نہیں کر سکتا۔",
                    f"{name} admin ke ikhtiyar se chal raha hai — main isay band nahi kar sakta.",
                )
        return False, "وہ تو چل ہی نہیں رہا تھا۔", f"{name} chal nahi raha tha."
    except Exception as exc:
        print(f"[actions] close error: {exc}")
        return False, "معاف کیجیے، بند نہیں کر پایا۔", f"{name} band nahi kar paya."


def _close_candidates(name: str):
    """Process images worth trying, deterministic sources first and guesswork last.

    A generator, so the lookups that cost a subprocess only run once the cheap ones
    have missed.
    """
    seen = set()

    def unseen(image):
        if image and image.lower() not in seen:
            seen.add(image.lower())
            return True
        return False

    mapped = APP_MAP.get(name, (None, None))[1]
    if unseen(mapped):
        yield mapped

    resolved = _shortcut_target_image(name)
    if unseen(resolved):
        yield resolved

    guess = name if name.endswith(".exe") else name + ".exe"
    if unseen(guess):
        yield guess

    fuzzy = _running_image(name)
    if unseen(fuzzy):
        yield fuzzy


def _kill(image: str) -> str:
    """Ask an app to close. Returns "closed", "pending", "denied" or "absent".

    taskkill without /F sends a close request the app can act on, so an editor raises
    its "save changes?" prompt rather than losing the work. It reports success as soon
    as that request is delivered, so the exit has to be confirmed separately.
    """
    requested = subprocess.run(
        ["taskkill", "/IM", image],
        capture_output=True, text=True, creationflags=_NO_WINDOW,
    )
    if requested.returncode != 0:
        # An elevated app (regedit, Task Manager) cannot be touched from an
        # unelevated one — worth saying out loud, since it is not the same thing
        # as the app not running.
        return "denied" if _access_denied(requested) else "absent"

    deadline = time.monotonic() + _CLOSE_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not _is_running(image):
            return "closed"
        time.sleep(0.25)

    # Still up. An app that owns a window is showing the user something and gets left
    # alone; one that owns none never received the request in the first place, so
    # forcing it costs nothing.
    if _owns_window(image):
        return "pending"
    forced = subprocess.run(
        ["taskkill", "/F", "/IM", image],
        capture_output=True, text=True, creationflags=_NO_WINDOW,
    )
    if forced.returncode == 0:
        return "closed"
    return "denied" if _access_denied(forced) else "pending"


def _access_denied(result) -> bool:
    return "denied" in (result.stdout + result.stderr).lower()


def _owns_window(image: str) -> bool:
    """Whether the app has a real, visible window to prompt the user with.

    Store apps have none — their frame belongs to ApplicationFrameHost — so a polite
    close request has nowhere to land and they would otherwise never shut down. Their
    processes do own hidden helper windows ("XCP", "CicMarshalWnd"), so this has to
    test visibility rather than mere existence.
    """
    pids = _pids_for(image)
    if not pids:
        return False
    try:
        import win32gui
        import win32process
    except ImportError as exc:
        print(f"[actions] window check unavailable: {exc}")
        return True  # can't tell whether anyone is being prompted — never force blindly

    visible = []

    def visit(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in pids:
                    visible.append(hwnd)
        except Exception:
            pass  # a window can die mid-enumeration; it just isn't one we care about
        return True

    try:
        win32gui.EnumWindows(visit, None)
    except Exception as exc:
        print(f"[actions] window scan failed for {image}: {exc}")
        return True
    return bool(visible)


def _pids_for(image: str) -> set:
    result = subprocess.run(
        ["tasklist", "/fi", f"imagename eq {image}", "/fo", "csv", "/nh"],
        capture_output=True, text=True, creationflags=_NO_WINDOW,
    )
    pids = set()
    for line in result.stdout.splitlines():
        fields = line.strip().strip('"').split('","')
        if len(fields) >= 2 and fields[1].isdigit():
            pids.add(int(fields[1]))
    return pids


def _is_running(image: str) -> bool:
    return bool(_pids_for(image))


if __name__ == "__main__":
    # Quick manual test: python -m mustafa.actions open notepad
    verb = sys.argv[1] if len(sys.argv) > 1 else "open"
    tgt = " ".join(sys.argv[2:]) or "notepad"
    fn = open_target if verb == "open" else close_target
    print(fn(tgt))
