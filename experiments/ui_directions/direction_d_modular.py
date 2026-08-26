"""
ToroidAMP — Direction D: Modular Instrument Prototype
Compact Winamp-style footprint with magnetic docking modules (Visualizer & Playlist),
floating support, and fullscreen capability.
"""

import sys
import math
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QListWidget, QListWidgetItem, QFrame
)
from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QMouseEvent, QPainter, QColor, QFont, QKeyEvent

import pygame
from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.visualizers.toroid import ToroidVisualizer
from toroidamp.visualizers.ribbon import WaveformRibbonVisualizer


class ModuleShell(QWidget):
    """
    Base floating & dockable module window with custom titlebar,
    drag movement, and magnetic edge proximity detection.
    """
    dock_requested = Signal(object, str) # module, edge ('bottom', 'right')
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
    """
    Dockable Visualizer Module hosting Toroid & Ribbon visualizers
    with seamless fullscreen capability.
    """
    fullscreen_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__("// MODULE :: VISUALIZER", parent)
        self.setFixedSize(420, 240)
        self.is_fullscreen = False

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

        self.btn_fs = QPushButton("⛶ FULLSCREEN", bot_bar)
        self.btn_fs.setStyleSheet("QPushButton { background: #141622; border: 1px solid #222638; color: #8892b0; font-family: monospace; font-size: 9px; padding: 2px 6px; } QPushButton:hover { border-color: #00f0ff; color: #00f0ff; }")
        self.btn_fs.clicked.connect(self.toggle_fullscreen)
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

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.showNormal()
            self.setFixedSize(420, 240)
            self.surf_w, self.surf_h = 412, 185
            self.surface = pygame.Surface((self.surf_w, self.surf_h))
            self.visualizers[self.vis_idx].resize(self.surf_w, self.surf_h)
            self.title_bar.show()
            self.btn_fs.setText("⛶ FULLSCREEN")
            self.fullscreen_toggled.emit(False)
        else:
            self.is_fullscreen = True
            self.title_bar.hide()
            self.btn_fs.setText("✕ EXIT FULLSCREEN (ESC)")
            self.showFullScreen()
            screen_geom = self.screen().geometry()
            self.surf_w, self.surf_h = screen_geom.width(), screen_geom.height() - 35
            self.surface = pygame.Surface((self.surf_w, self.surf_h))
            self.visualizers[self.vis_idx].resize(self.surf_w, self.surf_h)
            self.fullscreen_toggled.emit(True)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape and self.is_fullscreen:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)

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
    """
    Compact Dockable Playlist Queue Module.
    """
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


