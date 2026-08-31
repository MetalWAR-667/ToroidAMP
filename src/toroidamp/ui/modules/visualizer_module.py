"""
ToroidAMP - Production Visualizer Module
Hosts real-time visualizers (ToroidVisualizer, WaveformRibbonVisualizer)
plus official hardware GLSL visualizers, with dynamic switching and
RETINA MELT entry trigger.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedLayout
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QImage, QPixmap
import pygame

from .base import ModuleShell
from ..neon import NeonState
from ..theme import ThemeDefinition
from ...analysis.audio_frame import AudioFrame


from ...visualizers.base import Visualizer
from ...visualizers.toroid import ToroidVisualizer
from ...visualizers.ribbon import WaveformRibbonVisualizer
from ...visualizers.deep_field import DeepFieldVisualizer
from ...visualizers.floor import ToroidAMPFloorVisualizer
from ...visualizers.toroid_identity import ToroidIdentityVisualizer


from ...visualizers.cyber_bloom import CyberBloomVisualizer
from ...visualizers.audio_reactive_reference import AudioReactiveReferenceVisualizer
from ...visualizers.gpu_canvas import GLVisualizerCanvas


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

        # Visualizer Surface Container Stack (Page 0: CPU Pixmap, Page 1:
        # hardware GLSL canvas for official GPU visualizers). Page 1 shares
        # the exact same production GLVisualizerCanvas class RETINA MELT and
        # the GLSL Lab use -- no second GLSL renderer for NORMAL. Only
        # official, package-controlled shader paths (Visualizer.
        # get_shader_path()) are ever loaded here; NORMAL never exposes a
        # file picker or any other route to arbitrary user GLSL.
        self.surface_stack = QStackedLayout()
        self.surface_stack.setContentsMargins(0, 0, 0, 0)

        # Page 0: CPU Canvas
        self.vis_label = QLabel(self)
        self.vis_label.setStyleSheet("background-color: #06070a; border: 1px solid #1a1d2e;")
        self.vis_label.setAlignment(Qt.AlignCenter)
        self.surface_stack.addWidget(self.vis_label)

        # Page 1: Official GPU Visualizer Canvas
        self.gpu_canvas = GLVisualizerCanvas(self)
        self.surface_stack.addWidget(self.gpu_canvas)
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
        """Applies theme to visualizer module chrome."""
        super().apply_theme(theme)
        pal = theme.palette
        typo = theme.typography

        mono_font = f"'{typo.monospace_family}', monospace"

        self.vis_label.setStyleSheet(f"background-color: {pal.bg_lcd}; border: 1px solid {pal.border_panel};")

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
        """
        Authoritative single source of truth for visualizer presentation
        state. GPU visualizers load their official shader onto the shared
        production GLVisualizerCanvas and switch to the GL page; on a
        missing/failed shader they fall back to the same visualizer
        descriptor's own CPU render() (already implemented on every
        official GPU visualizer for exactly this case) rather than a
        placeholder — the surface_stack page always reflects what is
        actually rendering, mirroring RETINA MELT's _apply_visualizer_selection.
        """
        vis = self.current_visualizer
        name = vis.get_name().upper()
        self.btn_switch.setText(f"MODE: {name}")

        is_gpu = getattr(vis, "is_gpu", lambda: False)()
        if is_gpu:
            shader_path = getattr(vis, "get_shader_path", lambda: None)()
            if shader_path and shader_path.exists():
                # Show the canvas before loading: on platforms where a
                # hidden QOpenGLWidget's context isn't realized until shown
                # (observed on Linux/X11), loading before switching pages
                # silently defers compilation instead of running it now
                # (GLSL-002). Matches RETINA MELT's already-correct order.
                self.surface_stack.setCurrentIndex(1)
                ok = self.gpu_canvas.load_shader_file(shader_path)
                if not ok:
                    self.surface_stack.setCurrentIndex(0)
            else:
                self.surface_stack.setCurrentIndex(0)
        else:
            self.surface_stack.setCurrentIndex(0)

    # Alias for backward compatibility
    _update_presentation_mode = sync_visualizer_presentation

    def _switch_vis_mode(self):
        self.vis_idx = self._vis_idx + 1

    def render_frame(self, frame: AudioFrame, dt: float):
        if not self.isVisible():
            return

        if self.surface_stack.currentIndex() == 1:
            # Official GPU visualizer: same production AudioFrame contract
            # RETINA MELT uses, so volume-independent reactivity (v0.666)
            # and beat semantics are identical here, not a parallel path.
            self.gpu_canvas.update_audio_frame(frame)
            self.gpu_canvas.update()
            return

        vis = self.current_visualizer
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
        self.title_label.setStyleSheet(f"color: {c_col}; font-family: monospace; font-size: 10px; font-weight: bold;")

