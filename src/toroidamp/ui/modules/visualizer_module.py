"""
ToroidAMP - Production Visualizer Module
Hosts real-time visualizers (ToroidVisualizer, WaveformRibbonVisualizer)
with dynamic switching and RETINA MELT entry trigger.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedLayout
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QImage, QPixmap
import pygame

from .base import ModuleShell
from ..neon import NeonState
from ...analysis.audio_frame import AudioFrame


from ...visualizers.base import Visualizer
from ...visualizers.toroid import ToroidVisualizer
from ...visualizers.ribbon import WaveformRibbonVisualizer
from ...visualizers.deep_field import DeepFieldVisualizer
from ...visualizers.floor import ToroidAMPFloorVisualizer
from ...visualizers.toroid_identity import ToroidIdentityVisualizer


from ...visualizers.cyber_bloom import CyberBloomVisualizer
from ...visualizers.audio_reactive_reference import AudioReactiveReferenceVisualizer


class VisualizerModule(ModuleShell):
    """
    Dockable Visualizer Module hosting production visualizers
    with offscreen Pygame rendering and QPixmap surface transfer.
    """
    retina_melt_requested = Signal()

    # UX-003: default/min are stable product constants — not derived from
    # runtime geometry. 420x240 is the established production default;
    # 300x180 keeps the mode chip, MELT button, and titlebar all usable
    # while leaving a real render area.
    DEFAULT_SIZE = QSize(420, 240)
    MIN_SIZE = QSize(300, 180)
    DOCK_LOCKED_EDGES = {"left", "right"}  # docked VIS aligns its width to the chassis

    def __init__(self, parent=None):
        super().__init__("// MODULE :: VISUALIZER", parent)

        # Visualizer Surface Container Stack (Page 0: CPU Pixmap, Page 1: RETINA Placeholder)
        self.surface_stack = QStackedLayout()
        self.surface_stack.setContentsMargins(0, 0, 0, 0)

        # Page 0: CPU Canvas
        self.vis_label = QLabel(self)
        self.vis_label.setStyleSheet("background-color: #06070a; border: 1px solid #1a1d2e;")
        self.vis_label.setAlignment(Qt.AlignCenter)
        self.surface_stack.addWidget(self.vis_label)

        # Page 1: Deliberate Branded RETINA-only GPU Placeholder
        self.placeholder_widget = QWidget(self)
        self.placeholder_widget.setStyleSheet("background-color: #080910; border: 1px solid #1a1d2e;")
        p_layout = QVBoxLayout(self.placeholder_widget)
        p_layout.setContentsMargins(16, 16, 16, 16)
        p_layout.setSpacing(6)
        p_layout.setAlignment(Qt.AlignCenter)

        self.lbl_placeholder_name = QLabel("TOROID IDENTITY", self.placeholder_widget)
        self.lbl_placeholder_name.setStyleSheet("color: #00f0ff; font-family: monospace; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        self.lbl_placeholder_name.setAlignment(Qt.AlignCenter)
        p_layout.addWidget(self.lbl_placeholder_name)

        lbl_gpu_badge = QLabel("// HARDWARE GPU VISUALIZER //", self.placeholder_widget)
        lbl_gpu_badge.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 9px; font-weight: bold; border: none; background: transparent;")
        lbl_gpu_badge.setAlignment(Qt.AlignCenter)
        p_layout.addWidget(lbl_gpu_badge)

        lbl_avail = QLabel("Exclusive to RETINA MELT fullscreen playback.", self.placeholder_widget)
        lbl_avail.setStyleSheet("color: #7882a0; font-family: monospace; font-size: 9px; border: none; background: transparent;")
        lbl_avail.setAlignment(Qt.AlignCenter)
        p_layout.addWidget(lbl_avail)

        p_layout.addSpacing(6)

        self.btn_enter_retina = QPushButton("⛶ ENTER RETINA MELT", self.placeholder_widget)
        self.btn_enter_retina.setStyleSheet("""
            QPushButton {
                background: #141726;
                border: 1px solid #ff0077;
                color: #ff0077;
                font-family: monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 5px 14px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #ff0077;
                color: #ffffff;
            }
        """)
        self.btn_enter_retina.clicked.connect(self.retina_melt_requested.emit)
        p_layout.addWidget(self.btn_enter_retina, alignment=Qt.AlignCenter)

        self.surface_stack.addWidget(self.placeholder_widget)
        self.main_layout.addLayout(self.surface_stack, stretch=1)

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

        self.apply_theme(self._current_theme)

    def apply_theme(self, theme: ThemeDefinition):
        """Applies theme to visualizer module chrome and placeholder."""
        super().apply_theme(theme)
        pal = theme.palette
        typo = theme.typography

        disp_font = f"'{typo.display_family}', monospace"
        mono_font = f"'{typo.monospace_family}', monospace"

        self.vis_label.setStyleSheet(f"background-color: {pal.bg_lcd}; border: 1px solid {pal.border_panel};")
        self.placeholder_widget.setStyleSheet(f"background-color: {pal.bg_surface}; border: 1px solid {pal.border_panel};")
        self.lbl_placeholder_name.setStyleSheet(f"color: {pal.primary}; font-family: {disp_font}; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        self.btn_enter_retina.setStyleSheet(f"""
            QPushButton {{
                background: {pal.bg_surface_alt};
                border: 1px solid {pal.accent};
                color: {pal.accent};
                font-family: {mono_font};
                font-size: 10px;
                font-weight: bold;
                padding: 5px 14px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {pal.accent};
                color: #ffffff;
            }}
        """)

        self.btn_switch.setStyleSheet(f"""
            QPushButton {{
                background: {pal.bg_control};
                border: 1px solid {pal.border_control};
                color: {pal.primary};
                font-family: {mono_font};
                font-size: 9px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                background: {pal.primary};
                color: {pal.bg_lcd};
            }}
        """)

        self.btn_fs.setStyleSheet(f"""
            QPushButton {{
                background: {pal.bg_control};
                border: 1px solid {pal.border_control};
                color: {pal.accent};
                font-family: {mono_font};
                font-size: 9px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                background: {pal.accent};
                color: #ffffff;
            }}
        """)

        # Pygame Offscreen Engine — sized from the actual current viewport
        if not hasattr(self, "visualizers") or not self.visualizers:
            pygame.init()
            self.main_layout.activate()
            init_size = self.vis_label.size()
            self.surf_w = max(10, init_size.width())
            self.surf_h = max(10, init_size.height())
            self.surface = pygame.Surface((self.surf_w, self.surf_h))
            self.visualizers: list[Visualizer] = [
                ToroidVisualizer(self.surf_w, self.surf_h),
                WaveformRibbonVisualizer(self.surf_w, self.surf_h),
                DeepFieldVisualizer(self.surf_w, self.surf_h),
                ToroidAMPFloorVisualizer(self.surf_w, self.surf_h),
                ToroidIdentityVisualizer(self.surf_w, self.surf_h),
                CyberBloomVisualizer(self.surf_w, self.surf_h),
                AudioReactiveReferenceVisualizer(self.surf_w, self.surf_h),
            ]
            self._vis_idx = 0
            self.sync_visualizer_presentation()

    @property
    def vis_idx(self) -> int:
        return self._vis_idx

    @vis_idx.setter
    def vis_idx(self, idx: int):
        self._vis_idx = idx % len(self.visualizers)
        self.sync_visualizer_presentation()

    @property
    def current_visualizer(self) -> Visualizer:
        return self.visualizers[self._vis_idx]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_surface_size()

    def _sync_surface_size(self):
        """Keeps the offscreen render target matched to the current viewport size."""
        size = self.vis_label.size()
        w, h = max(10, size.width()), max(10, size.height())
        if w == self.surf_w and h == self.surf_h:
            return
        self.surf_w, self.surf_h = w, h
        self.surface = pygame.Surface((self.surf_w, self.surf_h))
        for vis in self.visualizers:
            vis.resize(self.surf_w, self.surf_h)

    def sync_visualizer_presentation(self):
        """Authoritative single source of truth for visualizer presentation state."""
        vis = self.current_visualizer
        name = vis.get_name().upper()
        self.btn_switch.setText(f"MODE: {name}")

        is_retina_only = getattr(vis, "is_retina_only", lambda: False)() or getattr(vis, "is_gpu", lambda: False)()
        if is_retina_only:
            self.lbl_placeholder_name.setText(name)
            self.surface_stack.setCurrentIndex(1)
        else:
            self.surface_stack.setCurrentIndex(0)

    # Alias for backward compatibility
    _update_presentation_mode = sync_visualizer_presentation

    def _switch_vis_mode(self):
        self.vis_idx = self._vis_idx + 1

    def render_frame(self, frame: AudioFrame, dt: float):
        if not self.isVisible():
            return
        vis = self.current_visualizer
        is_retina_only = getattr(vis, "is_retina_only", lambda: False)() or getattr(vis, "is_gpu", lambda: False)()
        if is_retina_only:
            # Under RETINA-only policy, do not spin software renderer for GPU visualizers
            return

        try:
            self.surface.fill((6, 7, 10))
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
        self.placeholder_widget.setStyleSheet(f"background-color: #080910; border: 1px solid {p_col}; border-radius: 2px;")
        self.title_label.setStyleSheet(f"color: {c_col}; font-family: monospace; font-size: 10px; font-weight: bold;")

