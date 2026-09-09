"""The pieces MUSTAFA's window is built from.

Each widget owns one job and takes its colours from `theme`, so the window file
stays a layout description rather than a pile of painting code.
"""

import html
import math
import random
from datetime import datetime, timezone

from PyQt6 import QtCore, QtGui, QtWidgets

from . import theme as t


# ---------------------------------------------------------------------------
# Backdrop
# ---------------------------------------------------------------------------
class Backdrop(QtWidgets.QWidget):
    """Dark gradient + HUD grid + drifting particles.

    The gradient and grid never change, so they are painted once into a pixmap
    and blitted each frame; only the particles are redrawn. On a CPU that is
    also running speech recognition, that difference is the whole ballgame —
    and the frame rate drops further while the assistant is busy.
    """

    IDLE_INTERVAL = 40   # 25 fps when nothing else needs the CPU
    BUSY_INTERVAL = 90   # ~11 fps while listening / transcribing / speaking

    def __init__(self, parent=None, count=30):
        super().__init__(parent)
        self._particles = [self._spawn(seeded=True) for _ in range(count)]
        self._cache: QtGui.QPixmap | None = None
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self.IDLE_INTERVAL)

    @staticmethod
    def _spawn(seeded=False):
        return {
            "x": random.random(),
            "y": random.random() if seeded else 1.02,
            "r": random.uniform(0.9, 2.4),
            "speed": random.uniform(0.00010, 0.00042),
            "drift": random.uniform(-0.00012, 0.00012),
            "phase": random.uniform(0, math.tau),
        }

    def set_busy(self, busy: bool):
        self._timer.setInterval(self.BUSY_INTERVAL if busy else self.IDLE_INTERVAL)

    def set_animating(self, running: bool):
        """Stop burning CPU while the window is minimised."""
        if running and not self._timer.isActive():
            self._timer.start()
        elif not running and self._timer.isActive():
            self._timer.stop()

    def _tick(self):
        for p in self._particles:
            p["y"] -= p["speed"]
            p["x"] += p["drift"]
            p["phase"] += 0.035
            if p["y"] < -0.02:
                p.update(self._spawn())
        self.update()

    def resizeEvent(self, event):
        self._cache = None
        super().resizeEvent(event)

    def _background(self) -> QtGui.QPixmap:
        if self._cache is not None:
            return self._cache
        ratio = self.devicePixelRatioF()
        pixmap = QtGui.QPixmap(int(self.width() * ratio), int(self.height() * ratio))
        pixmap.setDevicePixelRatio(ratio)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        grad = QtGui.QRadialGradient(w * 0.5, h * 0.34, max(w, h) * 0.85)
        grad.setColorAt(0.0, QtGui.QColor(11, 28, 47))
        grad.setColorAt(0.55, QtGui.QColor(6, 14, 25))
        grad.setColorAt(1.0, QtGui.QColor(t.BG_BASE))
        painter.fillRect(0, 0, w, h, grad)

        painter.setPen(QtGui.QPen(QtGui.QColor(0, 200, 255, 10), 1))
        step = 64
        for x in range(0, w, step):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            painter.drawLine(0, y, w, y)
        painter.end()

        self._cache = pixmap
        return pixmap

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.drawPixmap(0, 0, self._background())
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        w, h = self.width(), self.height()
        for p in self._particles:
            twinkle = 0.5 + 0.5 * math.sin(p["phase"])
            painter.setBrush(QtGui.QColor(0, 210, 255, int(35 + 75 * twinkle)))
            painter.drawEllipse(QtCore.QPointF(p["x"] * w, p["y"] * h), p["r"], p["r"])


