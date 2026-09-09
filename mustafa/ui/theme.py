"""Design tokens for MUSTAFA's interface — one source of truth for colour,
type, spacing and state.

Every widget pulls from here instead of inlining its own hex codes, so the whole
app can be re-skinned (or a light theme added) by editing this file alone. The
scales below are deliberately small: a handful of steps used consistently reads
as designed, while a dozen one-off values reads as accidental.
"""

from PyQt6 import QtGui

# --- Surfaces ---------------------------------------------------------------
# Four depths only: the page, a panel, a raised control, and an inset field.
BG_BASE = "#04080f"
BG_PANEL = "#0a1420"
BG_RAISED = "#0f1d2c"
BG_INSET = "#081320"

# --- Lines ------------------------------------------------------------------
LINE_SUBTLE = "rgba(126, 190, 232, 28)"   # panel edges
LINE_STRONG = "rgba(0, 208, 255, 90)"     # focused / active edges

# --- Text -------------------------------------------------------------------
TEXT_PRIMARY = "#e4f2ff"
TEXT_SECONDARY = "#93b0c8"
TEXT_MUTED = "#5c7a95"
TEXT_ON_ACCENT = "#02121b"

# --- Accent -----------------------------------------------------------------
ACCENT = "#00d0ff"
ACCENT_SOFT = "rgba(0, 208, 255, 38)"

# --- Assistant states -------------------------------------------------------
# colour, headline, and the one line of guidance the user actually needs while
# the app is in that state. Wording is Roman Urdu because that is how the
# primary user speaks to it.
STATES = {
    "Warming up": ("#ffb03c", "WARMING UP", "Models load ho rahe hain, ek lamha…"),
    "Idle":       ("#3b9eff", "READY",      "Listen dabaiye ya neeche likh kar bhejiye"),
    "Listening":  ("#00e5ff", "LISTENING",  "Boliye — beep ke baad sun raha hoon"),
    "Processing": ("#a855f7", "THINKING",   "Aap ki baat samajh raha hoon…"),
    "Speaking":   ("#22e39a", "SPEAKING",   "Jawab de raha hoon"),
    "Error":      ("#ff5c5c", "ERROR",      "Kuch masla hua — tafseel neeche hai"),
}
DEFAULT_STATE = "Idle"


def state(name: str):
    return STATES.get(name, STATES[DEFAULT_STATE])


def state_color(name: str) -> QtGui.QColor:
    return QtGui.QColor(state(name)[0])


def rgba(color: QtGui.QColor | str, alpha: int) -> str:
    """A QSS rgba() string from a colour plus 0-255 alpha."""
    c = QtGui.QColor(color) if isinstance(color, str) else color
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


# --- Type -------------------------------------------------------------------
FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"

# Six sizes, each with a job. Anything outside this list is a mistake.
SIZE_MICRO = 10   # meta: timestamps, footer
SIZE_LABEL = 11   # small-caps section labels
SIZE_BODY = 13    # chat text, inputs
SIZE_LEAD = 15    # the live caption under the orb
SIZE_TITLE = 20   # state headline
SIZE_BRAND = 22   # wordmark


def tracked_font(widget, size: int, weight: int = 600, spacing: float = 0.0,
                 mono: bool = False) -> None:
    """Apply a font with real letter-spacing.

    Qt style sheets silently ignore `letter-spacing`, so the wide-tracked HUD
    labels this design leans on have to be set through QFont.
    """
    font = QtGui.QFont(FONT_MONO if mono else FONT_UI, size)
    font.setWeight(QtGui.QFont.Weight(weight))
    if spacing:
        font.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, spacing)
    widget.setFont(font)


# --- Space ------------------------------------------------------------------
# 4-point rhythm. Gaps between things come from this list, nowhere else.
S1, S2, S3, S4, S5, S6 = 4, 8, 12, 16, 24, 32

RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 18
RADIUS_PILL = 999


