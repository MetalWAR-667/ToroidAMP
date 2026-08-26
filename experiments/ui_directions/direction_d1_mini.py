"""
ToroidAMP — Direction D.1: Mini Mode & Experience Scale Prototype
Implements the 3-Experience Scale:
1. MINI (~360x36 px, always-on-top, screen edge snapping, ultra-compact control strip)
2. NORMAL (420x135 px modular instrument core + dockable Visualizer & Playlist)
3. RETINA MELT (Fullscreen visualizer with auto-fading overlay controls and return-to-prior-scale memory)
"""

import sys
import math
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QListWidget, QListWidgetItem, QFrame, QStackedWidget
)
from PySide6.QtCore import Qt, QPoint, QTimer, Signal, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QImage, QPixmap, QMouseEvent, QPainter, QColor, QFont, QKeyEvent, QGuiApplication

import pygame
from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.visualizers.toroid import ToroidVisualizer
from toroidamp.visualizers.ribbon import WaveformRibbonVisualizer


class ModuleShell(QWidget):
    """
    Dockable module window with custom titlebar,
    drag movement, and magnetic edge proximity detection.
    """
    dock_requested = Signal(object, str)
    undock_requested = Signal(object)
    closed_signal = Signal(object)

    def __init__(self, title: str, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.module_title = title
        self.is_docked = False
        self.dock_edge = None
        self._drag_pos = QPoint()
        self._is_dragging = False

        self.setStyleSheet("""
            ModuleShell {
                background-color: #0d0e15;
                border: 1px solid #00f0ff;
                border-radius: 4px;
            }
        """)

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


class VisualizerModule(ModuleShell):
    """Dockable Visualizer Module hosting Toroid & Ribbon visualizers."""
    def __init__(self, parent=None):
        super().__init__("// MODULE :: VISUALIZER", parent)
        self.setFixedSize(420, 240)

        # Visualizer Surface Container
        self.vis_label = QLabel(self)
        self.vis_label.setStyleSheet("background-color: #06070a; border: 1px solid #1a1d2e;")
        self.vis_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.vis_label, stretch=1)

        # Bottom Bar: Mode Selector & Fullscreen
        bot_bar = QWidget(self)
        bot_bar.setFixedHeight(22)
        b_layout = QHBoxLayout(bot_bar)
        b_layout.setContentsMargins(4, 0, 4, 0)
        b_layout.setSpacing(6)

        self.btn_switch = QPushButton("MODE: 3D TORUS", bot_bar)
        self.btn_switch.setStyleSheet("QPushButton { background: #141622; border: 1px solid #222638; color: #00f0ff; font-family: monospace; font-size: 9px; padding: 2px 6px; } QPushButton:hover { background: #00f0ff; color: #000; }")
        self.btn_switch.clicked.connect(self._switch_vis_mode)
        b_layout.addWidget(self.btn_switch)

        b_layout.addStretch()

        self.btn_fs = QPushButton("⛶ RETINA MELT", bot_bar)
        self.btn_fs.setStyleSheet("QPushButton { background: #141622; border: 1px solid #222638; color: #ff0077; font-family: monospace; font-size: 9px; font-weight: bold; padding: 2px 6px; } QPushButton:hover { border-color: #ff0077; background: #ff0077; color: #fff; }")
        b_layout.addWidget(self.btn_fs)

        self.main_layout.addWidget(bot_bar)

        # Pygame Offscreen Engine
        pygame.init()
        self.surf_w, self.surf_h = 412, 185
        self.surface = pygame.Surface((self.surf_w, self.surf_h))
        self.visualizers = [
            ToroidVisualizer(self.surf_w, self.surf_h),
            WaveformRibbonVisualizer(self.surf_w, self.surf_h)
        ]
        self.vis_idx = 0

    def _switch_vis_mode(self):
        self.vis_idx = (self.vis_idx + 1) % len(self.visualizers)
        name = self.visualizers[self.vis_idx].get_name().upper()
        self.btn_switch.setText(f"MODE: {name}")

    def render_frame(self, frame: AudioFrame, dt: float):
        if not self.isVisible():
            return
        self.surface.fill((6, 7, 10))
        vis = self.visualizers[self.vis_idx]
        vis.render(self.surface, frame, dt)
        
        raw_data = pygame.image.tobytes(self.surface, "RGBA")
        qimg = QImage(raw_data, self.surf_w, self.surf_h, QImage.Format.Format_RGBA8888)
        self.vis_label.setPixmap(QPixmap.fromImage(qimg))