# ---------------------------------------------------------------------------
# Orb
# ---------------------------------------------------------------------------
class Orb(QtWidgets.QWidget):
    """The assistant's face: a glowing core that breathes with its state and
    swells with your actual voice level while listening."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        self._state = t.DEFAULT_STATE
        self._phase = 0.0
        self._spin = 0.0
        self._level = 0.0       # smoothed, what we draw
        self._level_target = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_state(self, state: str):
        self._state = state if state in t.STATES else t.DEFAULT_STATE
        if state != "Listening":
            self._level_target = 0.0
        self.update()

    def set_level(self, level: float):
        """0..1 microphone loudness, straight from the recorder."""
        self._level_target = max(0.0, min(1.0, level))

    def _tick(self):
        self._phase += 0.075
        self._spin += 0.010
        # Rise fast, fall slow: matches how a voice actually reads on a meter.
        pull = 0.45 if self._level_target > self._level else 0.12
        self._level += (self._level_target - self._level) * pull
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        color = t.state_color(self._state)
        base = min(w, h) * 0.165

        breathe = {"Idle": 0.035, "Warming up": 0.05, "Listening": 0.06,
                   "Processing": 0.05, "Speaking": 0.10, "Error": 0.03}
        amp = breathe.get(self._state, 0.04)
        radius = base * (1 + amp * math.sin(self._phase) + 0.30 * self._level)

        # Outer reticle: slow dashed ring + four tick marks, the HUD framing.
        reticle = QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), 70), 1.2)
        reticle.setDashPattern([2, 7])
        reticle.setDashOffset(self._spin * 60)
        painter.setPen(reticle)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        ring = base * 2.15
        painter.drawEllipse(QtCore.QPointF(cx, cy), ring, ring)

        painter.setPen(QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), 120), 1.6))
        for i in range(4):
            angle = self._spin + i * math.pi / 2
            x1, y1 = cx + math.cos(angle) * (ring - 8), cy + math.sin(angle) * (ring - 8)
            x2, y2 = cx + math.cos(angle) * (ring + 8), cy + math.sin(angle) * (ring + 8)
            painter.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))

        # Halo: a few translucent discs, cheaper and softer than a blur effect.
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        halo_r = radius * 2.05
        halo = QtGui.QRadialGradient(cx, cy, halo_r)
        inner, mid, edge = QtGui.QColor(color), QtGui.QColor(color), QtGui.QColor(color)
        inner.setAlpha(int(70 + 60 * self._level))
        mid.setAlpha(int(22 + 20 * self._level))
        edge.setAlpha(0)
        halo.setColorAt(radius / halo_r * 0.92, inner)
        halo.setColorAt(0.68, mid)
        halo.setColorAt(1.0, edge)
        painter.setBrush(QtGui.QBrush(halo))
        painter.drawEllipse(QtCore.QPointF(cx, cy), halo_r, halo_r)

        # Core, lit from the upper left so it reads as a sphere, not a circle.
        grad = QtGui.QRadialGradient(cx - radius * 0.32, cy - radius * 0.36, radius * 1.7)
        grad.setColorAt(0.0, color.lighter(150))
        grad.setColorAt(0.42, color)
        grad.setColorAt(1.0, color.darker(260))
        painter.setBrush(QtGui.QBrush(grad))
        painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)

        # Specular highlight.
        painter.setBrush(QtGui.QColor(255, 255, 255, 30))
        painter.drawEllipse(
            QtCore.QPointF(cx - radius * 0.34, cy - radius * 0.40),
            radius * 0.26, radius * 0.18,
        )

        # Working indicator: a sweeping arc, only while it means something.
        if self._state in ("Processing", "Warming up"):
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(color.lighter(165), 3))
            span = radius + 20
            rect = QtCore.QRectF(cx - span, cy - span, span * 2, span * 2)
            painter.drawArc(rect, int(math.degrees(self._phase) % 360) * 16, 100 * 16)


# ---------------------------------------------------------------------------
# Small indicators
# ---------------------------------------------------------------------------
class StatePill(QtWidgets.QWidget):
    """Always-visible status chip: a coloured dot that pulses plus the state name."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = t.DEFAULT_STATE
        self._pulse = 0.0
        self.setFixedHeight(28)
        t.tracked_font(self, t.SIZE_LABEL, weight=700, spacing=1.4, mono=True)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)

    def set_state(self, state: str):
        self._state = state if state in t.STATES else t.DEFAULT_STATE
        self.updateGeometry()
        self.update()

    def _tick(self):
        self._pulse += 0.12
        self.update()

    def _label(self) -> str:
        return t.state(self._state)[1]

    def sizeHint(self):
        width = self.fontMetrics().horizontalAdvance(self._label()) + 46
        return QtCore.QSize(width, 28)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        color = t.state_color(self._state)
        rect = QtCore.QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)

        painter.setPen(QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), 90), 1))
        painter.setBrush(QtGui.QColor(color.red(), color.green(), color.blue(), 26))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        glow = 0.55 + 0.45 * math.sin(self._pulse)
        cx, cy = 16.0, self.height() / 2
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(color.red(), color.green(), color.blue(), int(70 * glow)))
        painter.drawEllipse(QtCore.QPointF(cx, cy), 7, 7)
        painter.setBrush(color)
        painter.drawEllipse(QtCore.QPointF(cx, cy), 3.4, 3.4)

        painter.setPen(QtGui.QColor(t.TEXT_PRIMARY))
        painter.drawText(
            QtCore.QRectF(28, 0, self.width() - 36, self.height()),
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            self._label(),
        )


