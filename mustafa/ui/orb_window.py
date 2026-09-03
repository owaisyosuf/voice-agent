"""PyQt6 window with an animated, state-reactive orb — MUSTAFA's face."""

import math

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


class Orb(QtWidgets.QWidget):
    """Custom-painted glowing orb that pulses/spins based on state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 280)
        self._phase = 0.0
        self._state = "Idle"
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_state(self, state: str):
        self._state = state if state in STATE_COLORS else "Idle"
        self.update()

    def _tick(self):
        self._phase += 0.08
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


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MUSTAFA")
        self.resize(480, 600)
        self._build()

    def _build(self):
        central = QtWidgets.QWidget()
        central.setStyleSheet("background:#050a12;")
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        title = QtWidgets.QLabel("M U S T A F A")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color:#00d0ff; font-size:28px; font-weight:bold; letter-spacing:6px;"
        )

        self.orb = Orb()

        self.status = QtWidgets.QLabel("Idle")
        self.status.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color:#88ccff; font-size:16px; font-weight:bold;")

        self.transcript = QtWidgets.QLabel('Say "Hey Mustafa"')
        self.transcript.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.transcript.setWordWrap(True)
        self.transcript.setStyleSheet("color:#5f9fc0; font-size:13px;")

        self.listen_btn = QtWidgets.QPushButton("Listen")
        self.listen_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.listen_btn.setStyleSheet(
            "QPushButton{background:#0a2a3a; color:#00d0ff; border:1px solid #00d0ff;"
            " border-radius:18px; padding:10px 28px; font-size:14px;}"
            "QPushButton:hover{background:#0f3a4f;}"
        )

        layout.addWidget(title)
        layout.addWidget(self.orb, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.transcript)
        layout.addWidget(self.listen_btn, 0, QtCore.Qt.AlignmentFlag.AlignCenter)

    # --- slots wired from the worker thread ---
    def set_state(self, state: str):
        self.orb.set_state(state)
        self.status.setText(state)

    def set_transcript(self, text: str):
        self.transcript.setText(text or "...")
