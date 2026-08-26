"""
ToroidAMP - Foundation II Prototype Test Runner
Validates Dual-Source Audio Pipeline & Tracker PCM with PySide6 & Toroid
"""

import os
import sys
import time
import pygame
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSlider
)
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import QTimer, Qt

# Import prototype engine
from prototype_engine import DualEnginePlayer, Toroid3DVisualizer, AudioFrame


class ToroidAMPPrototypeWindow(QMainWindow):
    def __init__(self, modplug_dll: str, test_assets: dict[str, str]):
        super().__init__()
        self.setWindowTitle("ToroidAMP — Foundation II Dual-Source Audio & Toroid Prototype")
        self.resize(800, 680)

        self.test_assets = test_assets
        self.player = DualEnginePlayer(modplug_dll)
        
        # Pygame offscreen initialization
        pygame.init()
        self.vis_width = 780
        self.vis_height = 520
        self.surface = pygame.Surface((self.vis_width, self.vis_height))
        self.visualizer = Toroid3DVisualizer(self.vis_width, self.vis_height)

        # Performance monitoring
        self.last_render_time = time.perf_counter()
        self.frame_count = 0
        self.fps = 0.0
        self.last_fps_update = time.perf_counter()

        self._init_ui()

        # Render & Analysis Timer (~60 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_render_tick)
        self.timer.start(16)

    def _init_ui(self):
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Visualizer Surface Display
        self.vis_label = QLabel(self)
        self.vis_label.setFixedSize(self.vis_width, self.vis_height)
        self.vis_label.setStyleSheet("background-color: #0a0a12; border: 1px solid #00f0ff;")
        layout.addWidget(self.vis_label)

        # Telemetry / Status Bar
        self.status_label = QLabel("Ready. Select track and press Play.", self)
        self.status_label.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Controls Layout
        ctrl_layout = QHBoxLayout()

        # Track Selector
        self.track_combo = QComboBox(self)
        for name in self.test_assets.keys():
            self.track_combo.addItem(name)
        self.track_combo.currentTextChanged.connect(self._on_track_changed)
        ctrl_layout.addWidget(self.track_combo, stretch=2)

        # Play Button
        self.btn_play = QPushButton("Play", self)
        self.btn_play.clicked.connect(self._on_play)
        ctrl_layout.addWidget(self.btn_play)

        # Pause Button
        self.btn_pause = QPushButton("Pause", self)
        self.btn_pause.clicked.connect(self._on_pause)
        ctrl_layout.addWidget(self.btn_pause)

        # Stop Button
        self.btn_stop = QPushButton("Stop", self)
        self.btn_stop.clicked.connect(self._on_stop)
        ctrl_layout.addWidget(self.btn_stop)

        # Fullscreen Toggle Button
        self.btn_fs = QPushButton("Toggle Fullscreen", self)
        self.btn_fs.clicked.connect(self._on_toggle_fullscreen)
        ctrl_layout.addWidget(self.btn_fs)

        layout.addLayout(ctrl_layout)

        # Auto-load initial track
        first_track = list(self.test_assets.keys())[0]
        self.player.load_track(self.test_assets[first_track])

    def _on_track_changed(self, track_name: str):
        path = self.test_assets.get(track_name)
        if path and os.path.exists(path):
            self.player.load_track(path)
            self.status_label.setText(f"Loaded: {track_name} ({'Tracker Module' if self.player.is_tracker else 'Conventional Audio'})")

    def _on_play(self):
        self.player.play()
        self.status_label.setText(f"Playing: {self.track_combo.currentText()}")

    def _on_pause(self):
        self.player.pause()
        self.status_label.setText("Paused")

    def _on_stop(self):
        self.player.stop()
        self.status_label.setText("Stopped")

    def _on_toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_render_tick(self):
        now = time.perf_counter()
        dt = max(0.001, now - self.last_render_time)
        self.last_render_time = now

        # Frame counting
        self.frame_count += 1
        if now - self.last_fps_update >= 1.0:
            self.fps = self.frame_count / (now - self.last_fps_update)
            self.frame_count = 0
            self.last_fps_update = now

        # 1. Acquire normalized AudioFrame from PCM stream
        audio_frame = self.player.handoff.get_audio_frame(self.player.sr)

        # 2. Render Toroid 3D wireframe to offscreen Pygame surface
        self.surface.fill((10, 10, 18))
        self.visualizer.render(self.surface, audio_frame, dt)

        # 3. Transfer to PySide6 QPixmap
        raw_data = pygame.image.tobytes(self.surface, "RGBA")
        qimg = QImage(raw_data, self.vis_width, self.vis_height, QImage.Format.Format_RGBA8888)
        self.vis_label.setPixmap(QPixmap.fromImage(qimg))

        # 4. Update status display with live audio telemetry
        if self.player.is_playing:
            src_type = "TRACKER (libmodplug)" if self.player.is_tracker else "CONVENTIONAL (soundfile)"
            self.status_label.setText(
                f"[{src_type}] FPS: {self.fps:.1f} | RMS: {audio_frame.rms:.2f} | "
                f"Bass: {audio_frame.bass:.2f} | Mids: {audio_frame.mids:.2f} | "
                f"Beat: {'*BEAT*' if audio_frame.beat else '-'}"
            )

    def closeEvent(self, event):
        self.player.stop()
        event.accept()


if __name__ == "__main__":
    modplug_path = r"C:\Users\Usuario\AppData\Local\Programs\Python\Python313\Lib\site-packages\pygame\libmodplug-1.dll"
    
    assets = {
        "MP3: Burn The World Waltz": r"C:\ToroidAMP\ToroidAMP\tests\assets\audio\Burn The World Waltz.mp3",
        "MP3: Blast SFX": r"C:\ToroidAMP\Metalwar-Installer\blast.mp3",
        "OGG: Typewriter": r"C:\ToroidAMP\Metalwar-Installer\typewriter.ogg",
        "XM: Lotus Drei Remix": r"C:\ToroidAMP\Metalwar-Installer\dalezy-lotus_drei_remix.xm",
        "IT: Sad Song": r"C:\ToroidAMP\Metalwar-Installer\08_sad_song.it",
        "MOD: Tubular Bells": r"C:\ToroidAMP\Metalwar-Installer\tubularbells-metal hr.mod",
    }

    app = QApplication(sys.argv)
    window = ToroidAMPPrototypeWindow(modplug_path, assets)
    window.show()
    sys.exit(app.exec())