class LevelMeter(QtWidgets.QWidget):
    """Thin bar that shows the microphone actually hearing you.

    Without it, a failed capture and a silent room look identical — which is
    exactly the confusion this app had.
    """

    BARS = 21

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setFixedWidth(272)
        self._level = 0.0
        self._target = 0.0
        self._active = False
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._timer.start(40)
        else:
            self._timer.stop()
            self._level = self._target = 0.0
        self.update()

    def set_level(self, level: float):
        self._target = max(0.0, min(1.0, level))

    def _tick(self):
        pull = 0.5 if self._target > self._level else 0.14
        self._level += (self._target - self._level) * pull
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        color = t.state_color("Listening")
        w, h = self.width(), self.height()
        gap = 5
        bar_w = max(3.0, (w - gap * (self.BARS - 1)) / self.BARS)
        lit = self._level * self.BARS

        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        for i in range(self.BARS):
            # Tallest in the middle: reads as a voice, not a progress bar.
            shape = math.sin(math.pi * (i + 0.5) / self.BARS) ** 0.7
            bar_h = max(3.0, h * (0.22 + 0.78 * shape * min(1.0, self._level * 1.15)))
            on = i < lit
            alpha = 225 if on and self._active else 12  # inert track stays out of the way
            painter.setBrush(QtGui.QColor(color.red(), color.green(), color.blue(), alpha))
            x = i * (bar_w + gap)
            painter.drawRoundedRect(QtCore.QRectF(x, (h - bar_h) / 2, bar_w, bar_h), 2.0, 2.0)


class WindowButton(QtWidgets.QAbstractButton):
    """Minimise / maximise / close, drawn rather than typed.

    Glyph characters for these render differently on every Windows font (and the
    emoji ones come out as coloured blobs), so the shapes are painted directly.
    """

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._hover = False
        self.setFixedSize(34, 30)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolTip({"min": "Minimise", "max": "Maximise / restore",
                         "close": "Close"}[kind])

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        danger = self._kind == "close"

        if self._hover:
            tint = QtGui.QColor(255, 92, 92, 55) if danger else QtGui.QColor(0, 208, 255, 32)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(tint)
            painter.drawRoundedRect(QtCore.QRectF(0, 0, self.width(), self.height()),
                                    t.RADIUS_SM, t.RADIUS_SM)

        ink = QtGui.QColor("#ffd7d7" if danger and self._hover else
                           t.TEXT_PRIMARY if self._hover else t.TEXT_SECONDARY)
        painter.setPen(QtGui.QPen(ink, 1.4))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        cx, cy, r = self.width() / 2, self.height() / 2, 4.5

        if self._kind == "min":
            painter.drawLine(QtCore.QPointF(cx - r, cy), QtCore.QPointF(cx + r, cy))
        elif self._kind == "max":
            painter.drawRoundedRect(QtCore.QRectF(cx - r, cy - r, r * 2, r * 2), 1.5, 1.5)
        else:
            painter.drawLine(QtCore.QPointF(cx - r, cy - r), QtCore.QPointF(cx + r, cy + r))
            painter.drawLine(QtCore.QPointF(cx + r, cy - r), QtCore.QPointF(cx - r, cy + r))