class CompactCorePlayer(QWidget):
    """
    Compact Winamp-footprint Core Player (~420 x 135 px).
    Contains essential transport controls, title marquee, time display,
    volume, and module toggle chips.
    """
    play_clicked = Signal()
    pause_clicked = Signal()
    stop_clicked = Signal()
    prev_clicked = Signal()
    next_clicked = Signal()
    seek_changed = Signal(int)
    volume_changed = Signal(float)
    toggle_vis_clicked = Signal()
    toggle_pl_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.setFixedSize(420, 135)
        self._drag_pos = QPoint()
        self._is_dragging = False

        self.setStyleSheet("""
            CompactCorePlayer {
                background-color: #0a0b10;
                border: 2px solid #00f0ff;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        # Header: Identity & Window Controls
        hdr = QWidget(self)
        hdr.setFixedHeight(18)
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(0, 0, 0, 0)

        id_lbl = QLabel("TOROIDAMP // v0.1 CORE", hdr)
        id_lbl.setStyleSheet("color: #00f0ff; font-family: monospace; font-size: 10px; font-weight: bold;")
        h_layout.addWidget(id_lbl)

        h_layout.addStretch()

        btn_min = QPushButton("─", hdr)
        btn_min.setFixedSize(16, 16)
        btn_min.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #fff; }")
        btn_min.clicked.connect(self.showMinimized)
        h_layout.addWidget(btn_min)

        btn_close = QPushButton("✕", hdr)
        btn_close.setFixedSize(16, 16)
        btn_close.setStyleSheet("QPushButton { background: transparent; border: none; color: #8892b0; font-size: 11px; } QPushButton:hover { color: #ff0055; }")
        btn_close.clicked.connect(QApplication.quit)
        h_layout.addWidget(btn_close)

        layout.addWidget(hdr)

        # LCD Display Rack
        lcd_frame = QFrame(self)
        lcd_frame.setFixedHeight(38)
        lcd_frame.setStyleSheet("background-color: #040508; border: 1px solid #1a2233; border-radius: 3px; padding: 2px 6px;")
        lcd_layout = QHBoxLayout(lcd_frame)
        lcd_layout.setContentsMargins(4, 2, 4, 2)

        self.title_marquee = QLabel("♫ 01. Burn The World Waltz.mp3", lcd_frame)
        self.title_marquee.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 12px; font-weight: bold;")
        lcd_layout.addWidget(self.title_marquee, stretch=2)

        self.time_display = QLabel("02:15 / 03:20", lcd_frame)
        self.time_display.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 11px;")
        lcd_layout.addWidget(self.time_display, alignment=Qt.AlignRight)

        layout.addWidget(lcd_frame)

        # Progress / Seek Bar
        self.seek_slider = QSlider(Qt.Horizontal, self)
        self.seek_slider.setRange(0, 100)
        self.seek_slider.setValue(45)
        self.seek_slider.setFixedHeight(12)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 3px;
                background: #1a1d2e;
                border-radius: 1px;
            }
            QSlider::sub-page:horizontal {
                background: #00f0ff;
                border-radius: 1px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #00f0ff;
                width: 8px;
                margin-top: -3px;
                margin-bottom: -3px;
                border-radius: 4px;
            }
        """)
        self.seek_slider.valueChanged.connect(self.seek_changed.emit)
        layout.addWidget(self.seek_slider)

        # Transport & Module Bar
        ctrl_bar = QWidget(self)
        c_layout = QHBoxLayout(ctrl_bar)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(4)

        # Tactile Transport Buttons
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
            QPushButton:hover {
                border-color: #00f0ff;
                color: #00f0ff;
            }
            QPushButton:pressed {
                background-color: #00f0ff;
                color: #000000;
            }
        """
        btn_prev = QPushButton("◄◄", ctrl_bar)
        btn_prev.setStyleSheet(btn_style)
        btn_prev.clicked.connect(self.prev_clicked.emit)
        c_layout.addWidget(btn_prev)

        btn_play = QPushButton("►", ctrl_bar)
        btn_play.setStyleSheet(btn_style)
        btn_play.clicked.connect(self.play_clicked.emit)
        c_layout.addWidget(btn_play)

        btn_pause = QPushButton("❚❚", ctrl_bar)
        btn_pause.setStyleSheet(btn_style)
        btn_pause.clicked.connect(self.pause_clicked.emit)
        c_layout.addWidget(btn_pause)

        btn_stop = QPushButton("■", ctrl_bar)
        btn_stop.setStyleSheet(btn_style)
        btn_stop.clicked.connect(self.stop_clicked.emit)
        c_layout.addWidget(btn_stop)

        btn_next = QPushButton("►►", ctrl_bar)
        btn_next.setStyleSheet(btn_style)
        btn_next.clicked.connect(self.next_clicked.emit)
        c_layout.addWidget(btn_next)

        # Volume Slider Mini
        vol_lbl = QLabel("VOL", ctrl_bar)
        vol_lbl.setStyleSheet("color: #64748b; font-family: monospace; font-size: 9px; font-weight: bold;")
        c_layout.addWidget(vol_lbl)

        self.vol_slider = QSlider(Qt.Horizontal, ctrl_bar)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(50)
        self.vol_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 3px; background: #1a1d2e; }
            QSlider::sub-page:horizontal { background: #00ffaa; }
            QSlider::handle:horizontal { background: #ffffff; width: 6px; margin: -2px 0; }
        """)
        self.vol_slider.valueChanged.connect(lambda v: self.volume_changed.emit(v / 100.0))
        c_layout.addWidget(self.vol_slider)

        c_layout.addStretch()

        # Module Toggle Chips
        self.chip_vis = QPushButton("VIS", ctrl_bar)
        self.chip_vis.setCheckable(True)
        self.chip_vis.setStyleSheet("""
            QPushButton {
                background: #0f1320;
                border: 1px solid #00f0ff;
                color: #00f0ff;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 2px;
            }
            QPushButton:checked {
                background: #00f0ff;
                color: #000000;
            }
        """)
        self.chip_vis.clicked.connect(self.toggle_vis_clicked.emit)
        c_layout.addWidget(self.chip_vis)

        self.chip_pl = QPushButton("PL", ctrl_bar)
        self.chip_pl.setCheckable(True)
        self.chip_pl.setStyleSheet("""
            QPushButton {
                background: #0f1320;
                border: 1px solid #ff0077;
                color: #ff0077;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 6px;
                border-radius: 2px;
            }
            QPushButton:checked {
                background: #ff0077;
                color: #000000;
            }
        """)
        self.chip_pl.clicked.connect(self.toggle_pl_clicked.emit)
        c_layout.addWidget(self.chip_pl)

        layout.addWidget(ctrl_bar)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos - self.pos()
            self.move(self.pos() + delta)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._is_dragging = False


