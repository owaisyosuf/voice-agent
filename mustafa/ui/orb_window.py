"""PyQt6 fullscreen HUD: an animated, state-reactive orb over a live particle
backdrop, with a persistent chat log docked at the bottom — MUSTAFA's face.
"""

import html
import math
import random

from PyQt6 import QtCore, QtGui, QtWidgets

STATE_COLORS = {
    "Idle": QtGui.QColor(0, 150, 255),
    "Listening": QtGui.QColor(0, 220, 255),
    "Processing": QtGui.QColor(160, 80, 255),
    "Speaking": QtGui.QColor(0, 255, 180),
    "Error": QtGui.QColor(255, 60, 60),
}

STATE_AMPLITUDE = {
    "Idle": 0.05,
    "Listening": 0.16,
    "Processing": 0.10,
    "Speaking": 0.14,
    "Error": 0.08,
}

ACCENT = "#00d0ff"


class ParticleField(QtWidgets.QWidget):
    """Dark gradient + faint HUD grid + slowly drifting glow particles — the backdrop
    every other widget sits on top of."""

    def __init__(self, parent=None, count=55):
        super().__init__(parent)
        self._particles = [
            {
                "x": random.random(),
                "y": random.random(),
                "r": random.uniform(1.0, 2.6),
                "speed": random.uniform(0.00012, 0.0005),
                "drift": random.uniform(-0.00015, 0.00015),
                "phase": random.uniform(0, math.tau),
            }
            for _ in range(count)
        ]
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _tick(self):
        for p in self._particles:
            p["y"] -= p["speed"]
            p["x"] += p["drift"]
            p["phase"] += 0.03
            if p["y"] < -0.02:
                p["y"] = 1.02
                p["x"] = random.random()
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        grad = QtGui.QRadialGradient(w * 0.5, h * 0.32, max(w, h) * 0.9)
        grad.setColorAt(0.0, QtGui.QColor(9, 24, 42))
        grad.setColorAt(0.55, QtGui.QColor(5, 12, 22))
        grad.setColorAt(1.0, QtGui.QColor(2, 5, 9))
        painter.fillRect(self.rect(), grad)

        grid_pen = QtGui.QPen(QtGui.QColor(0, 200, 255, 12))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        step = 56
        for x in range(0, w, step):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            painter.drawLine(0, y, w, y)

        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        for p in self._particles:
            twinkle = 0.5 + 0.5 * math.sin(p["phase"])
            alpha = int(50 + 90 * twinkle)
            painter.setBrush(QtGui.QColor(0, 210, 255, alpha))
            r = p["r"]
            painter.drawEllipse(QtCore.QPointF(p["x"] * w, p["y"] * h), r, r)