class BrandMark(QtWidgets.QWidget):
    """Tiny orb glyph next to the wordmark — the app's identity in 26 pixels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(26, 26)
        self._state = t.DEFAULT_STATE

    def set_state(self, state: str):
        self._state = state if state in t.STATES else t.DEFAULT_STATE
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        color = t.state_color(self._state)
        c = QtCore.QPointF(13, 13)
        painter.setPen(QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), 110), 1.4))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawEllipse(c, 11, 11)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(color.red(), color.green(), color.blue(), 60))
        painter.drawEllipse(c, 7, 7)
        painter.setBrush(color)
        painter.drawEllipse(c, 4, 4)


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------
def _local_time(ts_iso: str | None) -> str:
    if not ts_iso:
        return datetime.now().strftime("%H:%M")
    try:
        parsed = datetime.fromisoformat(ts_iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone().strftime("%H:%M")
    except ValueError:
        return ""


class Bubble(QtWidgets.QFrame):
    """One message. The user's sit right and tinted, Mustafa's left and glassy —
    so the thread is readable at a glance without reading the names."""

    MIN_WIDTH = 190
    MAX_WIDTH = 440

    def __init__(self, role: str, text: str, ts: str | None = None, parent=None):
        super().__init__(parent)
        mine = role == "user"
        accent = t.ACCENT if mine else t.state_color("Speaking").name()

        # Scope the frame styling to this object: QLabel inherits QFrame, so an
        # unscoped "QFrame { border: ... }" would draw a box around every line
        # of text inside the bubble too.
        self.setObjectName("bubble")
        self.setStyleSheet(
            f"QFrame#bubble {{ background: {t.rgba(accent, 20) if mine else t.BG_RAISED};"
            f" border: 1px solid {t.rgba(accent, 42 if mine else 28)};"
            f" border-radius: {t.RADIUS_MD}px; }}"
            f"QFrame#bubble QLabel {{ background: transparent; border: none; }}"
        )
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(t.S4, t.S3, t.S4, t.S3)
        box.setSpacing(t.S1)

        header = QtWidgets.QLabel(
            f'<span style="color:{accent}">{"AAP" if mine else "MUSTAFA"}</span>'
            f'<span style="color:{t.TEXT_MUTED}">  ·  {_local_time(ts)}</span>'
        )
        header.setStyleSheet("background: transparent; border: none;")
        t.tracked_font(header, t.SIZE_MICRO, weight=700, spacing=1.2, mono=True)

        body = QtWidgets.QLabel(html.escape(text or "…").replace("\n", "<br>"))
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {t.TEXT_PRIMARY}; background: transparent; border: none;")
        body.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)

        box.addWidget(header)
        box.addWidget(body)

        # A word-wrapped QLabel reports a tiny width hint, which inside a stretched
        # row collapses the bubble to a three-word column. Measure the text and let
        # the bubble hug it, up to a comfortable reading measure.
        metrics = QtGui.QFontMetrics(body.font())
        text_width = metrics.horizontalAdvance(body.text().replace("<br>", " "))
        self.ideal_width = int(min(self.MAX_WIDTH, max(self.MIN_WIDTH, text_width + 2 * t.S4 + 10)))
        self.setFixedWidth(self.ideal_width)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,
                           QtWidgets.QSizePolicy.Policy.Minimum)

    def fit(self, available: int):
        """Shrink to fit a narrower pane; never grow past the reading measure."""
        self.setFixedWidth(max(self.MIN_WIDTH // 2, min(self.ideal_width, available)))


class EmptyState(QtWidgets.QWidget):
    """First-run panel: says what the app can do, in the user's own words, and
    lets them try one without touching the microphone."""

    suggestion = QtCore.pyqtSignal(str)

    EXAMPLES = [
        "notepad kholo",
        "chrome band karo",
        "calculator chalao",
        "Pakistan ka capital kya hai?",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(0, t.S5, 0, 0)
        box.setSpacing(t.S3)

        title = QtWidgets.QLabel("Shuru kijiye")
        title.setStyleSheet(f"color: {t.TEXT_PRIMARY}; background: transparent;")
        t.tracked_font(title, t.SIZE_LEAD, weight=700)

        hint = QtWidgets.QLabel(
            "Bol kar ya likh kar hukum dijiye — app kholna, band karna, ya koi bhi sawal."
        )
        hint.setObjectName("caption")
        hint.setWordWrap(True)

        box.addWidget(title)
        box.addWidget(hint)
        box.addSpacing(t.S2)

        for example in self.EXAMPLES:
            button = QtWidgets.QPushButton(example)
            button.setObjectName("chip")
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(34)
            button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum,
                                 QtWidgets.QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _=False, text=example: self.suggestion.emit(text))
            # Wrapped in a row so each chip is only as wide as its own text.
            row = QtWidgets.QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(button)
            row.addStretch(1)
            box.addLayout(row)
        box.addStretch(1)


class ConversationView(QtWidgets.QScrollArea):
    """Scrolling message thread with an empty state and sticky auto-scroll."""

    suggestion = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QtWidgets.QWidget()
        self._box = QtWidgets.QVBoxLayout(container)
        self._box.setContentsMargins(0, 0, t.S2, 0)
        self._box.setSpacing(t.S3)

        self._empty = EmptyState()
        self._empty.suggestion.connect(self.suggestion)
        self._box.addWidget(self._empty)
        self._box.addStretch(1)
        self.setWidget(container)
        self._count = 0
        self._bubbles: list[Bubble] = []

    def count(self) -> int:
        return self._count

    def append(self, role: str, text: str, ts: str | None = None):
        if self._empty.isVisible():
            self._empty.hide()

        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        bubble = Bubble(role, text, ts)
        bubble.fit(self._available_width())
        self._bubbles.append(bubble)
        if role == "user":
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)

        holder = QtWidgets.QWidget()
        holder.setLayout(row)
        self._box.insertWidget(self._box.count() - 1, holder)
        self._count += 1
        # Let the layout settle before scrolling, or we land one message short.
        QtCore.QTimer.singleShot(0, self._scroll_to_end)

    def clear(self):
        self._bubbles.clear()
        while self._box.count() > 2:  # keep the empty state and the stretch
            item = self._box.takeAt(1)
            widget = item.widget()
            if widget:
                widget.setParent(None)   # gone now, not whenever Qt gets round to it
                widget.deleteLater()
        self._count = 0
        self._empty.show()

    # On a wide screen an unconstrained thread scatters bubbles against the far
    # edges with a dead gutter down the middle. Cap the column and centre it, the
    # way any readable message view does.
    CONTENT_WIDTH = 780

    def _available_width(self) -> int:
        return max(160, min(self.viewport().width(), self.CONTENT_WIDTH) - t.S5)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        pad = max(0, (self.viewport().width() - self.CONTENT_WIDTH) // 2)
        self._box.setContentsMargins(pad, 0, pad + t.S2, 0)
        available = self._available_width()
        for bubble in self._bubbles:
            bubble.fit(available)

    def _scroll_to_end(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())