def stylesheet() -> str:
    """Global QSS. Set once on the window; every child inherits it."""
    return f"""
    QWidget {{
        color: {TEXT_PRIMARY};
        font-family: "{FONT_UI}";
        font-size: {SIZE_BODY}px;
    }}

    /* --- panels --- */
    QFrame#panel {{
        background: {BG_PANEL};
        border: 1px solid {LINE_SUBTLE};
        border-radius: {RADIUS_LG}px;
    }}
    QWidget#stage {{ background: transparent; }}

    /* --- section labels --- */
    QLabel#sectionLabel {{ color: {TEXT_MUTED}; background: transparent; }}
    QLabel#caption     {{ color: {TEXT_SECONDARY}; background: transparent; }}
    QLabel#meta        {{ color: {TEXT_MUTED}; background: transparent; }}

    /* --- composer --- */
    QLineEdit#composer {{
        background: {BG_INSET};
        border: 1px solid {LINE_SUBTLE};
        border-radius: {RADIUS_PILL}px;
        padding: 0 {S5}px;
        selection-background-color: {ACCENT_SOFT};
    }}
    QLineEdit#composer:focus {{ border: 1px solid {LINE_STRONG}; background: #0a1826; }}
    QLineEdit#composer:disabled {{ color: {TEXT_MUTED}; }}

    /* --- buttons --- */
    QPushButton#primary {{
        background: {ACCENT};
        color: {TEXT_ON_ACCENT};
        border: none;
        border-radius: {RADIUS_PILL}px;
        padding: 0 {S5}px;
        font-weight: 700;
    }}
    QPushButton#primary:hover {{ background: #4ce0ff; }}
    QPushButton#primary:pressed {{ background: #00a8cf; }}
    QPushButton#primary:disabled {{ background: {rgba(ACCENT, 45)}; color: {TEXT_MUTED}; }}

    QPushButton#ghost {{
        background: transparent;
        color: {TEXT_SECONDARY};
        border: 1px solid {LINE_SUBTLE};
        border-radius: {RADIUS_PILL}px;
        padding: 0 {S4}px;
    }}
    QPushButton#ghost:hover {{ color: {TEXT_PRIMARY}; border-color: {LINE_STRONG}; }}
    QPushButton#ghost:pressed {{ background: {rgba(ACCENT, 22)}; }}
    QPushButton#ghost:disabled {{ color: {TEXT_MUTED}; border-color: {LINE_SUBTLE}; }}

    QPushButton#danger {{
        background: {rgba(STATES["Error"][0], 30)};
        color: {STATES["Error"][0]};
        border: 1px solid {rgba(STATES["Error"][0], 120)};
        border-radius: {RADIUS_PILL}px;
        padding: 0 {S4}px;
        font-weight: 700;
    }}
    QPushButton#danger:hover {{
        background: {rgba(STATES["Error"][0], 60)}; color: #ffd7d7;
    }}
    QPushButton#danger:pressed {{ background: {rgba(STATES["Error"][0], 90)}; }}

    QPushButton#window {{
        background: transparent; color: {TEXT_SECONDARY};
        border: none; border-radius: {RADIUS_SM}px;
    }}
    QPushButton#window:hover {{ background: {rgba(ACCENT, 28)}; color: {TEXT_PRIMARY}; }}
    QPushButton#windowClose:hover {{ background: rgba(255, 92, 92, 55); color: #ffd7d7; }}

    QPushButton#chip {{
        background: {rgba(ACCENT, 16)};
        color: {TEXT_SECONDARY};
        border: 1px solid {LINE_SUBTLE};
        border-radius: {RADIUS_PILL}px;
        padding: {S2}px {S4}px;
        text-align: left;
    }}
    QPushButton#chip:hover {{ color: {TEXT_PRIMARY}; border-color: {LINE_STRONG}; }}

    /* --- conversation scroller --- */
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 8px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {rgba(ACCENT, 55)}; border-radius: 4px; min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {rgba(ACCENT, 110)}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

    QSplitter::handle {{ background: transparent; }}

    QToolTip {{
        background: {BG_RAISED}; color: {TEXT_PRIMARY};
        border: 1px solid {LINE_SUBTLE}; padding: {S2}px {S3}px;
    }}
    """
