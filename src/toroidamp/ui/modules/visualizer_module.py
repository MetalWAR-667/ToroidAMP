"""
ToroidAMP - Production Visualizer Module
Hosts real-time visualizers (ToroidVisualizer, WaveformRibbonVisualizer)
with dynamic switching and RETINA MELT entry trigger.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
import pygame

from .base import ModuleShell
from ..neon import NeonState
from ...analysis.audio_frame import AudioFrame


from ...visualizers.base import Visualizer
from ...visualizers.toroid import ToroidVisualizer
from ...visualizers.ribbon import WaveformRibbonVisualizer


class VisualizerModule(ModuleShell):
    """
    Dockable Visualizer Module hosting production visualizers
    with offscreen Pygame rendering and QPixmap surface transfer.
    """
    retina_melt_requested = Signal()

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
        self.btn_switch.setStyleSheet("""
            QPushButton {
                background: #141622;
                border: 1px solid #222638;
                color: #00f0ff;
                font-family: monospace;
                font-size: 9px;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background: #00f0ff;
                color: #000000;
            }
        """)
        self.btn_switch.clicked.connect(self._switch_vis_mode)
        b_layout.addWidget(self.btn_switch)

        b_layout.addStretch()

        self.btn_fs = QPushButton("⛶ MELT", bot_bar)
        self.btn_fs.setStyleSheet("""
            QPushButton {
                background: #141622;
                border: 1px solid #3d1f2e;
                color: #ff0077;
                font-family: monospace;
                font-size: 9px;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background: #ff0077;
                color: #ffffff;
            }
        """)
        self.btn_fs.clicked.connect(self.retina_melt_requested.emit)
        b_layout.addWidget(self.btn_fs)

        self.main_layout.addWidget(bot_bar)

        # Pygame Offscreen Engine
        pygame.init()
        self.surf_w, self.surf_h = 412, 185
        self.surface = pygame.Surface((self.surf_w, self.surf_h))
        self.visualizers: list[Visualizer] = [
            ToroidVisualizer(self.surf_w, self.surf_h),
            WaveformRibbonVisualizer(self.surf_w, self.surf_h)
        ]
        self.vis_idx = 0

    @property
    def current_visualizer(self) -> Visualizer:
        return self.visualizers[self.vis_idx]

    def _switch_vis_mode(self):
        self.vis_idx = (self.vis_idx + 1) % len(self.visualizers)
        name = self.visualizers[self.vis_idx].get_name().upper()
        self.btn_switch.setText(f"MODE: {name}")

    def render_frame(self, frame: AudioFrame, dt: float):
        if not self.isVisible():
            return
        try:
            self.surface.fill((6, 7, 10))
            vis = self.visualizers[self.vis_idx]
            vis.render(self.surface, frame, dt)
            
            raw_data = pygame.image.tobytes(self.surface, "RGBA")
            qimg = QImage(raw_data, self.surf_w, self.surf_h, QImage.Format.Format_RGBA8888)
            self.vis_label.setPixmap(QPixmap.fromImage(qimg))
        except Exception as e:
            # Failure isolation: render bug must never crash playback
            pass

    def apply_neon_state(self, state: NeonState):
        """Propagates spectral neon palette to module border, inner visualizer frame, and header."""
        super().apply_neon_state(state)
        p_col = state.tier2_panel_color.name()
        c_col = state.tier1_chassis_color.name()

        # Update visualizer viewport inner border
        self.vis_label.setStyleSheet(f"background-color: #06070a; border: 1px solid {p_col}; border-radius: 2px;")
        self.title_label.setStyleSheet(f"color: {c_col}; font-family: monospace; font-size: 10px; font-weight: bold;")