class DirectionDModularApp(QWidget):
    """
    Main Modular Controller managing the Player Core, Visualizer Module,
    and Playlist Module with magnetic docking choreography.
    """
    SNAP_THRESHOLD = 30 # pixels

    def __init__(self):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, 1, 1) # Invisible manager anchor

        # 1. Create Compact Player Core
        self.core = CompactCorePlayer()
        self.core.move(250, 180)
        self.core.show()

        # 2. Create Visualizer Module
        self.vis_mod = VisualizerModule()
        self.vis_mod.dock_requested.connect(lambda m, edge: self.dock_module(m, "bottom"))
        self.vis_mod.undock_requested.connect(self.undock_module)
        self.vis_mod.closed_signal.connect(lambda m: self.core.chip_vis.setChecked(False))

        # 3. Create Playlist Module
        self.pl_mod = PlaylistModule()
        self.pl_mod.dock_requested.connect(lambda m, edge: self.dock_module(m, "right"))
        self.pl_mod.undock_requested.connect(self.undock_module)
        self.pl_mod.closed_signal.connect(lambda m: self.core.chip_pl.setChecked(False))

        # Track list for demonstration
        self.tracks = [
            ("Burn The World Waltz.mp3", "03:20"),
            ("dalezy-lotus_drei_remix.xm", "00:40"),
            ("08_sad_song.it", "03:19"),
            ("tubularbells-metal hr.mod", "01:55")
        ]
        self.pl_mod.populate(self.tracks)
        self.current_track_idx = 0

        # Wire Core Signals
        self.core.toggle_vis_clicked.connect(self._toggle_vis)
        self.core.toggle_pl_clicked.connect(self._toggle_pl)
        self.core.play_clicked.connect(self._on_play)
        self.core.pause_clicked.connect(self._on_pause)
        self.core.stop_clicked.connect(self._on_stop)
        self.core.next_clicked.connect(self._next_track)
        self.core.prev_clicked.connect(self._prev_track)
        self.pl_mod.track_selected.connect(self._select_track)

        # Simulation / Audio Frame Generation Timer (~60 FPS)
        self.is_playing = True
        self.playback_time = 0.0
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._tick)
        self.render_timer.start(16)

        # Magnetic Snap Monitor Timer (~30 FPS)
        self.snap_timer = QTimer(self)
        self.snap_timer.timeout.connect(self._check_magnetic_snapping)
        self.snap_timer.start(33)

    def _toggle_vis(self):
        if self.vis_mod.isVisible():
            self.vis_mod.hide()
            self.core.chip_vis.setChecked(False)
        else:
            self.dock_module(self.vis_mod, "bottom")
            self.vis_mod.show()
            self.core.chip_vis.setChecked(True)

    def _toggle_pl(self):
        if self.pl_mod.isVisible():
            self.pl_mod.hide()
            self.core.chip_pl.setChecked(False)
        else:
            self.dock_module(self.pl_mod, "right")
            self.pl_mod.show()
            self.core.chip_pl.setChecked(True)

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
        core_geom = self.core.geometry()

        # Realign Visualizer at Bottom of Core
        if self.vis_mod.is_docked and not self.vis_mod.is_fullscreen:
            self.vis_mod.move(core_geom.left(), core_geom.bottom() + 2)

        # Realign Playlist at Right of Core & Visualizer stack
        if self.pl_mod.is_docked:
            self.pl_mod.move(core_geom.right() + 2, core_geom.top())
            if self.vis_mod.is_docked and self.vis_mod.isVisible():
                self.pl_mod.setFixedHeight(core_geom.height() + self.vis_mod.height() + 2)
            else:
                self.pl_mod.setFixedHeight(core_geom.height())

    def _check_magnetic_snapping(self):
        """Monitors floating modules and performs snap-to-dock when near compatible edges."""
        if not self.core.isVisible():
            return

        core_geom = self.core.geometry()

        # Follow core movement if docked
        self.realign_docked_modules()

        # 1. Check Visualizer Bottom Proximity
        if not self.vis_mod.is_docked and self.vis_mod.isVisible() and not self.vis_mod.is_fullscreen:
            vis_geom = self.vis_mod.geometry()
            dx = abs(vis_geom.left() - core_geom.left())
            dy = abs(vis_geom.top() - (core_geom.bottom() + 2))
            if dx < self.SNAP_THRESHOLD and dy < self.SNAP_THRESHOLD:
                self.dock_module(self.vis_mod, "bottom")

        # 2. Check Playlist Right Proximity
        if not self.pl_mod.is_docked and self.pl_mod.isVisible():
            pl_geom = self.pl_mod.geometry()
            dx = abs(pl_geom.left() - (core_geom.right() + 2))
            dy = abs(pl_geom.top() - core_geom.top())
            if dx < self.SNAP_THRESHOLD and dy < self.SNAP_THRESHOLD:
                self.dock_module(self.pl_mod, "right")

    def _on_play(self):
        self.is_playing = True

    def _on_pause(self):
        self.is_playing = False

    def _on_stop(self):
        self.is_playing = False
        self.playback_time = 0.0

    def _select_track(self, index: int):
        self.current_track_idx = index
        title, _ = self.tracks[index]
        self.core.title_marquee.setText(f"♫ {index+1:02d}. {title}")
        self.pl_mod.set_current_index(index)
        self.playback_time = 0.0

    def _next_track(self):
        idx = (self.current_track_idx + 1) % len(self.tracks)
        self._select_track(idx)

    def _prev_track(self):
        idx = (self.current_track_idx - 1) % len(self.tracks)
        self._select_track(idx)

    def _tick(self):
        if self.is_playing:
            self.playback_time += 0.016

        # Update Time Display
        mins = int(self.playback_time // 60)
        secs = int(self.playback_time % 60)
        self.core.time_display.setText(f"{mins:02d}:{secs:02d} / 03:20")

        # Synthetic/Simulated AudioFrame reacting to time
        t = self.playback_time
        rms = (math.sin(t * 3.0) + 1.0) * 0.4 * (1.0 if self.is_playing else 0.0)
        bass = (math.sin(t * 5.0) + 1.0) * 0.45 * (1.0 if self.is_playing else 0.0)
        mids = (math.cos(t * 2.0) + 1.0) * 0.35 * (1.0 if self.is_playing else 0.0)
        treble = (math.sin(t * 8.0) + 1.0) * 0.25 * (1.0 if self.is_playing else 0.0)

        # Dynamic beat calculation
        is_beat = (math.sin(t * 6.28 * 2.1) > 0.8) and self.is_playing
        is_strong_beat = (math.sin(t * 6.28 * 1.05) > 0.92) and self.is_playing

        # Waveform synthetic buffer
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

        # Render Visualizer Module
        self.vis_mod.render_frame(frame, 0.016)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    manager = DirectionDModularApp()
    sys.exit(app.exec())
