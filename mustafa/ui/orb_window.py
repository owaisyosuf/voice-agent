"""MUSTAFA's window.

Layout, and only layout — the painting lives in `widgets`, the colours and type
in `theme`. Two panes: the voice stage on the left (orb, state, live caption,
mic level) and the conversation on the right, with one composer bar underneath
that serves both typing and speaking.
"""

from PyQt6 import QtCore, QtGui, QtWidgets

from ..config import (
    ASSISTANT_NAME,
    TTS_VOICE,
    WAKE_WORD_ENABLED,
    WHISPER_MODEL,
)
from . import theme as t
from .widgets import (
    Backdrop,
    BrandMark,
    ConversationView,
    LevelMeter,
    Orb,
    StatePill,
    WindowButton,
)


class TitleBar(QtWidgets.QWidget):
    """Brand, live status, window controls — and the handle the window drags by."""

    minimize = QtCore.pyqtSignal()
    maximize = QtCore.pyqtSignal()
    close_window = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self._drag_offset = None

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(t.S3)

        self.mark = BrandMark()

        wordmark = QtWidgets.QLabel(ASSISTANT_NAME.upper())
        wordmark.setStyleSheet(f"color: {t.TEXT_PRIMARY}; background: transparent;")
        t.tracked_font(wordmark, t.SIZE_BRAND, weight=700, spacing=6.0)

        tagline = QtWidgets.QLabel("VOICE AGENT FOR WINDOWS")
        tagline.setObjectName("meta")
        t.tracked_font(tagline, t.SIZE_MICRO, weight=600, spacing=2.6, mono=True)

        brand = QtWidgets.QVBoxLayout()
        brand.setSpacing(0)
        brand.addWidget(wordmark)
        brand.addWidget(tagline)

        self.pill = StatePill()

        row.addWidget(self.mark)
        row.addLayout(brand)
        row.addSpacing(t.S3)
        row.addWidget(self.pill)
        row.addStretch(1)
        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(t.S1)
        for kind, signal in (("min", self.minimize),
                             ("max", self.maximize),
                             ("close", self.close_window)):
            button = WindowButton(kind)
            button.clicked.connect(signal)
            controls.addWidget(button)
        row.addLayout(controls)

    # Frameless windows have to move themselves.
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

    def mouseDoubleClickEvent(self, event):
        self.maximize.emit()