class PlaylistModule(ModuleShell):
    """Compact Dockable Playlist Queue Module."""
    track_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__("// MODULE :: PLAYLIST", parent)
        self.setFixedSize(260, 240)

        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #06070a;
                border: 1px solid #1a1d2e;
                color: #8892b0;
                font-family: monospace;
                font-size: 11px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #11131c;
            }
            QListWidget::item:selected {
                background-color: #141a2e;
                color: #00f0ff;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: #0f121d;
                color: #00e5ff;
            }
        """)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        self.main_layout.addWidget(self.list_widget, stretch=1)

        # Queue Footer
        foot_bar = QWidget(self)
        foot_bar.setFixedHeight(20)
        f_layout = QHBoxLayout(foot_bar)
        f_layout.setContentsMargins(2, 0, 2, 0)
        self.queue_info = QLabel("TOTAL: 4 TRACKS", foot_bar)
        self.queue_info.setStyleSheet("color: #4a5270; font-family: monospace; font-size: 9px;")
        f_layout.addWidget(self.queue_info)
        self.main_layout.addWidget(foot_bar)

    def populate(self, tracks: list[tuple[str, str]]):
        self.list_widget.clear()
        for idx, (title, duration) in enumerate(tracks):
            item = QListWidgetItem(f"[{idx+1:02d}] {title:<18} {duration}")
            self.list_widget.addItem(item)
        self.queue_info.setText(f"TOTAL: {len(tracks)} TRACKS")

    def set_current_index(self, index: int):
        self.list_widget.setCurrentRow(index)

    def _on_row_changed(self, row: int):
        if row >= 0:
            self.track_selected.emit(row)


class UnifiedChassisPlayer(QWidget):
    """
    Unified Single-Window Chassis capable of operating in:
    1. MINI MODE (~380 x 36 px always-on-top control strip with screen edge snapping)
    2. NORMAL MODE (420 x 135 px modular core instrument)
    """
    scale_changed = Signal(str) # 'mini', 'normal'
    retina_melt_requested = Signal()
    play_toggled = Signal()
    prev_clicked = Signal()
    next_clicked = Signal()
    stop_clicked = Signal()
    seek_changed = Signal(int)
    volume_changed = Signal(float)
    toggle_vis_clicked = Signal()
    toggle_pl_clicked = Signal()

    EDGE_SNAP_THRESHOLD = 25 # pixels

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.mode = "normal" # 'mini' or 'normal'
        self._drag_pos = QPoint()
        self._is_dragging = False

        self.setStyleSheet("""
            UnifiedChassisPlayer {
                background-color: #0a0b10;
                border: 2px solid #00f0ff;
                border-radius: 4px;
            }
        """)

        # Main Layout using a stacked widget to cleanly transition between MINI and NORMAL views
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)

        self.stack = QStackedWidget(self)
        self.outer_layout.addWidget(self.stack)

        self._init_normal_view()
        self._init_mini_view()

        # Start in NORMAL mode
        self.set_mode("normal", animated=False)

    def _init_normal_view(self):
        """Constructs the NORMAL 420x135 px modular core view."""
        self.normal_widget = QWidget()
        layout = QVBoxLayout(self.normal_widget)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        # Header: Identity & Window Controls
        hdr = QWidget(self.normal_widget)
        hdr.setFixedHeight(18)
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(0, 0, 0, 0)

        id_lbl = QLabel("TOROIDAMP // v0.1 NORMAL", hdr)
        id_lbl.setStyleSheet("color: #00f0ff; font-family: monospace; font-size: 10px; font-weight: bold;")
        h_layout.addWidget(id_lbl)

        h_layout.addStretch()

        # Button to collapse into MINI
        btn_to_mini = QPushButton("▼ MINI", hdr)
        btn_to_mini.setFixedHeight(16)
        btn_to_mini.setStyleSheet("QPushButton { background: #141724; border: 1px solid #28304a; color: #ffaa00; font-family: monospace; font-size: 9px; font-weight: bold; padding: 0 4px; border-radius: 2px; } QPushButton:hover { border-color: #ffaa00; }")
        btn_to_mini.clicked.connect(lambda: self.set_mode("mini"))
        h_layout.addWidget(btn_to_mini)

        btn_fs = QPushButton("⛶ MELT", hdr)
        btn_fs.setFixedHeight(16)
        btn_fs.setStyleSheet("QPushButton { background: #141724; border: 1px solid #28304a; color: #ff0077; font-family: monospace; font-size: 9px; font-weight: bold; padding: 0 4px; border-radius: 2px; } QPushButton:hover { border-color: #ff0077; }")
        btn_fs.clicked.connect(self.retina_melt_requested.emit)
        h_layout.addWidget(btn_fs)

        btn_close = QPushButton("✕", hdr)
        btn_close.setFixedSize(16, 16)
        btn_close.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #ff0055; }")
        btn_close.clicked.connect(QApplication.quit)
        h_layout.addWidget(btn_close)

        layout.addWidget(hdr)

        # LCD Display Rack
        lcd_frame = QFrame(self.normal_widget)
        lcd_frame.setFixedHeight(38)
        lcd_frame.setStyleSheet("background-color: #040508; border: 1px solid #1a2233; border-radius: 3px; padding: 2px 6px;")
        lcd_layout = QHBoxLayout(lcd_frame)
        lcd_layout.setContentsMargins(4, 2, 4, 2)

        self.normal_title_marquee = QLabel("♫ 01. Burn The World Waltz.mp3", lcd_frame)
        self.normal_title_marquee.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 12px; font-weight: bold;")
        lcd_layout.addWidget(self.normal_title_marquee, stretch=2)

        self.normal_time_display = QLabel("02:15 / 03:20", lcd_frame)
        self.normal_time_display.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 11px;")
        lcd_layout.addWidget(self.normal_time_display, alignment=Qt.AlignRight)

        layout.addWidget(lcd_frame)

        # Progress / Seek Bar
        self.normal_seek_slider = QSlider(Qt.Horizontal, self.normal_widget)
        self.normal_seek_slider.setRange(0, 100)
        self.normal_seek_slider.setValue(45)
        self.normal_seek_slider.setFixedHeight(12)
        self.normal_seek_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 3px; background: #1a1d2e; border-radius: 1px; }
            QSlider::sub-page:horizontal { background: #00f0ff; border-radius: 1px; }
            QSlider::handle:horizontal { background: #ffffff; border: 1px solid #00f0ff; width: 8px; margin: -3px 0; border-radius: 4px; }
        """)
        self.normal_seek_slider.valueChanged.connect(self.seek_changed.emit)
        layout.addWidget(self.normal_seek_slider)

        # Transport & Module Bar
        ctrl_bar = QWidget(self.normal_widget)
        c_layout = QHBoxLayout(ctrl_bar)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(4)

        btn_style = """
            QPushButton {
                background-color: #141724;
                border: 1px solid #28304a;
                border-radius: 2px;
                color: #e2e8f0;
                font-family: monospace;
                font-weight: bold;
                font-size: 10px;
                padding: 4px 8px;
            }
            QPushButton:hover { border-color: #00f0ff; color: #00f0ff; }
            QPushButton:pressed { background-color: #00f0ff; color: #000000; }
        """
        btn_prev = QPushButton("◄◄", ctrl_bar)
        btn_prev.setStyleSheet(btn_style)
        btn_prev.clicked.connect(self.prev_clicked.emit)
        c_layout.addWidget(btn_prev)

        self.normal_btn_play = QPushButton("►", ctrl_bar)
        self.normal_btn_play.setStyleSheet(btn_style)
        self.normal_btn_play.clicked.connect(self.play_toggled.emit)
        c_layout.addWidget(self.normal_btn_play)

        btn_stop = QPushButton("■", ctrl_bar)
        btn_stop.setStyleSheet(btn_style)
        btn_stop.clicked.connect(self.stop_clicked.emit)
        c_layout.addWidget(btn_stop)

        btn_next = QPushButton("►►", ctrl_bar)
        btn_next.setStyleSheet(btn_style)
        btn_next.clicked.connect(self.next_clicked.emit)
        c_layout.addWidget(btn_next)

        vol_lbl = QLabel("VOL", ctrl_bar)
        vol_lbl.setStyleSheet("color: #64748b; font-family: monospace; font-size: 9px; font-weight: bold;")
        c_layout.addWidget(vol_lbl)

        self.normal_vol_slider = QSlider(Qt.Horizontal, ctrl_bar)
        self.normal_vol_slider.setRange(0, 100)
        self.normal_vol_slider.setValue(80)
        self.normal_vol_slider.setFixedWidth(50)
        self.normal_vol_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 3px; background: #1a1d2e; }
            QSlider::sub-page:horizontal { background: #00ffaa; }
            QSlider::handle:horizontal { background: #ffffff; width: 6px; margin: -2px 0; }
        """)
        self.normal_vol_slider.valueChanged.connect(lambda v: self.volume_changed.emit(v / 100.0))
        c_layout.addWidget(self.normal_vol_slider)

        c_layout.addStretch()

        # Module Toggle Chips
        self.chip_vis = QPushButton("VIS", ctrl_bar)
        self.chip_vis.setCheckable(True)
        self.chip_vis.setStyleSheet("""
            QPushButton { background: #0f1320; border: 1px solid #00f0ff; color: #00f0ff; font-family: monospace; font-size: 9px; font-weight: bold; padding: 3px 6px; border-radius: 2px; }
            QPushButton:checked { background: #00f0ff; color: #000000; }
        """)
        self.chip_vis.clicked.connect(self.toggle_vis_clicked.emit)
        c_layout.addWidget(self.chip_vis)

        self.chip_pl = QPushButton("PL", ctrl_bar)
        self.chip_pl.setCheckable(True)
        self.chip_pl.setStyleSheet("""
            QPushButton { background: #0f1320; border: 1px solid #ff0077; color: #ff0077; font-family: monospace; font-size: 9px; font-weight: bold; padding: 3px 6px; border-radius: 2px; }
            QPushButton:checked { background: #ff0077; color: #000000; }
        """)
        self.chip_pl.clicked.connect(self.toggle_pl_clicked.emit)
        c_layout.addWidget(self.chip_pl)

        layout.addWidget(ctrl_bar)
        self.stack.addWidget(self.normal_widget)

    def _init_mini_view(self):
        """Constructs the ultra-compact MINI ~380x36 px control strip."""
        self.mini_widget = QWidget()
        layout = QHBoxLayout(self.mini_widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # Micro Transport Controls
        mini_btn_style = """
            QPushButton {
                background-color: #141724;
                border: 1px solid #28304a;
                border-radius: 2px;
                color: #e2e8f0;
                font-family: monospace;
                font-weight: bold;
                font-size: 9px;
                padding: 2px 5px;
            }
            QPushButton:hover { border-color: #00f0ff; color: #00f0ff; }
        """
        btn_prev = QPushButton("◄◄", self.mini_widget)
        btn_prev.setStyleSheet(mini_btn_style)
        btn_prev.clicked.connect(self.prev_clicked.emit)
        layout.addWidget(btn_prev)

        self.mini_btn_play = QPushButton("►", self.mini_widget)
        self.mini_btn_play.setStyleSheet(mini_btn_style)
        self.mini_btn_play.clicked.connect(self.play_toggled.emit)
        layout.addWidget(self.mini_btn_play)

        btn_next = QPushButton("►►", self.mini_widget)
        btn_next.setStyleSheet(mini_btn_style)
        btn_next.clicked.connect(self.next_clicked.emit)
        layout.addWidget(btn_next)

        # Compact Track Title Marquee
        self.mini_title_marquee = QLabel("♫ 01. Burn The World Waltz.mp3", self.mini_widget)
        self.mini_title_marquee.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 10px; font-weight: bold;")
        layout.addWidget(self.mini_title_marquee, stretch=2)

        # Mini Time Display
        self.mini_time_display = QLabel("02:15", self.mini_widget)
        self.mini_time_display.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 9px;")
        layout.addWidget(self.mini_time_display)

        # Mini Volume Indicator / Toggle
        vol_ico = QLabel("🔊", self.mini_widget)
        vol_ico.setStyleSheet("color: #00ffaa; font-size: 10px;")
        layout.addWidget(vol_ico)

        # Expand to NORMAL button
        btn_to_normal = QPushButton("▲ NORMAL", self.mini_widget)
        btn_to_normal.setFixedHeight(18)
        btn_to_normal.setStyleSheet("QPushButton { background: #141724; border: 1px solid #00f0ff; color: #00f0ff; font-family: monospace; font-size: 9px; font-weight: bold; padding: 0 4px; border-radius: 2px; } QPushButton:hover { background: #00f0ff; color: #000; }")
        btn_to_normal.clicked.connect(lambda: self.set_mode("normal"))
        layout.addWidget(btn_to_normal)

        # Direct to RETINA MELT
        btn_fs = QPushButton("⛶", self.mini_widget)
        btn_fs.setFixedSize(18, 18)
        btn_fs.setStyleSheet("QPushButton { background: #141724; border: 1px solid #ff0077; color: #ff0077; font-family: monospace; font-size: 10px; font-weight: bold; border-radius: 2px; } QPushButton:hover { background: #ff0077; color: #fff; }")
        btn_fs.clicked.connect(self.retina_melt_requested.emit)
        layout.addWidget(btn_fs)

        self.stack.addWidget(self.mini_widget)

    def set_mode(self, mode: str, animated: bool = True):
        self.mode = mode
        if mode == "mini":
            self.stack.setCurrentWidget(self.mini_widget)
            self.setFixedSize(380, 36)
            # Set Always-On-Top for MINI
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.show()
            self.scale_changed.emit("mini")
        else: # 'normal'
            self.stack.setCurrentWidget(self.normal_widget)
            self.setFixedSize(420, 135)
            # Remove Always-On-Top in NORMAL
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()
            self.scale_changed.emit("normal")

    def update_telemetry(self, title: str, time_str: str, is_playing: bool):
        self.normal_title_marquee.setText(title)
        self.mini_title_marquee.setText(title)
        self.normal_time_display.setText(time_str)
        self.mini_time_display.setText(time_str.split(" / ")[0] if " / " in time_str else time_str)
        
        play_icon = "❚❚" if is_playing else "►"
        self.normal_btn_play.setText(play_icon)
        self.mini_btn_play.setText(play_icon)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            
            # If in MINI mode, apply screen edge snapping
            if self.mode == "mini":
                screen_geom = self.screen().availableGeometry()
                # Snap to Top
                if abs(new_pos.y() - screen_geom.top()) < self.EDGE_SNAP_THRESHOLD:
                    new_pos.setY(screen_geom.top())
                # Snap to Bottom
                elif abs((new_pos.y() + self.height()) - screen_geom.bottom()) < self.EDGE_SNAP_THRESHOLD:
                    new_pos.setY(screen_geom.bottom() - self.height())
                # Snap to Left
                if abs(new_pos.x() - screen_geom.left()) < self.EDGE_SNAP_THRESHOLD:
                    new_pos.setX(screen_geom.left())
                # Snap to Right
                elif abs((new_pos.x() + self.width()) - screen_geom.right()) < self.EDGE_SNAP_THRESHOLD:
                    new_pos.setX(screen_geom.right() - self.width())

            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._is_dragging = False


class RetinaMeltFullscreenWindow(QWidget):
    """
    RETINA MELT: Fullscreen Visualizer Experience with Auto-Hiding Playback Controls.
    """
    exit_requested = Signal()
    play_toggled = Signal()
    prev_clicked = Signal()
    next_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: #000000;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Fullscreen Visualizer Label
        self.vis_label = QLabel(self)
        self.vis_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.vis_label)

        # Floating Overlay Control Bar (at bottom center)
        self.hud = QFrame(self)
        self.hud.setFixedHeight(48)
        self.hud.setFixedWidth(540)
        self.hud.setStyleSheet("""
            QFrame {
                background-color: rgba(10, 11, 16, 210);
                border: 1px solid #00f0ff;
                border-radius: 6px;
            }
        """)
        h_layout = QHBoxLayout(self.hud)
        h_layout.setContentsMargins(12, 6, 12, 6)
        h_layout.setSpacing(8)

        hud_btn_style = """
            QPushButton {
                background-color: #141724;
                border: 1px solid #00f0ff;
                border-radius: 3px;
                color: #00f0ff;
                font-family: monospace;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 8px;
            }
            QPushButton:hover { background-color: #00f0ff; color: #000; }
        """
        btn_prev = QPushButton("◄◄", self.hud)
        btn_prev.setStyleSheet(hud_btn_style)
        btn_prev.clicked.connect(self.prev_clicked.emit)
        h_layout.addWidget(btn_prev)

        self.hud_btn_play = QPushButton("►", self.hud)
        self.hud_btn_play.setStyleSheet(hud_btn_style)
        self.hud_btn_play.clicked.connect(self.play_toggled.emit)
        h_layout.addWidget(self.hud_btn_play)

        btn_next = QPushButton("►►", self.hud)
        btn_next.setStyleSheet(hud_btn_style)
        btn_next.clicked.connect(self.next_clicked.emit)
        h_layout.addWidget(btn_next)

        self.hud_title = QLabel("♫ Burn The World Waltz.mp3", self.hud)
        self.hud_title.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 11px; font-weight: bold; background: transparent; border: none;")
        h_layout.addWidget(self.hud_title, stretch=2)

        self.hud_time = QLabel("02:15 / 03:20", self.hud)
        self.hud_time.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 10px; background: transparent; border: none;")
        h_layout.addWidget(self.hud_time)

        btn_exit = QPushButton("✕ EXIT (ESC)", self.hud)
        btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #24141d;
                border: 1px solid #ff0077;
                border-radius: 3px;
                color: #ff0077;
                font-family: monospace;
                font-weight: bold;
                font-size: 10px;
                padding: 4px 8px;
            }
            QPushButton:hover { background-color: #ff0077; color: #fff; }
        """)
        btn_exit.clicked.connect(self.exit_requested.emit)
        h_layout.addWidget(btn_exit)

        # Pygame Engine for Fullscreen
        pygame.init()
        self.surf_w, self.surf_h = 1920, 1080
        self.surface = pygame.Surface((self.surf_w, self.surf_h))
        self.toroid = ToroidVisualizer(self.surf_w, self.surf_h)

        # HUD Inactivity Timer (Auto-hide HUD after 2.5s of no mouse movement)
        self.hud_timer = QTimer(self)
        self.hud_timer.timeout.connect(self._hide_hud)
        self.hud_timer.start(2500)

        # Track mouse without clicking
        self.setMouseTracking(True)
        self.vis_label.setMouseTracking(True)

    def show_fullscreen_experience(self):
        screen_geom = QGuiApplication.primaryScreen().geometry()
        self.surf_w = screen_geom.width()
        self.surf_h = screen_geom.height()
        self.surface = pygame.Surface((self.surf_w, self.surf_h))
        self.toroid.resize(self.surf_w, self.surf_h)
        
        self.setGeometry(screen_geom)
        self.hud.move((self.surf_w - self.hud.width()) // 2, self.surf_h - 70)
        self.hud.show()
        self.showFullScreen()

    def mouseMoveEvent(self, event: QMouseEvent):
        self.hud.show()
        self.hud_timer.start(2500) # Reset timer
        event.accept()

    def _hide_hud(self):
        self.hud.hide()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Escape, Qt.Key_F):
            self.exit_requested.emit()
        elif event.key() == Qt.Key_Space:
            self.play_toggled.emit()
        else:
            super().keyPressEvent(event)

    def render_frame(self, frame: AudioFrame, dt: float):
        if not self.isVisible():
            return
        self.surface.fill((0, 0, 0))
        self.toroid.render(self.surface, frame, dt)
        raw_data = pygame.image.tobytes(self.surface, "RGBA")
        qimg = QImage(raw_data, self.surf_w, self.surf_h, QImage.Format.Format_RGBA8888)
        self.vis_label.setPixmap(QPixmap.fromImage(qimg))


class ExperienceScaleManager(QWidget):
    """
    Main Orchestrator for ToroidAMP's 3 Experience Scales:
    - MINI
    - NORMAL
    - RETINA MELT
    Maintains memory of prior scales and module states.
    """
    SNAP_THRESHOLD = 30 # px for modular docking

    def __init__(self):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, 1, 1)

        # 1. Main Unified Chassis (MINI & NORMAL)
        self.player = UnifiedChassisPlayer()
        self.player.move(250, 180)
        self.player.show()

        # 2. Dockable Modules (Visualizer & Playlist)
        self.vis_mod = VisualizerModule()
        self.pl_mod = PlaylistModule()

        # 3. Retina Melt Fullscreen Window
        self.retina_melt = RetinaMeltFullscreenWindow()

        # Scale and Module State Memory
        self.prior_scale = "normal" # 'mini' or 'normal'
        self.saved_vis_visible = False
        self.saved_pl_visible = False

        # Track list for demonstration
        self.tracks = [
            ("Burn The World Waltz.mp3", "03:20"),
            ("dalezy-lotus_drei_remix.xm", "00:40"),
            ("08_sad_song.it", "03:19"),
            ("tubularbells-metal hr.mod", "01:55")
        ]
        self.pl_mod.populate(self.tracks)
        self.current_track_idx = 0

        # Wire Signals
        self._wire_signals()

        # Simulation / Render Loop (~60 FPS)
        self.is_playing = True
        self.playback_time = 0.0
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._tick)
        self.render_timer.start(16)

        # Magnetic Snap Monitor Timer (~30 FPS)
        self.snap_timer = QTimer(self)
        self.snap_timer.timeout.connect(self._check_magnetic_snapping)
        self.snap_timer.start(33)

    def _wire_signals(self):
        # Player Chassis Scale & Controls
        self.player.scale_changed.connect(self._on_scale_changed)
        self.player.retina_melt_requested.connect(self._enter_retina_melt)
        self.player.play_toggled.connect(self._toggle_play)
        self.player.prev_clicked.connect(self._prev_track)
        self.player.next_clicked.connect(self._next_track)
        self.player.stop_clicked.connect(self._stop_playback)
        self.player.toggle_vis_clicked.connect(self._toggle_vis)
        self.player.toggle_pl_clicked.connect(self._toggle_pl)

        # Module Docking & Playlist
        self.vis_mod.dock_requested.connect(lambda m, edge: self.dock_module(m, "bottom"))
        self.vis_mod.undock_requested.connect(self.undock_module)
        self.vis_mod.closed_signal.connect(lambda m: self.player.chip_vis.setChecked(False))
        self.vis_mod.btn_fs.clicked.connect(self._enter_retina_melt)

        self.pl_mod.dock_requested.connect(lambda m, edge: self.dock_module(m, "right"))
        self.pl_mod.undock_requested.connect(self.undock_module)
        self.pl_mod.closed_signal.connect(lambda m: self.player.chip_pl.setChecked(False))
        self.pl_mod.track_selected.connect(self._select_track)

        # Retina Melt Fullscreen Controls
        self.retina_melt.exit_requested.connect(self._exit_retina_melt)
        self.retina_melt.play_toggled.connect(self._toggle_play)
        self.retina_melt.prev_clicked.connect(self._prev_track)
        self.retina_melt.next_clicked.connect(self._next_track)

    def _on_scale_changed(self, new_scale: str):
        if new_scale == "mini":
            # Record previous module states before hiding
            self.saved_vis_visible = self.vis_mod.isVisible()
            self.saved_pl_visible = self.pl_mod.isVisible()
            self.vis_mod.hide()
            self.pl_mod.hide()
            self.prior_scale = "mini"
        elif new_scale == "normal":
            # Restore previous module states
            if self.saved_vis_visible:
                self.dock_module(self.vis_mod, "bottom")
                self.vis_mod.show()
                self.player.chip_vis.setChecked(True)
            if self.saved_pl_visible:
                self.dock_module(self.pl_mod, "right")
                self.pl_mod.show()
                self.player.chip_pl.setChecked(True)
            self.prior_scale = "normal"
            self.realign_docked_modules()

    def _enter_retina_melt(self):
        """Transitions into Fullscreen RETINA MELT from either MINI or NORMAL."""
        self.prior_scale = self.player.mode # Remember whether we came from MINI or NORMAL
        
        # Hide standard player windows during fullscreen
        self.player.hide()
        self.vis_mod.hide()
        self.pl_mod.hide()

        # Update HUD state
        title, _ = self.tracks[self.current_track_idx]
        self.retina_melt.hud_title.setText(f"♫ {title}")
        self.retina_melt.hud_btn_play.setText("❚❚" if self.is_playing else "►")
        
        self.retina_melt.show_fullscreen_experience()

    def _exit_retina_melt(self):
        """Returns seamlessly from RETINA MELT back to the exact prior experience scale."""
        self.retina_melt.hide()
        self.player.set_mode(self.prior_scale, animated=False)
        self.player.show()

    def _toggle_play(self):
        self.is_playing = not self.is_playing
        self.retina_melt.hud_btn_play.setText("❚❚" if self.is_playing else "►")

    def _stop_playback(self):
        self.is_playing = False
        self.playback_time = 0.0
        self.retina_melt.hud_btn_play.setText("►")

    def _select_track(self, index: int):
        self.current_track_idx = index
        title, _ = self.tracks[index]
        self.pl_mod.set_current_index(index)
        self.retina_melt.hud_title.setText(f"♫ {title}")
        self.playback_time = 0.0

    def _next_track(self):
        idx = (self.current_track_idx + 1) % len(self.tracks)
        self._select_track(idx)

    def _prev_track(self):
        idx = (self.current_track_idx - 1) % len(self.tracks)
        self._select_track(idx)

    def _toggle_vis(self):
        if self.vis_mod.isVisible():
            self.vis_mod.hide()
            self.player.chip_vis.setChecked(False)
        else:
            self.dock_module(self.vis_mod, "bottom")
            self.vis_mod.show()
            self.player.chip_vis.setChecked(True)

    def _toggle_pl(self):
        if self.pl_mod.isVisible():
            self.pl_mod.hide()
            self.player.chip_pl.setChecked(False)
        else:
            self.dock_module(self.pl_mod, "right")
            self.pl_mod.show()
            self.player.chip_pl.setChecked(True)

    def dock_module(self, module: ModuleShell, edge: str):
        module.is_docked = True
        module.dock_edge = edge
        module.btn_dock.setText("⇱")
        self.realign_docked_modules()

    def undock_module(self, module: ModuleShell):
        module.is_docked = False
        module.dock_edge = None
        module.btn_dock.setText("⇲")

    def realign_docked_modules(self):
        if self.player.mode != "normal":
            return
        core_geom = self.player.geometry()

        if self.vis_mod.is_docked and self.vis_mod.isVisible():
            self.vis_mod.move(core_geom.left(), core_geom.bottom() + 2)

        if self.pl_mod.is_docked and self.pl_mod.isVisible():
            self.pl_mod.move(core_geom.right() + 2, core_geom.top())
            if self.vis_mod.is_docked and self.vis_mod.isVisible():
                self.pl_mod.setFixedHeight(core_geom.height() + self.vis_mod.height() + 2)
            else:
                self.pl_mod.setFixedHeight(core_geom.height())

    def _check_magnetic_snapping(self):
        if self.player.mode != "normal" or not self.player.isVisible():
            return
        core_geom = self.player.geometry()
        self.realign_docked_modules()

        # Check Visualizer Bottom Proximity
        if not self.vis_mod.is_docked and self.vis_mod.isVisible():
            vis_geom = self.vis_mod.geometry()
            dx = abs(vis_geom.left() - core_geom.left())
            dy = abs(vis_geom.top() - (core_geom.bottom() + 2))
            if dx < self.SNAP_THRESHOLD and dy < self.SNAP_THRESHOLD:
                self.dock_module(self.vis_mod, "bottom")

        # Check Playlist Right Proximity
        if not self.pl_mod.is_docked and self.pl_mod.isVisible():
            pl_geom = self.pl_mod.geometry()
            dx = abs(pl_geom.left() - (core_geom.right() + 2))
            dy = abs(pl_geom.top() - core_geom.top())
            if dx < self.SNAP_THRESHOLD and dy < self.SNAP_THRESHOLD:
                self.dock_module(self.pl_mod, "right")

    def _tick(self):
        if self.is_playing:
            self.playback_time += 0.016

        mins = int(self.playback_time // 60)
        secs = int(self.playback_time % 60)
        time_str = f"{mins:02d}:{secs:02d} / 03:20"

        title, _ = self.tracks[self.current_track_idx]
        full_title = f"♫ {self.current_track_idx+1:02d}. {title}"
        self.player.update_telemetry(full_title, time_str, self.is_playing)
        self.retina_melt.hud_time.setText(time_str)

        # Generate AudioFrame
        t = self.playback_time
        rms = (math.sin(t * 3.0) + 1.0) * 0.4 * (1.0 if self.is_playing else 0.0)
        bass = (math.sin(t * 5.0) + 1.0) * 0.45 * (1.0 if self.is_playing else 0.0)
        mids = (math.cos(t * 2.0) + 1.0) * 0.35 * (1.0 if self.is_playing else 0.0)
        treble = (math.sin(t * 8.0) + 1.0) * 0.25 * (1.0 if self.is_playing else 0.0)

        is_beat = (math.sin(t * 6.28 * 2.1) > 0.8) and self.is_playing
        is_strong_beat = (math.sin(t * 6.28 * 1.05) > 0.92) and self.is_playing

        wf = [float(math.sin(t * 20.0 + i * 0.1) * (0.2 + bass * 0.8)) for i in range(128)]
        spec = [float(abs(math.sin(t * 4.0 + i * 0.15)) * (0.1 + bass * 0.9)) for i in range(64)]

        frame = AudioFrame(
            rms=rms,
            peak=min(1.0, rms * 1.3),
            bass=bass,
            mids=mids,
            treble=treble,
            spectrum=tuple(spec),
            waveform=tuple(wf),
            beat=is_beat,
            strong_beat=is_strong_beat
        )

        # Render Active Visualizers
        if self.vis_mod.isVisible():
            self.vis_mod.render_frame(frame, 0.016)
        if self.retina_melt.isVisible():
            self.retina_melt.render_frame(frame, 0.016)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    manager = ExperienceScaleManager()
    sys.exit(app.exec())