class Orb(QtWidgets.QWidget):
    """Custom-painted glowing orb that pulses/spins based on state, with a slow
    always-on HUD reticle ring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 240)
        self.setMaximumSize(460, 460)
        self._phase = 0.0
        self._ring_phase = 0.0
        self._state = "Idle"
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_state(self, state: str):
        self._state = state if state in STATE_COLORS else "Idle"
        self.update()

    def _tick(self):
        self._phase += 0.08
        self._ring_phase += 0.012
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        base = min(w, h) * 0.26
        color = STATE_COLORS.get(self._state, STATE_COLORS["Idle"])
        amp = STATE_AMPLITUDE.get(self._state, 0.05)
        radius = base * (1 + amp * math.sin(self._phase))

        # outer HUD reticle: slow-rotating dashed ring
        reticle_pen = QtGui.QPen(QtGui.QColor(color.red(), color.green(), color.blue(), 90), 1.5)
        reticle_pen.setDashPattern([2, 6])
        reticle_pen.setDashOffset(self._ring_phase * 40)
        painter.setPen(reticle_pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        ring_r = radius + 34
        painter.drawEllipse(QtCore.QPointF(cx, cy), ring_r, ring_r)

        # outer glow rings
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        for i in range(4, 0, -1):
            glow = QtGui.QColor(color.red(), color.green(), color.blue(), int(28 * i / 4))
            painter.setBrush(glow)
            rr = radius + i * 14
            painter.drawEllipse(QtCore.QPointF(cx, cy), rr, rr)

        # core sphere
        grad = QtGui.QRadialGradient(cx, cy, radius)
        grad.setColorAt(0.0, color.lighter(160))
        grad.setColorAt(1.0, color)
        painter.setBrush(QtGui.QBrush(grad))
        painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)

        # spinner arc while processing
        if self._state == "Processing":
            pen = QtGui.QPen(color.lighter(180), 4)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            rect = QtCore.QRectF(
                cx - radius - 12, cy - radius - 12,
                2 * (radius + 12), 2 * (radius + 12),
            )
            start = int(math.degrees(self._phase)) % 360
            painter.drawArc(rect, start * 16, 90 * 16)


def _glow(widget, color=ACCENT, radius=22):
    effect = QtWidgets.QGraphicsDropShadowEffect(widget)
    effect.setColor(QtGui.QColor(color))
    effect.setBlurRadius(radius)
    effect.setOffset(0, 0)
    widget.setGraphicsEffect(effect)


GLASS_PANEL = (
    "background: rgba(10,22,38,150); border:1px solid rgba(0,210,255,70);"
    " border-radius:14px;"
)


class DragHeader(QtWidgets.QWidget):
    """Lets the frameless window be dragged by clicking its header bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_offset = None

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MUSTAFA")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.FramelessWindowHint)
        self._maximized = False
        self._build()

    def showFilled(self):
        """Fill the screen's work area (leaves the taskbar visible) and show."""
        self.setGeometry(QtWidgets.QApplication.primaryScreen().availableGeometry())
        self._maximized = True
        self.show()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def _toggle_maximize(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if self._maximized:
            avail = screen.availableGeometry()
            w, h = 560, 760
            x = avail.x() + (avail.width() - w) // 2
            y = avail.y() + (avail.height() - h) // 2
            self.setGeometry(x, y, w, h)
            self._maximized = False
            self._maximize_btn.setText("⛶")
        else:
            self.setGeometry(screen.availableGeometry())
            self._maximized = True
            self._maximize_btn.setText("🗗")

    def _build(self):
        central = ParticleField()
        self.setCentralWidget(central)

        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(36, 24, 36, 28)
        root.setSpacing(18)

        # --- header: brand + window controls (drag this bar to move the window) ---
        header_widget = DragHeader()
        header = QtWidgets.QHBoxLayout(header_widget)
        header.setContentsMargins(0, 0, 0, 0)
        title = QtWidgets.QLabel("M U S T A F A")
        title.setStyleSheet(
            f"color:{ACCENT}; font-size:26px; font-weight:bold; letter-spacing:8px;"
            " background:transparent;"
        )
        _glow(title, ACCENT, 28)

        subtitle = QtWidgets.QLabel("VOICE-CONTROLLED SYSTEM AGENT")
        subtitle.setStyleSheet(
            "color:rgba(150,200,230,160); font-size:11px; letter-spacing:4px;"
            " font-family:Consolas; background:transparent;"
        )

        brand_col = QtWidgets.QVBoxLayout()
        brand_col.setSpacing(2)
        brand_col.addWidget(title)
        brand_col.addWidget(subtitle)

        def window_btn(symbol, fg="#8fd6ff", border="rgba(0,210,255,140)"):
            btn = QtWidgets.QPushButton(symbol)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(36, 36)
            btn.setStyleSheet(
                f"QPushButton{{background:rgba(10,40,55,90); color:{fg};"
                f" border:1px solid {border}; border-radius:18px; font-size:13px;}}"
                f"QPushButton:hover{{background:rgba(15,58,79,160);}}"
            )
            return btn

        minimize_btn = window_btn("─")
        minimize_btn.clicked.connect(self.showMinimized)

        self._maximize_btn = window_btn("⛶")
        self._maximize_btn.clicked.connect(self._toggle_maximize)

        close_btn = window_btn("✕", fg="#ff6b6b", border="rgba(255,90,90,140)")
        close_btn.clicked.connect(self.close)

        window_btns = QtWidgets.QHBoxLayout()
        window_btns.setSpacing(8)
        window_btns.addWidget(minimize_btn)
        window_btns.addWidget(self._maximize_btn)
        window_btns.addWidget(close_btn)

        header.addLayout(brand_col)
        header.addStretch(1)
        header.addLayout(window_btns)
        root.addWidget(header_widget)

        # --- center: orb + status + last line ---
        center = QtWidgets.QVBoxLayout()
        center.setSpacing(14)

        orb_row = QtWidgets.QHBoxLayout()
        self.orb = Orb()
        orb_row.addStretch(1)
        orb_row.addWidget(self.orb)
        orb_row.addStretch(1)

        self.status = QtWidgets.QLabel("IDLE")
        self.status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(
            f"color:{ACCENT}; font-size:15px; font-weight:bold; letter-spacing:5px;"
            " font-family:Consolas; background:transparent;"
        )

        self.transcript = QtWidgets.QLabel("Type a command below, or click Listen")
        self.transcript.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.transcript.setWordWrap(True)
        self.transcript.setMaximumWidth(720)
        self.transcript.setStyleSheet(
            "color:#8fd6ff; font-size:14px; background:transparent;"
        )
        transcript_row = QtWidgets.QHBoxLayout()
        transcript_row.addStretch(1)
        transcript_row.addWidget(self.transcript)
        transcript_row.addStretch(1)

        center.addLayout(orb_row, 1)
        center.addWidget(self.status)
        center.addLayout(transcript_row)
        root.addLayout(center, 3)

        # --- input row ---
        self.input_box = QtWidgets.QLineEdit()
        self.input_box.setPlaceholderText(
            "e.g.  open notepad   /   notepad kholo   /   close chrome   /   ask me anything"
        )
        self.input_box.setClearButtonEnabled(True)
        self.input_box.setFixedHeight(46)
        self.input_box.setStyleSheet(
            "QLineEdit{background:rgba(10,22,32,170); color:#d0f0ff;"
            " border:1px solid rgba(30,90,117,200); border-radius:20px; padding:0 18px;"
            " font-size:14px;}"
            f"QLineEdit:focus{{border:1px solid {ACCENT};}}"
        )

        self.listen_btn = QtWidgets.QPushButton("🎤  LISTEN")
        self.listen_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.listen_btn.setFixedHeight(46)
        self.listen_btn.setStyleSheet(
            f"QPushButton{{background:rgba(10,42,58,190); color:{ACCENT};"
            f" border:1px solid {ACCENT}; border-radius:20px; padding:0 26px;"
            " font-size:13px; font-weight:bold; letter-spacing:1px;}}"
            "QPushButton:hover{background:rgba(15,58,79,220);}"
        )
        _glow(self.listen_btn, ACCENT, 18)

        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(12)
        input_row.addWidget(self.input_box, 1)
        input_row.addWidget(self.listen_btn)
        root.addLayout(input_row)

        # --- persistent chat log, docked at the bottom ---
        chat_panel = QtWidgets.QWidget()
        chat_panel.setStyleSheet(f"QWidget{{{GLASS_PANEL}}}")
        chat_layout = QtWidgets.QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(18, 12, 18, 14)
        chat_layout.setSpacing(6)

        chat_header = QtWidgets.QLabel("TRANSCRIPT LOG")
        chat_header.setStyleSheet(
            "color:rgba(150,200,230,180); font-size:11px; letter-spacing:4px;"
            " font-family:Consolas; background:transparent;"
        )

        self.chat_view = QtWidgets.QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.chat_view.setStyleSheet(
            "QTextEdit{background:transparent; color:#d0f0ff; font-size:13px;"
            " border:none;}"
        )

        chat_layout.addWidget(chat_header)
        chat_layout.addWidget(self.chat_view, 1)
        root.addWidget(chat_panel, 2)

    # --- slots wired from the worker thread ---
    def set_state(self, state: str):
        self.orb.set_state(state)
        self.status.setText(state.upper())

    def set_transcript(self, text: str):
        self.transcript.setText(text or "...")

    def append_chat(self, role: str, text: str):
        who = "Aap" if role == "user" else "Mustafa"
        color = "#00d0ff" if role == "user" else "#5fffb0"
        safe_text = html.escape(text or "...").replace("\n", "<br>")
        self.chat_view.append(f'<span style="color:{color}"><b>{who}:</b></span> {safe_text}')
