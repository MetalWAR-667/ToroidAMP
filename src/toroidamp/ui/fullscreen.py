"""
ToroidAMP - Production Fullscreen Experience Window (RETINA MELT)
Manages full display takeover, auto-hiding overlay HUD, canonical Marquee track title,
seek timeline slider, volume control, in-fullscreen visualizer cycling, and native resolution rendering.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSlider
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QMouseEvent, QKeyEvent, QGuiApplication
import pygame

from ..analysis.audio_frame import AudioFrame
from ..visualizers.base import Visualizer
from ..visualizers.toroid import ToroidVisualizer
from ..visualizers.ribbon import WaveformRibbonVisualizer
from ..visualizers.deep_field import DeepFieldVisualizer
from ..visualizers.floor import ToroidAMPFloorVisualizer
from .marquee import MarqueeLabel
from .chassis import SeekSlider


class RetinaMeltWindow(QWidget):
    """
    RETINA MELT: Fullscreen Visualizer Experience with Auto-Hiding Playback Controls,
    Canonical Marquee Title, Direct Seek Timeline, Visualizer Mode Cycling, and Volume Adjustment.
    """
    exit_requested = Signal()
    play_toggled = Signal()
    prev_clicked = Signal()
    next_clicked = Signal()
    volume_changed = Signal(float)
    visualizer_switched = Signal(int)
    seek_changed = Signal(int)  # 0..1000 permille value

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: #000000;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Fullscreen Visualizer Surface Label
        self.vis_label = QLabel(self)
        self.vis_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.vis_label)

        # Floating Overlay Control Bar (Two-Row Bottom HUD)
        self.hud = QFrame(self)
        self.hud.setFixedHeight(76)
        self.hud.setFixedWidth(780)
        self.hud.setStyleSheet("""
            QFrame#retina_hud {
                background-color: rgba(10, 11, 16, 235);
                border: 1px solid #00f0ff;
                border-radius: 6px;
            }
        """)
        self.hud.setObjectName("retina_hud")

        hud_layout = QVBoxLayout(self.hud)
        hud_layout.setContentsMargins(12, 6, 12, 6)
        hud_layout.setSpacing(4)

        # --- ROW 1: Marquee Track Title & Time ---
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(8)

        self.hud_marquee = MarqueeLabel(self.hud)
        self.hud_marquee.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 11px; font-weight: bold; background: transparent; border: none;")
        self.hud_marquee.set_marquee_text("♫ No Track Loaded")
        row1.addWidget(self.hud_marquee, stretch=3)

        self.hud_time = QLabel("00:00 / 00:00", self.hud)
        self.hud_time.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 10px; background: transparent; border: none;")
        self.hud_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row1.addWidget(self.hud_time, stretch=1)

        hud_layout.addLayout(row1)

        # --- ROW 2: Transport | Seek Timeline | Volume | Mode | Exit ---
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(6)

        hud_btn_style = """
            QPushButton {
                background-color: #141724;
                border: 1px solid #00f0ff;
                border-radius: 3px;
                color: #00f0ff;
                font-family: monospace;
                font-weight: bold;
                font-size: 11px;
                padding: 3px 6px;
            }
            QPushButton:hover { background-color: #00f0ff; color: #000000; }
        """
        btn_prev = QPushButton("◄◄", self.hud)
        btn_prev.setStyleSheet(hud_btn_style)
        btn_prev.clicked.connect(self.prev_clicked.emit)
        row2.addWidget(btn_prev)

        self.hud_btn_play = QPushButton("►", self.hud)
        self.hud_btn_play.setStyleSheet(hud_btn_style)
        self.hud_btn_play.clicked.connect(self.play_toggled.emit)
        row2.addWidget(self.hud_btn_play)

        btn_next = QPushButton("►►", self.hud)
        btn_next.setStyleSheet(hud_btn_style)
        btn_next.clicked.connect(self.next_clicked.emit)
        row2.addWidget(btn_next)

        # Seek Timeline Slider (Canonical SeekSlider)
        self.hud_seek_slider = SeekSlider(Qt.Horizontal, self.hud)
        self.hud_seek_slider.setRange(0, 1000)
        self.hud_seek_slider.setValue(0)
        self.hud_seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #141724;
                border: 1px solid #222638;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #ffaa00;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #ffaa00;
                width: 8px;
                margin-top: -3px;
                margin-bottom: -3px;
                border-radius: 4px;
            }
        """)
        self.hud_seek_slider.sliderMoved.connect(self.seek_changed.emit)
        row2.addWidget(self.hud_seek_slider, stretch=2)

        # Volume Controls
        vol_label = QLabel("VOL", self.hud)
        vol_label.setStyleSheet("color: #00f0ff; font-family: monospace; font-size: 9px; font-weight: bold; background: transparent; border: none;")
        row2.addWidget(vol_label)

        self.hud_slider_vol = QSlider(Qt.Horizontal, self.hud)
        self.hud_slider_vol.setRange(0, 100)
        self.hud_slider_vol.setValue(80)
        self.hud_slider_vol.setFixedWidth(55)
        self.hud_slider_vol.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #141724;
                border: 1px solid #222638;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #00f0ff;
                border-radius: 2px;
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
        self.hud_slider_vol.valueChanged.connect(self._on_vol_slider_changed)
        row2.addWidget(self.hud_slider_vol)

        # Visualizer Mode Selector Button
        self.hud_btn_mode = QPushButton("MODE: 3D TORUS", self.hud)
        self.hud_btn_mode.setStyleSheet("""
            QPushButton {
                background-color: #141724;
                border: 1px solid #00f0ff;
                border-radius: 3px;
                color: #00f0ff;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 6px;
            }
            QPushButton:hover { background-color: #00f0ff; color: #000000; }
        """)
        self.hud_btn_mode.clicked.connect(self._cycle_visualizer_mode)
        row2.addWidget(self.hud_btn_mode)

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
                padding: 3px 6px;
            }
            QPushButton:hover { background-color: #ff0077; color: #ffffff; }
        """)
        btn_exit.clicked.connect(self.exit_requested.emit)
        row2.addWidget(btn_exit)

        hud_layout.addLayout(row2)

        # Pygame Fullscreen Render Engine
        pygame.init()
        self.surf_w, self.surf_h = 1920, 1080
        self.surface = pygame.Surface((self.surf_w, self.surf_h))
        self.visualizers: list[Visualizer] = [
            ToroidVisualizer(self.surf_w, self.surf_h),
            WaveformRibbonVisualizer(self.surf_w, self.surf_h),
            DeepFieldVisualizer(self.surf_w, self.surf_h),
            ToroidAMPFloorVisualizer(self.surf_w, self.surf_h),
        ]
        self.vis_idx = 0

        # Auto-Hide Timer (2.5s mouse inactivity)
        self.hud_timer = QTimer(self)
        self.hud_timer.timeout.connect(self._hide_hud)
        self.hud_timer.start(2500)

        self.setMouseTracking(True)
        self.vis_label.setMouseTracking(True)

    def _on_vol_slider_changed(self, value: int):
        self.volume_changed.emit(value / 100.0)

    def set_volume(self, volume: float):
        """Syncs volume slider without triggering feedback loops."""
        val = int(round(max(0.0, min(1.0, volume)) * 100.0))
        self.hud_slider_vol.blockSignals(True)
        self.hud_slider_vol.setValue(val)
        self.hud_slider_vol.blockSignals(False)

    def set_seek_position(self, current_sec: float, duration_sec: float):
        """Syncs seek slider position without triggering sliderMoved."""
        if not self.hud_seek_slider.isSliderDown() and duration_sec > 0.0:
            val = int((current_sec / duration_sec) * 1000.0)
            self.hud_seek_slider.blockSignals(True)
            self.hud_seek_slider.setValue(max(0, min(1000, val)))
            self.hud_seek_slider.blockSignals(False)

    def _cycle_visualizer_mode(self):
        """Advances to the next production visualizer in fullscreen."""
        self.vis_idx = (self.vis_idx + 1) % len(self.visualizers)
        self.visualizers[self.vis_idx].resize(self.surf_w, self.surf_h)
        self._update_mode_button_text()
        self.visualizer_switched.emit(self.vis_idx)

    def _update_mode_button_text(self):
        name = self.visualizers[self.vis_idx].get_name().upper()
        self.hud_btn_mode.setText(f"MODE: {name}")

    def set_visualizer_index(self, index: int):
        self.vis_idx = index % len(self.visualizers)
        self.visualizers[self.vis_idx].resize(self.surf_w, self.surf_h)
        self._update_mode_button_text()

    def show_fullscreen_experience(self):
        screen_geom = QGuiApplication.primaryScreen().geometry()
        self.surf_w = screen_geom.width()
        self.surf_h = screen_geom.height()
        self.surface = pygame.Surface((self.surf_w, self.surf_h))
        self.visualizers[self.vis_idx].resize(self.surf_w, self.surf_h)
        self._update_mode_button_text()
        
        self.setGeometry(screen_geom)
        self.hud.move((self.surf_w - self.hud.width()) // 2, self.surf_h - 95)
        self.hud.show()
        self.showFullScreen()

    def mouseMoveEvent(self, event: QMouseEvent):
        self.hud.show()
        self.hud_timer.start(2500)
        event.accept()

    def _hide_hud(self):
        self.hud.hide()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Escape, Qt.Key_F):
            self.exit_requested.emit()
        elif event.key() == Qt.Key_Space:
            self.play_toggled.emit()
        elif event.key() == Qt.Key_M:
            self._cycle_visualizer_mode()
        else:
            super().keyPressEvent(event)

    def update_telemetry(self, title: str, time_str: str, is_playing: bool):
        self.hud_marquee.set_marquee_text(title)
        self.hud_time.setText(time_str)
        self.hud_btn_play.setText("❚❚" if is_playing else "►")

    def render_frame(self, frame: AudioFrame, dt: float):
        if not self.isVisible():
            return
        try:
            self.surface.fill((0, 0, 0))
            vis = self.visualizers[self.vis_idx]
            vis.render(self.surface, frame, dt)
            raw_data = pygame.image.tobytes(self.surface, "RGBA")
            qimg = QImage(raw_data, self.surf_w, self.surf_h, QImage.Format.Format_RGBA8888)
            self.vis_label.setPixmap(QPixmap.fromImage(qimg))
        except Exception:
            pass
