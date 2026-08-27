from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QColor

from ..neon import NeonState


class ModuleShell(QWidget):
    """
    Base floating & dockable module window.

    USER SIZE IS STATE — a module's floating dimensions are user choice, not
    layout incidental. `user_size` tracks the last size the human chose while
    the module was floating; lifecycle transitions (MINI/NORMAL, dock/undock)
    may hide or temporarily constrain a module but must never erase that choice.
    """
    dock_requested = Signal(object, str)
    undock_requested = Signal(object)
    closed_signal = Signal(object)

    # Subclasses override these three to define their resize contract.
    DEFAULT_SIZE = QSize(300, 200)
    MIN_SIZE = QSize(200, 150)
    # Edges disabled while docked — either because docking forces that
    # dimension programmatically (e.g. VIS width follows the chassis), or
    # because dragging that edge would fight the dock's position anchor
    # (e.g. PL's x is anchored to the chassis right edge, so its left edge
    # is not draggable while docked). Empty set = fully free even docked.
    DOCK_LOCKED_EDGES: set[str] = set()

    RESIZE_MARGIN = 6

    _CURSOR_MAP = {
        frozenset({"left"}): Qt.SizeHorCursor,
        frozenset({"right"}): Qt.SizeHorCursor,
        frozenset({"top"}): Qt.SizeVerCursor,
        frozenset({"bottom"}): Qt.SizeVerCursor,
        frozenset({"left", "top"}): Qt.SizeFDiagCursor,
        frozenset({"right", "bottom"}): Qt.SizeFDiagCursor,
        frozenset({"right", "top"}): Qt.SizeBDiagCursor,
        frozenset({"left", "bottom"}): Qt.SizeBDiagCursor,
    }

    def __init__(self, title: str, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.module_title = title
        self.is_docked = False
        self.dock_edge = None
        self._drag_pos = QPoint()
        self._is_dragging = False
        self._resizing = False
        self._resize_edges: set[str] = set()
        self._resize_start_geom = QRect()
        self._resize_start_pos = QPoint()
        self._current_neon: NeonState | None = None

        self.setMinimumSize(self.MIN_SIZE)
        self._user_size = QSize(self.DEFAULT_SIZE)
        self.resize(self.DEFAULT_SIZE)

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

        # UX-003: repurposed from the former dock/undock toggle into an
        # explicit "Reset size" action. Dock/undock is now purely a function
        # of dragging the module (magnetic snap docks it; dragging a docked
        # module away undocks it) — see WindowManager._check_magnetic_snapping.
        self.btn_reset = QPushButton("↺", self.title_bar)
        self.btn_reset.setToolTip("Reset size")
        self.btn_reset.setFixedSize(16, 16)
        self.btn_reset.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #00f0ff; }")
        self.btn_reset.clicked.connect(self.reset_size)
        t_layout.addWidget(self.btn_reset)

        self.btn_close = QPushButton("✕", self.title_bar)
        self.btn_close.setToolTip("Close Module")
        self.btn_close.setFixedSize(16, 16)
        self.btn_close.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #ff0055; }")
        self.btn_close.clicked.connect(self.close_module)
        t_layout.addWidget(self.btn_close)

        self.main_layout.addWidget(self.title_bar)

    @property
    def user_size(self) -> QSize:
        """The module's last known floating (undocked) size — persisted session state."""
        return QSize(self._user_size)

    def set_user_size(self, width: int, height: int):
        """Applies a known user size (e.g. session restore), clamped to the module minimum."""
        size = QSize(max(self.MIN_SIZE.width(), width), max(self.MIN_SIZE.height(), height))
        self._user_size = size
        self.resize(size)

    def reset_size(self):
        """
        RESET SIZE — restores default dimensions only.
        Does not move, dock, undock, close, or change module content/selection.
        """
        self._user_size = QSize(self.DEFAULT_SIZE)
        self.resize(self.DEFAULT_SIZE)

    def restore_user_size(self):
        """Restores the last floating size — used when a module is undocked."""
        self.resize(self._user_size)

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

    # ------------------------------------------------------------------
    # Resize affordance — frameless windows get no native edge resize, so
    # ModuleShell hit-tests its own border margin and drives geometry by hand.
    # ------------------------------------------------------------------

    def _allowed_edges(self) -> set[str]:
        """Edges the user may currently drag, given docking constraints."""
        if not self.is_docked:
            return {"left", "right", "top", "bottom"}
        return {"left", "right", "top", "bottom"} - self.DOCK_LOCKED_EDGES

    def _edge_at(self, pos: QPoint) -> set[str]:
        edges = set()
        w, h = self.width(), self.height()
        m = self.RESIZE_MARGIN
        if pos.x() <= m:
            edges.add("left")
        elif pos.x() >= w - m:
            edges.add("right")
        if pos.y() <= m:
            edges.add("top")
        elif pos.y() >= h - m:
            edges.add("bottom")
        return edges & self._allowed_edges()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            return
        edges = self._edge_at(event.pos())
        if edges:
            self._resizing = True
            self._resize_edges = edges
            self._resize_start_geom = self.geometry()
            self._resize_start_pos = event.globalPosition().toPoint()
            event.accept()
            return
        if event.pos().y() <= 24:
            self._is_dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._resizing and (event.buttons() & Qt.LeftButton):
            self._apply_resize_drag(event.globalPosition().toPoint())
            event.accept()
            return

        if self._is_dragging and (event.buttons() & Qt.LeftButton):
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            if self.is_docked:
                self.undock_requested.emit(self)
            self.move(new_pos)
            event.accept()
            return

        # Hover feedback: show a resize cursor near a draggable edge.
        if not (event.buttons() & Qt.LeftButton):
            edges = self._edge_at(event.pos())
            if edges:
                cursor = self._CURSOR_MAP.get(frozenset(edges))
                self.setCursor(cursor if cursor is not None else Qt.ArrowCursor)
            else:
                self.unsetCursor()

    def _apply_resize_drag(self, global_pos: QPoint):
        delta = global_pos - self._resize_start_pos
        geom = QRect(self._resize_start_geom)
        min_w, min_h = self.MIN_SIZE.width(), self.MIN_SIZE.height()

        if "left" in self._resize_edges:
            new_left = geom.left() + delta.x()
            if geom.right() - new_left + 1 < min_w:
                new_left = geom.right() - min_w + 1
            geom.setLeft(new_left)
        if "right" in self._resize_edges:
            geom.setWidth(max(min_w, geom.width() + delta.x()))
        if "top" in self._resize_edges:
            new_top = geom.top() + delta.y()
            if geom.bottom() - new_top + 1 < min_h:
                new_top = geom.bottom() - min_h + 1
            geom.setTop(new_top)
        if "bottom" in self._resize_edges:
            geom.setHeight(max(min_h, geom.height() + delta.y()))

        self.setGeometry(geom)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._resizing:
            self._resizing = False
            self._resize_edges = set()
            # A completed edge-drag always reflects genuine user intent, even
            # while docked — docking only prevents dragging the edges it
            # forces programmatically (DOCK_LOCKED_EDGES), so any drag that
            # actually happened here was never one of those. Floating
            # resizes are already captured continuously via resizeEvent;
            # this additionally captures docked-but-free-edge resizes
            # (e.g. a docked PlaylistModule's bottom/right edges), which
            # resizeEvent intentionally ignores while docked.
            self._user_size = self.size()
            event.accept()
            return
        if self._is_dragging:
            self._is_dragging = False
            event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.is_docked:
            self._user_size = self.size()

    def close_module(self):
        self.hide()
        self.closed_signal.emit(self)
