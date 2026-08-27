from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QColor

from ..neon import NeonState


class ModuleShell(QWidget):
    """
    Base floating & dockable module window.
    """
    dock_requested = Signal(object, str)
    undock_requested = Signal(object)
    closed_signal = Signal(object)

    def __init__(self, title: str, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.module_title = title
        self.is_docked = False
        self.dock_edge = None
        self._drag_pos = QPoint()
        self._is_dragging = False
        self._current_neon: NeonState | None = None

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(4)

        # Title Bar
        self.title_bar = QWidget(self)
        self.title_bar.setFixedHeight(22)
        self.title_bar.setStyleSheet("background-color: #141622; border-bottom: 1px solid #222638; border-radius: 2px;")
        t_layout = QHBoxLayout(self.title_bar)
        t_layout.setContentsMargins(6, 0, 4, 0)
        t_layout.setSpacing(4)

        self.title_label = QLabel(self.module_title, self.title_bar)
        self.title_label.setStyleSheet("color: #00f0ff; font-family: monospace; font-size: 10px; font-weight: bold;")
        t_layout.addWidget(self.title_label)

        t_layout.addStretch()

        self.btn_dock = QPushButton("⇲", self.title_bar)
        self.btn_dock.setToolTip("Dock / Undock")
        self.btn_dock.setFixedSize(16, 16)
        self.btn_dock.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #00f0ff; }")
        self.btn_dock.clicked.connect(self._toggle_dock)
        t_layout.addWidget(self.btn_dock)

        self.btn_close = QPushButton("✕", self.title_bar)
        self.btn_close.setToolTip("Close Module")
        self.btn_close.setFixedSize(16, 16)
        self.btn_close.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #ff0055; }")
        self.btn_close.clicked.connect(self.close_module)
        t_layout.addWidget(self.btn_close)

        self.main_layout.addWidget(self.title_bar)

    def apply_neon_state(self, state: NeonState):
        """Applies dynamic reactive neon state to module borders."""
        self._current_neon = state
        self.update()

    def paintEvent(self, event):
        """Paints reactive electric border tailored for docked vs floating state."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background fill
        painter.setBrush(QColor(13, 14, 21, 250))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)

        # Border styling:
        # Floating: slightly brighter/distinct outline
        # Docked: sleek cohesive electric edge
        if self._current_neon:
            color = self._current_neon.tier1_chassis_color if not self.is_docked else self._current_neon.tier2_panel_color
            pen = QPen(color, 1.2)
        else:
            pen = QPen(QColor(0, 240, 255, 180), 1.2)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)
        painter.end()


    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and event.pos().y() <= 24:
            self._is_dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            if self.is_docked:
                self.undock_requested.emit(self)
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_dragging:
            self._is_dragging = False
            event.accept()

    def _toggle_dock(self):
        if self.is_docked:
            self.undock_requested.emit(self)
        else:
            self.dock_requested.emit(self, "auto")

    def close_module(self):
        self.hide()
        self.closed_signal.emit(self)
