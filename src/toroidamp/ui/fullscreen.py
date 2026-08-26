"""
ToroidAMP - Production Fullscreen Experience Window (RETINA MELT)
Manages full display takeover, auto-hiding overlay HUD, and native resolution visualizer rendering.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QMouseEvent, QKeyEvent, QGuiApplication
import pygame

from ..analysis.audio_frame import AudioFrame
from ..visualizers.base import Visualizer
from ..visualizers.toroid import ToroidVisualizer
from ..visualizers.ribbon import WaveformRibbonVisualizer


class RetinaMeltWindow(QWidget):
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

        # Fullscreen Visualizer Surface Label
        self.vis_label = QLabel(self)
        self.vis_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.vis_label)

        # Floating Overlay Control Bar (Bottom Center HUD)
        self.hud = QFrame(self)
        self.hud.setFixedHeight(48)
        self.hud.setFixedWidth(540)
        self.hud.setStyleSheet("""
            QFrame {
                background-color: rgba(10, 11, 16, 220);
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
            QPushButton:hover { background-color: #00f0ff; color: #000000; }
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

        self.hud_title = QLabel("♫ No Track Loaded", self.hud)
        self.hud_title.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 11px; font-weight: bold; background: transparent; border: none;")
        h_layout.addWidget(self.hud_title, stretch=2)

        self.hud_time = QLabel("00:00 / 00:00", self.hud)
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
            QPushButton:hover { background-color: #ff0077; color: #ffffff; }
        """)
        btn_exit.clicked.connect(self.exit_requested.emit)
        h_layout.addWidget(btn_exit)

        # Pygame Fullscreen Render Engine
        pygame.init()
        self.surf_w, self.surf_h = 1920, 1080
        self.surface = pygame.Surface((self.surf_w, self.surf_h))
        self.visualizers: list[Visualizer] = [
            ToroidVisualizer(self.surf_w, self.surf_h),
            WaveformRibbonVisualizer(self.surf_w, self.surf_h)
        ]
        self.vis_idx = 0

        # Auto-Hide Timer (2.5s mouse inactivity)
        self.hud_timer = QTimer(self)
        self.hud_timer.timeout.connect(self._hide_hud)
        self.hud_timer.start(2500)

        self.setMouseTracking(True)
        self.vis_label.setMouseTracking(True)

    def set_visualizer_index(self, index: int):
        self.vis_idx = index % len(self.visualizers)
        self.visualizers[self.vis_idx].resize(self.surf_w, self.surf_h)

    def show_fullscreen_experience(self):
        screen_geom = QGuiApplication.primaryScreen().geometry()
        self.surf_w = screen_geom.width()
        self.surf_h = screen_geom.height()
        self.surface = pygame.Surface((self.surf_w, self.surf_h))
        self.visualizers[self.vis_idx].resize(self.surf_w, self.surf_h)
        
        self.setGeometry(screen_geom)
        self.hud.move((self.surf_w - self.hud.width()) // 2, self.surf_h - 70)
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
        else:
            super().keyPressEvent(event)

    def update_telemetry(self, title: str, time_str: str, is_playing: bool):
        self.hud_title.setText(title)
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