class Hairline(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {t.LINE_SUBTLE}; border: none;")


class MainWindow(QtWidgets.QMainWindow):
    """Public surface used by the worker threads:
    set_state / set_transcript / set_level / append_chat / set_busy,
    plus the `input_box` and `listen_btn` controls and the signals below.
    """

    suggestion = QtCore.pyqtSignal(str)          # example chip clicked
    clear_requested = QtCore.pyqtSignal()        # user asked to wipe the thread

    def __init__(self):
        super().__init__()
        self.setWindowTitle(ASSISTANT_NAME.upper())
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(940, 620)
        self._maximized = False
        self._build()
        self.set_state("Idle")

    # --- window chrome ------------------------------------------------------
    def showFilled(self):
        """Fill the screen's work area (leaves the taskbar visible) and show."""
        self.setGeometry(QtWidgets.QApplication.primaryScreen().availableGeometry())
        self._maximized = True
        self.show()
        self.input_box.setFocus()

    def _toggle_maximize(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if self._maximized:
            available = screen.availableGeometry()
            w, h = 1120, 760
            self.setGeometry(
                available.x() + (available.width() - w) // 2,
                available.y() + (available.height() - h) // 2,
                w, h,
            )
            self._maximized = False
        else:
            self.setGeometry(screen.availableGeometry())
            self._maximized = True

    def keyPressEvent(self, event):
        # Escape steps back (fullscreen -> window) before it ever closes the app,
        # so a stray keypress can't kill a conversation mid-sentence.
        if event.key() == QtCore.Qt.Key.Key_Escape:
            if self._maximized:
                self._toggle_maximize()
            else:
                self.close()
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.Type.WindowStateChange:
            self.backdrop.set_animating(not self.isMinimized())
        super().changeEvent(event)

    # --- construction -------------------------------------------------------
    def _build(self):
        QtWidgets.QApplication.instance().setFont(QtGui.QFont(t.FONT_UI, t.SIZE_BODY))
        self.setStyleSheet(t.stylesheet())

        self.backdrop = Backdrop()
        self.setCentralWidget(self.backdrop)

        root = QtWidgets.QVBoxLayout(self.backdrop)
        root.setContentsMargins(t.S5, t.S4, t.S5, t.S5)
        root.setSpacing(t.S4)

        self.title_bar = TitleBar()
        self.title_bar.minimize.connect(self.showMinimized)
        self.title_bar.maximize.connect(self._toggle_maximize)
        self.title_bar.close_window.connect(self.close)
        root.addWidget(self.title_bar)
        root.addWidget(Hairline())

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setHandleWidth(t.S5)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_stage())
        splitter.addWidget(self._build_conversation())
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([560, 640])
        root.addWidget(splitter, 1)

        root.addWidget(self._build_composer())
        root.addWidget(self._build_footer())

    def _build_stage(self) -> QtWidgets.QWidget:
        stage = QtWidgets.QWidget()
        stage.setObjectName("stage")
        stage.setMinimumWidth(360)
        box = QtWidgets.QVBoxLayout(stage)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(t.S3)

        self.orb = Orb()

        self.state_title = QtWidgets.QLabel()
        self.state_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        t.tracked_font(self.state_title, t.SIZE_TITLE, weight=700, spacing=5.0)

        self.state_hint = QtWidgets.QLabel()
        self.state_hint.setObjectName("caption")
        self.state_hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.state_hint.setWordWrap(True)

        self.meter = LevelMeter()

        meter_row = QtWidgets.QHBoxLayout()
        meter_row.addStretch(1)
        meter_row.addWidget(self.meter)
        meter_row.addStretch(1)

        # The one line that changes most: what was heard, or what was answered.
        self.transcript = QtWidgets.QLabel("")
        self.transcript.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.transcript.setWordWrap(True)
        self.transcript.setMinimumHeight(48)
        self.transcript.setStyleSheet(
            f"color: {t.TEXT_PRIMARY}; background: transparent;"
        )
        t.tracked_font(self.transcript, t.SIZE_LEAD, weight=400)

        box.addWidget(self.orb, 1)
        box.addWidget(self.state_title)
        box.addWidget(self.state_hint)
        box.addLayout(meter_row)
        box.addSpacing(t.S2)
        box.addWidget(self.transcript)
        return stage

    def _build_conversation(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(380)
        box = QtWidgets.QVBoxLayout(panel)
        box.setContentsMargins(t.S5, t.S4, t.S4, t.S4)
        box.setSpacing(t.S3)

        label = QtWidgets.QLabel("CONVERSATION")
        label.setObjectName("sectionLabel")
        t.tracked_font(label, t.SIZE_LABEL, weight=700, spacing=3.0, mono=True)

        self.chat_count = QtWidgets.QLabel("")
        self.chat_count.setObjectName("meta")
        t.tracked_font(self.chat_count, t.SIZE_MICRO, weight=600, spacing=1.0, mono=True)

        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_btn.setObjectName("ghost")
        self.clear_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.setToolTip("Poori guftagu aur memory mita dein")
        self.clear_btn.clicked.connect(self._confirm_clear)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(t.S3)
        header.addWidget(label)
        header.addWidget(self.chat_count)
        header.addStretch(1)
        header.addWidget(self.clear_btn)

        self.chat_view = ConversationView()
        self.chat_view.suggestion.connect(self.suggestion)

        box.addLayout(header)
        box.addWidget(Hairline())
        box.addWidget(self.chat_view, 1)
        return panel

    def _build_composer(self) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget()
        holder.setObjectName("stage")
        row = QtWidgets.QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(t.S3)

        self.input_box = QtWidgets.QLineEdit()
        self.input_box.setObjectName("composer")
        self.input_box.setPlaceholderText(
            "Likh kar hukum dijiye — \"notepad kholo\", \"close chrome\", ya koi sawal…"
        )
        self.input_box.setClearButtonEnabled(True)
        self.input_box.setFixedHeight(50)

        self.send_btn = QtWidgets.QPushButton("Send")
        self.send_btn.setObjectName("ghost")
        self.send_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.send_btn.setFixedHeight(50)
        self.send_btn.setMinimumWidth(88)

        self.listen_btn = QtWidgets.QPushButton("Listen")
        self.listen_btn.setObjectName("primary")
        self.listen_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.listen_btn.setFixedHeight(50)
        self.listen_btn.setMinimumWidth(150)
        self.listen_btn.setToolTip("Ctrl+Space")
        glow = QtWidgets.QGraphicsDropShadowEffect(self.listen_btn)
        glow.setColor(QtGui.QColor(t.ACCENT))
        glow.setBlurRadius(26)
        glow.setOffset(0, 0)
        self.listen_btn.setGraphicsEffect(glow)

        row.addWidget(self.input_box, 1)
        row.addWidget(self.send_btn)
        row.addWidget(self.listen_btn)
        return holder

    def _build_footer(self) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget()
        holder.setObjectName("stage")
        row = QtWidgets.QHBoxLayout(holder)
        row.setContentsMargins(t.S1, 0, t.S1, 0)

        keys = QtWidgets.QLabel(
            "Ctrl+Space  bolna    ·    Enter  bhejna    ·    Esc  window chhota karna"
        )
        keys.setObjectName("meta")
        t.tracked_font(keys, t.SIZE_MICRO, weight=600, spacing=0.6, mono=True)

        wake = "wake word on" if WAKE_WORD_ENABLED else "wake word off"
        config = QtWidgets.QLabel(f"whisper {WHISPER_MODEL}  ·  {TTS_VOICE}  ·  {wake}")
        config.setObjectName("meta")
        config.setToolTip("Sab kuch .env se badla ja sakta hai")
        t.tracked_font(config, t.SIZE_MICRO, weight=600, spacing=0.6, mono=True)

        row.addWidget(keys)
        row.addStretch(1)
        row.addWidget(config)
        return holder

    def _confirm_clear(self):
        if not self.chat_view.count():
            return
        confirm = QtWidgets.QMessageBox(self)
        confirm.setWindowTitle("Clear conversation")
        confirm.setText("Poori guftagu aur Mustafa ki memory mita dein?")
        confirm.setIcon(QtWidgets.QMessageBox.Icon.Question)
        confirm.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
        if confirm.exec() == QtWidgets.QMessageBox.StandardButton.Yes:
            self.chat_view.clear()
            self._update_count()
            self.clear_requested.emit()

    # --- slots wired from the worker threads --------------------------------
    def set_state(self, state: str):
        color, headline, hint = t.state(state)
        self.orb.set_state(state)
        self.title_bar.pill.set_state(state)
        self.title_bar.mark.set_state(state)
        self.state_title.setText(headline)
        self.state_title.setStyleSheet(f"color: {color}; background: transparent;")
        self.state_hint.setText(hint)
        self.meter.set_active(state == "Listening")
        self.backdrop.set_busy(state != "Idle")

    def set_level(self, level: float):
        """Microphone loudness, 0..1, while a capture is running."""
        self.orb.set_level(level)
        self.meter.set_level(level)

    def set_transcript(self, text: str):
        self.transcript.setText(text or "")

    def set_busy(self, busy: bool):
        """Disable the controls that would queue a second command mid-flight."""
        self.listen_btn.setEnabled(not busy)
        self.listen_btn.setText("Busy…" if busy else "Listen")
        self.send_btn.setEnabled(not busy)
        self.input_box.setEnabled(not busy)
        if not busy:
            self.input_box.setFocus()

    def append_chat(self, role: str, text: str, ts: str | None = None):
        self.chat_view.append(role, text, ts)
        self._update_count()

    def _update_count(self):
        total = self.chat_view.count()
        self.chat_count.setText(f"{total} messages" if total else "")
