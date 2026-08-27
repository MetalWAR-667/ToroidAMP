"""
ToroidAMP - Production Fullscreen Experience Window (RETINA MELT)
Manages full display takeover, explicit HUD visibility state machine (HUD_HIDDEN / HUD_VISIBLE / HUD_PINNED),
canonical Marquee track title, seek timeline slider, volume control, in-fullscreen visualizer cycling,
hardware-accelerated GPU visualizers, dynamic live visual parameter [ TUNE ] controls,
Integrated Shader Authoring [ LAB ] surface, and robust re-entry.
"""

from pathlib import Path
from typing import Dict, List, Optional
import json
import pygame
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage, QKeyEvent, QMouseEvent, QPixmap, QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QScrollArea,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from ..analysis.audio_frame import AudioFrame
from ..session import SessionManager
from ..visualizers.base import Visualizer
from ..visualizers.deep_field import DeepFieldVisualizer
from ..visualizers.floor import ToroidAMPFloorVisualizer
from ..visualizers.gpu_canvas import GLVisualizerCanvas
from ..visualizers.gpu_compiler import (
    hex_to_rgb_normalized,
    create_shader_preset,
    parse_and_apply_preset
)
from ..visualizers.ribbon import WaveformRibbonVisualizer
from ..visualizers.toroid import ToroidVisualizer
from ..visualizers.toroid_identity import ToroidIdentityVisualizer
from ..visualizers.cyber_bloom import CyberBloomVisualizer
from .chassis import SeekSlider
from .marquee import MarqueeLabel
COLOR_DIALOG_STYLESHEET = """
    QColorDialog {
        background-color: #121520;
    }
    QLabel {
        color: #e0e6f0;
        font-family: monospace;
        font-size: 10px;
    }
    QLineEdit, QSpinBox {
        background-color: #181c2c;
        color: #00f0ff;
        border: 1px solid #2a324b;
        border-radius: 3px;
        padding: 2px 4px;
        font-family: monospace;
        font-size: 10px;
    }
    QPushButton {
        background-color: #1a1f30;
        color: #00f0ff;
        border: 1px solid #00f0ff;
        border-radius: 3px;
        padding: 4px 10px;
        font-family: monospace;
        font-weight: bold;
        font-size: 10px;
    }
    QPushButton:hover {
        background-color: #00f0ff;
        color: #000000;
    }
    QPushButton:pressed {
        background-color: #00b3cc;
        color: #000000;
    }
"""


def _open_styled_color_dialog(initial_color: QColor, parent: Optional[QWidget] = None, title: str = "Select Color") -> Optional[QColor]:
    """Opens a QColorDialog styled with ToroidAMP's dark cyberpunk palette to guarantee high-contrast readability."""
    dlg = QColorDialog(initial_color, parent)
    dlg.setWindowTitle(title)
    dlg.setStyleSheet(COLOR_DIALOG_STYLESHEET)
    if dlg.exec() == QColorDialog.Accepted:
        return dlg.selectedColor()
    return None


class RetinaMeltWindow(QWidget):
    """
    RETINA MELT: Fullscreen Visualizer Experience with Explicit Control State Machine:
      - HUD_PINNED  : Left click on background pins HUD permanently visible until right click.
      - HUD_VISIBLE : Transient mouse movement shows HUD with 2.5s inactivity timer.
      - HUD_HIDDEN  : Right click hides HUD, closes TUNE, and closes LAB immediately.
      - Auto-hide is completely suspended while [ TUNE ] or [ LAB ] panels are active.
      - Mutual exclusivity: TUNE and LAB are mutually exclusive overlays sharing one parameter state.
    """

    exit_requested = Signal()
    play_toggled = Signal()
    prev_clicked = Signal()
    next_clicked = Signal()
    volume_changed = Signal(float)
    visualizer_switched = Signal(int)
    seek_changed = Signal(int)  # 0..1000 permille value
    parameters_changed = Signal(str, dict)  # vis_id, params

    def __init__(self, session_manager: Optional[SessionManager] = None, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: #000000;")
        self.session_manager = session_manager

        # Local shader tracking for current session
        self._local_shader_path: Optional[Path] = None
        self._local_shader_active = False

        # Root layout holding the stacked visualizer surface and floating HUD
        self.root_stack = QStackedLayout(self)
        self.root_stack.setStackingMode(QStackedLayout.StackAll)
        self.root_stack.setContentsMargins(0, 0, 0, 0)

        # 1. Surface Display Stack (Index 0: CPU Pixmap, Index 1: Hardware GPU QOpenGLWidget)
        self.surface_container = QWidget(self)
        self.surface_layout = QStackedLayout(self.surface_container)
        self.surface_layout.setContentsMargins(0, 0, 0, 0)

        self.vis_label = QLabel(self.surface_container)
        self.vis_label.setStyleSheet("background-color: #000000;")
        self.vis_label.setAlignment(Qt.AlignCenter)
        self.surface_layout.addWidget(self.vis_label)

        self.gpu_canvas = GLVisualizerCanvas(self.surface_container)
        self.surface_layout.addWidget(self.gpu_canvas)

        self.root_stack.addWidget(self.surface_container)

        # 2. Floating Cyberpunk HUD Overlay Container
        self.hud = QFrame(self)
        self.hud.setFixedSize(680, 84)
        self.hud.setStyleSheet(
            """
            QFrame#retina_hud {
                background-color: rgba(10, 11, 16, 230);
                border: 1px solid #00f0ff;
                border-radius: 6px;
            }
        """
        )
        self.hud.setObjectName("retina_hud")

        hud_layout = QVBoxLayout(self.hud)
        hud_layout.setContentsMargins(12, 6, 12, 6)
        hud_layout.setSpacing(4)

        # Top Row: Marquee Title + Time
        row1 = QHBoxLayout()
        self.hud_marquee = MarqueeLabel(self.hud)
        self.hud_marquee.set_marquee_text("TOROIDAMP // RETINA MELT")
        self.hud_marquee.setStyleSheet(
            "color: #00f0ff; font-family: monospace; font-size: 11px; font-weight: bold; background: transparent;"
        )
        row1.addWidget(self.hud_marquee, stretch=1)

        self.hud_time = QLabel("00:00 / 00:00", self.hud)
        self.hud_time.setStyleSheet(
            "color: #7882a0; font-family: monospace; font-size: 10px; background: transparent;"
        )
        row1.addWidget(self.hud_time)
        hud_layout.addLayout(row1)

        # Middle Row: Seek Timeline Slider
        self.hud_seek_slider = SeekSlider(Qt.Horizontal, self.hud)
        self.hud_seek_slider.setRange(0, 1000)
        self.hud_seek_slider.sliderMoved.connect(self.seek_changed.emit)
        hud_layout.addWidget(self.hud_seek_slider)

        # Bottom Row: Transport Controls, Volume, Mode, TUNE, LAB, Exit
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        btn_prev = QPushButton("⏮", self.hud)
        btn_prev.setFixedSize(28, 22)
        btn_prev.setStyleSheet(
            """
            QPushButton {
                background-color: #141724;
                border: 1px solid #222638;
                border-radius: 3px;
                color: #ffffff;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #00f0ff; color: #000000; }
        """
        )
        btn_prev.clicked.connect(self.prev_clicked.emit)
        row2.addWidget(btn_prev)

        self.hud_btn_play = QPushButton("►", self.hud)
        self.hud_btn_play.setFixedSize(28, 22)
        self.hud_btn_play.setStyleSheet(
            """
            QPushButton {
                background-color: #141724;
                border: 1px solid #00f0ff;
                border-radius: 3px;
                color: #00f0ff;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #00f0ff; color: #000000; }
        """
        )
        self.hud_btn_play.clicked.connect(self.play_toggled.emit)
        row2.addWidget(self.hud_btn_play)

        btn_next = QPushButton("⏭", self.hud)
        btn_next.setFixedSize(28, 22)
        btn_next.setStyleSheet(
            """
            QPushButton {
                background-color: #141724;
                border: 1px solid #222638;
                border-radius: 3px;
                color: #ffffff;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #00f0ff; color: #000000; }
        """
        )
        btn_next.clicked.connect(self.next_clicked.emit)
        row2.addWidget(btn_next)

        row2.addSpacing(6)

        # Volume Slider in HUD
        lbl_vol = QLabel("VOL", self.hud)
        lbl_vol.setStyleSheet(
            "color: #7882a0; font-family: monospace; font-size: 9px; font-weight: bold; background: transparent;"
        )
        row2.addWidget(lbl_vol)

        self.hud_slider_vol = QSlider(Qt.Horizontal, self.hud)
        self.hud_slider_vol.setRange(0, 100)
        self.hud_slider_vol.setValue(100)
        self.hud_slider_vol.setFixedWidth(64)
        self.hud_slider_vol.setStyleSheet(
            """
            QSlider::groove:horizontal { height: 4px; background: #141724; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #00f0ff; border-radius: 2px; }
            QSlider::handle:horizontal { background: #ffffff; width: 8px; margin: -2px 0; border-radius: 4px; }
        """
        )
        self.hud_slider_vol.valueChanged.connect(self._on_vol_slider_changed)
        row2.addWidget(self.hud_slider_vol)

        # Visualizer Mode Selector Button
        self.hud_btn_mode = QPushButton("MODE: 3D TORUS", self.hud)
        self.hud_btn_mode.setStyleSheet(
            """
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
        """
        )
        self.hud_btn_mode.clicked.connect(self._cycle_visualizer_mode)
        row2.addWidget(self.hud_btn_mode)

        # [ TUNE ] Button
        self.hud_btn_tune = QPushButton("⚙ TUNE", self.hud)
        self.hud_btn_tune.setCheckable(True)
        self.hud_btn_tune.setStyleSheet(
            """
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
            QPushButton:checked { background-color: #00f0ff; color: #000000; }
        """
        )
        self.hud_btn_tune.clicked.connect(self._toggle_tune_panel)
        row2.addWidget(self.hud_btn_tune)

        # [ LAB ] Button
        self.hud_btn_lab = QPushButton("⚗ LAB", self.hud)
        self.hud_btn_lab.setCheckable(True)
        self.hud_btn_lab.setStyleSheet(
            """
            QPushButton {
                background-color: #1a1628;
                border: 1px solid #ffaa00;
                border-radius: 3px;
                color: #ffaa00;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 6px;
            }
            QPushButton:hover { background-color: #ffaa00; color: #000000; }
            QPushButton:checked { background-color: #ffaa00; color: #000000; }
        """
        )
        self.hud_btn_lab.clicked.connect(self._toggle_lab_panel)
        row2.addWidget(self.hud_btn_lab)

        btn_exit = QPushButton("✕ EXIT (ESC)", self.hud)
        btn_exit.setStyleSheet(
            """
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
        """
        )
        btn_exit.clicked.connect(self.exit_requested.emit)
        row2.addWidget(btn_exit)

        hud_layout.addLayout(row2)

        # --- Dynamic TUNE Overlay Panel ---
        self.tune_panel = QFrame(self)
        self.tune_panel.setFixedWidth(320)
        self.tune_panel.setStyleSheet(
            """
            QFrame#retina_tune {
                background-color: rgba(10, 11, 16, 245);
                border: 1px solid #00f0ff;
                border-radius: 6px;
            }
        """
        )
        self.tune_panel.setObjectName("retina_tune")
        self.tune_panel.hide()

        self.tune_layout = QVBoxLayout(self.tune_panel)
        self.tune_layout.setContentsMargins(12, 10, 12, 10)
        self.tune_layout.setSpacing(6)

        # Tune Header
        tune_header = QHBoxLayout()
        lbl_tune_title = QLabel("// VISUALIZER TUNE", self.tune_panel)
        lbl_tune_title.setStyleSheet(
            "color: #00f0ff; font-family: monospace; font-size: 11px; font-weight: bold; background: transparent; border: none;"
        )
        tune_header.addWidget(lbl_tune_title)
        tune_header.addStretch()

        btn_reset_tune = QPushButton("↺ RESET", self.tune_panel)
        btn_reset_tune.setStyleSheet(
            """
            QPushButton {
                background-color: #141724;
                border: 1px solid #ffaa00;
                border-radius: 3px;
                color: #ffaa00;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 2px 6px;
            }
            QPushButton:hover { background-color: #ffaa00; color: #000000; }
        """
        )
        btn_reset_tune.clicked.connect(self._reset_tune_parameters)
        tune_header.addWidget(btn_reset_tune)

        btn_close_tune = QPushButton("✕", self.tune_panel)
        btn_close_tune.setStyleSheet(
            """
            QPushButton {
                background-color: #24141d;
                border: 1px solid #ff0077;
                border-radius: 3px;
                color: #ff0077;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 2px 5px;
            }
            QPushButton:hover { background-color: #ff0077; color: #ffffff; }
        """
        )
        btn_close_tune.clicked.connect(self._close_tune_panel)
        tune_header.addWidget(btn_close_tune)

        self.tune_layout.addLayout(tune_header)

        # Dynamic Controls Container inside Tune Panel
        self.tune_controls_widget = QWidget(self.tune_panel)
        self.tune_controls_layout = QVBoxLayout(self.tune_controls_widget)
        self.tune_controls_layout.setContentsMargins(0, 4, 0, 0)
        self.tune_controls_layout.setSpacing(4)
        self.tune_layout.addWidget(self.tune_controls_widget)

        self._param_sliders: Dict[str, QSlider] = {}
        self._param_val_labels: Dict[str, QLabel] = {}

        # --- Dynamic Integrated LAB Overlay Panel ---
        self.lab_panel = QFrame(self)
        self.lab_panel.setFixedWidth(340)
        self.lab_panel.setStyleSheet(
            """
            QFrame#retina_lab {
                background-color: rgba(10, 11, 18, 248);
                border: 1px solid #ffaa00;
                border-radius: 6px;
            }
        """
        )
        self.lab_panel.setObjectName("retina_lab")
        self.lab_panel.hide()

        self.lab_layout = QVBoxLayout(self.lab_panel)
        self.lab_layout.setContentsMargins(10, 8, 10, 8)
        self.lab_layout.setSpacing(6)

        # Lab Header
        lab_header = QHBoxLayout()
        lbl_lab_title = QLabel("⚗ SHADER AUTHORING LAB", self.lab_panel)
        lbl_lab_title.setStyleSheet(
            "color: #ffaa00; font-family: monospace; font-size: 11px; font-weight: bold; background: transparent; border: none;"
        )
        lab_header.addWidget(lbl_lab_title)
        lab_header.addStretch()

        btn_close_lab = QPushButton("✕", self.lab_panel)
        btn_close_lab.setStyleSheet(
            """
            QPushButton {
                background-color: #24141d;
                border: 1px solid #ff0077;
                border-radius: 3px;
                color: #ff0077;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 2px 5px;
            }
            QPushButton:hover { background-color: #ff0077; color: #ffffff; }
        """
        )
        btn_close_lab.clicked.connect(self._close_lab_panel)
        lab_header.addWidget(btn_close_lab)
        self.lab_layout.addLayout(lab_header)

        # Active Shader Identity Label
        self.lbl_lab_identity = QLabel("ACTIVE: TOROID IDENTITY (OFFICIAL)", self.lab_panel)
        self.lbl_lab_identity.setStyleSheet(
            "color: #00f0ff; font-family: monospace; font-size: 10px; font-weight: bold; background: #131624; padding: 4px 6px; border-radius: 3px; border: 1px solid #20263c;"
        )
        self.lab_layout.addWidget(self.lbl_lab_identity)

        # Shader Command Bar: LOAD, RELOAD, RESET
        h_lab_actions = QHBoxLayout()
        h_lab_actions.setSpacing(4)

        self.btn_lab_load = QPushButton("📁 LOAD...", self.lab_panel)
        self.btn_lab_load.setStyleSheet(
            """
            QPushButton {
                background: #181c2c;
                border: 1px solid #00f0ff;
                border-radius: 3px;
                color: #00f0ff;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 5px;
            }
            QPushButton:hover { background: #00f0ff; color: #000000; }
        """
        )
        self.btn_lab_load.clicked.connect(self._load_local_shader_dialog)
        h_lab_actions.addWidget(self.btn_lab_load)

        self.btn_lab_reload = QPushButton("⟳ RELOAD (R)", self.lab_panel)
        self.btn_lab_reload.setStyleSheet(
            """
            QPushButton {
                background: #181c2c;
                border: 1px solid #00f0ff;
                border-radius: 3px;
                color: #00f0ff;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 5px;
            }
            QPushButton:hover { background: #00f0ff; color: #000000; }
        """
        )
        self.btn_lab_reload.clicked.connect(self._reload_lab_shader)
        h_lab_actions.addWidget(self.btn_lab_reload)

        self.btn_lab_reset = QPushButton("↺ RESET", self.lab_panel)
        self.btn_lab_reset.setStyleSheet(
            """
            QPushButton {
                background: #181c2c;
                border: 1px solid #ffaa00;
                border-radius: 3px;
                color: #ffaa00;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 5px;
            }
            QPushButton:hover { background: #ffaa00; color: #000000; }
        """
        )
        self.btn_lab_reset.clicked.connect(self._reset_tune_parameters)
        h_lab_actions.addWidget(self.btn_lab_reset)
        self.lab_layout.addLayout(h_lab_actions)

        # Preset Actions Bar: SAVE PRESET, LOAD PRESET
        h_preset_actions = QHBoxLayout()
        h_preset_actions.setSpacing(4)

        self.btn_lab_save_preset = QPushButton("⇱ SAVE PRESET", self.lab_panel)
        self.btn_lab_save_preset.setStyleSheet(
            """
            QPushButton {
                background: #1f1b26;
                border: 1px solid #ff0077;
                border-radius: 3px;
                color: #ff0077;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 5px;
            }
            QPushButton:hover { background: #ff0077; color: #ffffff; }
        """
        )
        self.btn_lab_save_preset.clicked.connect(self._save_lab_preset_dialog)
        h_preset_actions.addWidget(self.btn_lab_save_preset)

        self.btn_lab_load_preset = QPushButton("⇲ LOAD PRESET", self.lab_panel)
        self.btn_lab_load_preset.setStyleSheet(
            """
            QPushButton {
                background: #1f1b26;
                border: 1px solid #ff0077;
                border-radius: 3px;
                color: #ff0077;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 3px 5px;
            }
            QPushButton:hover { background: #ff0077; color: #ffffff; }
        """
        )
        self.btn_lab_load_preset.clicked.connect(self._load_lab_preset_dialog)
        h_preset_actions.addWidget(self.btn_lab_load_preset)
        self.lab_layout.addLayout(h_preset_actions)

        # Scrollable Parameters Area
        self.lab_scroll = QScrollArea(self.lab_panel)
        self.lab_scroll.setWidgetResizable(True)
        self.lab_scroll.setStyleSheet("background-color: #0b0d14; border: 1px solid #1a1e30; border-radius: 3px;")
        self.lab_controls_widget = QWidget()
        self.lab_controls_layout = QVBoxLayout(self.lab_controls_widget)
        self.lab_controls_layout.setContentsMargins(6, 6, 6, 6)
        self.lab_controls_layout.setSpacing(6)
        self.lab_controls_layout.addStretch()
        self.lab_scroll.setWidget(self.lab_controls_widget)
        self.lab_layout.addWidget(self.lab_scroll, stretch=1)

        # Compact Diagnostic Status View
        self.lab_diag_view = QLabel("[OK] Shader ready.", self.lab_panel)
        self.lab_diag_view.setStyleSheet(
            "color: #00ffcc; font-family: monospace; font-size: 9px; background: #0e111a; padding: 4px 6px; border: 1px solid #1a2032; border-radius: 2px;"
        )
        self.lab_diag_view.setWordWrap(True)
        self.lab_layout.addWidget(self.lab_diag_view)

        # Pygame Fullscreen Render Engine
        pygame.init()
        self.surf_w, self.surf_h = 1920, 1080
        self.surface = pygame.Surface((self.surf_w, self.surf_h))
        self.visualizers: list[Visualizer] = [
            ToroidVisualizer(self.surf_w, self.surf_h),
            WaveformRibbonVisualizer(self.surf_w, self.surf_h),
            DeepFieldVisualizer(self.surf_w, self.surf_h),
            ToroidAMPFloorVisualizer(self.surf_w, self.surf_h),
            ToroidIdentityVisualizer(self.surf_w, self.surf_h),
            CyberBloomVisualizer(self.surf_w, self.surf_h),
        ]
        self.vis_idx = 0
        self._apply_visualizer_selection()
        self._hud_state = "HUD_VISIBLE"

        # Auto-Hide Timer (2.5s mouse inactivity)
        self.hud_timer = QTimer(self)
        self.hud_timer.timeout.connect(self._on_hud_timer_timeout)
        self.hud_timer.start(2500)

        self.setMouseTracking(True)
        self.vis_label.setMouseTracking(True)
        self.gpu_canvas.setMouseTracking(True)

        # Install event filter on backgrounds to capture Left/Right clicks without stealing child slider events
        self.vis_label.installEventFilter(self)
        self.gpu_canvas.installEventFilter(self)

    @property
    def current_visualizer(self) -> Visualizer:
        return self.visualizers[self.vis_idx]

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
        self._local_shader_active = False
        self._local_shader_path = None
        self.vis_idx = (self.vis_idx + 1) % len(self.visualizers)
        self._apply_visualizer_selection()
        self.visualizer_switched.emit(self.vis_idx)

    def _update_mode_button_text(self):
        if self._local_shader_active and self._local_shader_path:
            name = f"LOCAL: {self._local_shader_path.stem.upper()}"
            self.hud_btn_mode.setText(f"MODE: {name}")
            self.hud_btn_tune.setVisible(True)
            self.hud_btn_lab.setVisible(True)
            return

        vis = self.current_visualizer
        name = vis.get_name().upper()
        self.hud_btn_mode.setText(f"MODE: {name}")

        is_gpu = getattr(vis, "is_gpu", lambda: False)()
        meta = getattr(vis, "get_metadata", lambda: None)()
        has_params = is_gpu and meta and len(meta.parameters) > 0
        self.hud_btn_tune.setVisible(bool(has_params))
        self.hud_btn_lab.setVisible(is_gpu)

        if not has_params and self.tune_panel.isVisible():
            self._close_tune_panel()

    def set_visualizer_index(self, index: int):
        self._local_shader_active = False
        self._local_shader_path = None
        self.vis_idx = index % len(self.visualizers)
        self._apply_visualizer_selection()

    def _apply_visualizer_selection(self):
        # Authoritative visualizer switch: dismiss visualizer-specific workbench overlays
        if self.lab_panel.isVisible():
            self._close_lab_panel()

        vis = self.current_visualizer
        is_gpu = getattr(vis, "is_gpu", lambda: False)()

        if is_gpu:
            shader_path = getattr(vis, "get_shader_path", lambda: None)()
            if shader_path and shader_path.exists():
                self.surface_layout.setCurrentIndex(1)
                self.gpu_canvas.load_shader_file(shader_path)
                self._restore_persisted_parameters()
            else:
                # Failure fallback to safe CPU visualizer
                self.surface_layout.setCurrentIndex(0)
                vis.resize(self.surf_w, self.surf_h)
        else:
            self.surface_layout.setCurrentIndex(0)
            vis.resize(self.surf_w, self.surf_h)

        self._update_mode_button_text()
        if self.tune_panel.isVisible():
            self._rebuild_tune_panel()

    def _restore_persisted_parameters(self):
        vis = self.current_visualizer
        vis_id = getattr(vis, "get_id", lambda: "vis")()
        meta = self.gpu_canvas.metadata

        if not meta or not meta.parameters:
            return

        persisted = {}
        if self.session_manager and hasattr(self.session_manager, "state"):
            persisted = self.session_manager.state.visualizer_parameters.get(vis_id, {})

        for p_name, param in meta.parameters.items():
            if p_name in persisted:
                raw_val = persisted[p_name]
                if param.param_type == "float":
                    try:
                        val = float(raw_val)
                        val = max(param.min_value, min(param.max_value, val))
                        self.gpu_canvas.set_param_value(p_name, val)
                    except (ValueError, TypeError):
                        self.gpu_canvas.set_param_value(p_name, param.default_value)
                elif param.param_type == "bool":
                    b_val = raw_val is True or raw_val == 1 or str(raw_val).lower() in ("true", "1")
                    self.gpu_canvas.set_param_value(p_name, b_val)
                elif param.param_type == "color":
                    c_str = str(raw_val).strip()
                    if hex_to_rgb_normalized(c_str) is not None:
                        self.gpu_canvas.set_param_value(p_name, c_str.upper())
                    else:
                        self.gpu_canvas.set_param_value(p_name, param.default_value)
                else:
                    self.gpu_canvas.set_param_value(p_name, param.default_value)
            else:
                self.gpu_canvas.set_param_value(p_name, param.default_value)

    def _persist_parameters(self):
        if self._local_shader_active:
            # Local shaders do not permanently alter standard official session visualizer slots
            return

        vis = self.current_visualizer
        vis_id = getattr(vis, "get_id", lambda: "vis")()
        params = dict(self.gpu_canvas.current_params)
        self.parameters_changed.emit(vis_id, params)

        if self.session_manager and hasattr(self.session_manager, "state"):
            self.session_manager.state.visualizer_parameters[vis_id] = params
            self.session_manager.save()

    # --- TUNE PANEL STATE MACHINE ---

    def _toggle_tune_panel(self):
        if self.tune_panel.isVisible():
            self._close_tune_panel()
        else:
            self._open_tune_panel()

    def _open_tune_panel(self):
        if self.lab_panel.isVisible():
            self._close_lab_panel()
        self._rebuild_tune_panel()
        self._position_tune_panel()
        self.tune_panel.show()
        self.hud_btn_tune.setChecked(True)
        self.hud_timer.stop()  # Suspend auto-hide while tuning

    def _close_tune_panel(self):
        self.tune_panel.hide()
        self.hud_btn_tune.setChecked(False)
        if not self.lab_panel.isVisible():
            self.hud_timer.start(2500)

    def _position_tune_panel(self):
        hud_pos = self.hud.pos()
        tune_x = hud_pos.x() + self.hud.width() - self.tune_panel.width()
        tune_y = hud_pos.y() - self.tune_panel.sizeHint().height() - 8
        self.tune_panel.move(max(10, tune_x), max(10, tune_y))

    def _rebuild_tune_panel(self):
        while self.tune_controls_layout.count() > 0:
            item = self.tune_controls_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._param_sliders.clear()
        self._param_val_labels.clear()

        meta = self.gpu_canvas.metadata
        if not meta or not meta.parameters:
            lbl_none = QLabel("(No tunable parameters)", self.tune_panel)
            lbl_none.setStyleSheet("color: #606880; font-family: monospace; font-size: 10px; font-style: italic;")
            self.tune_controls_layout.addWidget(lbl_none)
            self.tune_panel.adjustSize()
            return

        for p_name, param in meta.parameters.items():
            card = QFrame(self.tune_panel)
            card.setStyleSheet("background-color: #141724; border: 1px solid #222638; border-radius: 3px;")
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(6, 4, 6, 4)
            c_layout.setSpacing(2)

            if param.param_type == "bool":
                curr_b = bool(self.gpu_canvas.current_params.get(p_name, param.default_value))
                chk = QCheckBox(param.display_name, card)
                chk.setChecked(curr_b)
                chk.setStyleSheet("""
                    QCheckBox {
                        color: #00f0ff;
                        font-family: monospace;
                        font-size: 10px;
                        font-weight: bold;
                        border: none;
                    }
                    QCheckBox::indicator {
                        width: 12px;
                        height: 12px;
                        background: #181c2c;
                        border: 1px solid #00f0ff;
                        border-radius: 2px;
                    }
                    QCheckBox::indicator:checked {
                        background: #00f0ff;
                    }
                """)
                def make_chk_cb(name=p_name):
                    def on_chk(checked: bool):
                        self.gpu_canvas.set_param_value(name, checked)
                        self._persist_parameters()
                        if self.lab_panel.isVisible():
                            self._rebuild_lab_panel()
                    return on_chk
                chk.toggled.connect(make_chk_cb())
                c_layout.addWidget(chk)

            elif param.param_type == "color":
                curr_c = str(self.gpu_canvas.current_params.get(p_name, param.default_value))
                h_row = QHBoxLayout()
                lbl_name = QLabel(param.display_name, card)
                lbl_name.setStyleSheet("color: #00f0ff; font-family: monospace; font-size: 10px; font-weight: bold; border: none;")
                h_row.addWidget(lbl_name)
                h_row.addStretch()

                btn_color = QPushButton(curr_c, card)
                btn_color.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {curr_c};
                        color: #000000;
                        font-family: monospace;
                        font-size: 9px;
                        font-weight: bold;
                        border: 1px solid #ffffff;
                        border-radius: 2px;
                        padding: 1px 5px;
                    }}
                """)
                def make_color_cb(name=p_name, btn=btn_color):
                    def on_color_click():
                        init_qcol = QColor(self.gpu_canvas.current_params.get(name, "#00E5FF"))
                        picked = _open_styled_color_dialog(init_qcol, self, f"Select {name}")
                        if picked and picked.isValid():
                            hex_col = picked.name().upper()
                            self.gpu_canvas.set_param_value(name, hex_col)
                            btn.setText(hex_col)
                            btn.setStyleSheet(f"""
                                QPushButton {{
                                    background-color: {hex_col};
                                    color: #000000;
                                    font-family: monospace;
                                    font-size: 9px;
                                    font-weight: bold;
                                    border: 1px solid #ffffff;
                                    border-radius: 2px;
                                    padding: 1px 5px;
                                }}
                            """)
                            self._persist_parameters()
                            if self.lab_panel.isVisible():
                                self._rebuild_lab_panel()
                    return on_color_click
                btn_color.clicked.connect(make_color_cb())
                h_row.addWidget(btn_color)
                c_layout.addLayout(h_row)

            else:
                # float parameter
                h_row = QHBoxLayout()
                lbl_name = QLabel(param.display_name, card)
                lbl_name.setStyleSheet("color: #00f0ff; font-family: monospace; font-size: 10px; font-weight: bold; border: none;")
                h_row.addWidget(lbl_name)
                h_row.addStretch()

                curr_v = float(self.gpu_canvas.current_params.get(p_name, param.default_value))
                lbl_val = QLabel(f"{curr_v:5.2f}", card)
                lbl_val.setStyleSheet("color: #ffaa00; font-family: monospace; font-size: 10px; border: none;")
                h_row.addWidget(lbl_val)
                c_layout.addLayout(h_row)

                slider = QSlider(Qt.Horizontal, card)
                slider.setRange(0, 1000)
                slider.setStyleSheet(
                    """
                    QSlider::groove:horizontal { height: 4px; background: #1c2035; border-radius: 2px; }
                    QSlider::sub-page:horizontal { background: #00f0ff; border-radius: 2px; }
                    QSlider::handle:horizontal { background: #ffffff; border: 1px solid #00f0ff; width: 10px; margin: -3px 0; border-radius: 5px; }
                """
                )

                val_span = max(0.0001, param.max_value - param.min_value)
                init_pos = int(round(((curr_v - param.min_value) / val_span) * 1000.0))
                slider.setValue(max(0, min(1000, init_pos)))

                def make_slider_cb(name=p_name, p=param, l=lbl_val):
                    def on_slider_move(val_int: int):
                        mapped_val = p.min_value + (val_int / 1000.0) * (p.max_value - p.min_value)
                        self.gpu_canvas.set_param_value(name, mapped_val)
                        l.setText(f"{mapped_val:5.2f}")
                        self._persist_parameters()
                        if self.lab_panel.isVisible():
                            self._rebuild_lab_panel()
                    return on_slider_move

                slider.valueChanged.connect(make_slider_cb())
                c_layout.addWidget(slider)

                self._param_sliders[p_name] = slider
                self._param_val_labels[p_name] = lbl_val

            self.tune_controls_layout.addWidget(card)

        self.tune_panel.adjustSize()
        self._position_tune_panel()

    def _reset_tune_parameters(self):
        """Restores visualizer defaults and writes them to persistent storage."""
        self.gpu_canvas.reset_params()
        self._rebuild_tune_panel()
        if self.lab_panel.isVisible():
            self._rebuild_lab_panel()
        self._persist_parameters()

    # --- INTEGRATED LAB PANEL STATE MACHINE ---

    def _toggle_lab_panel(self):
        if self.lab_panel.isVisible():
            self._close_lab_panel()
        else:
            self._open_lab_panel()

    def _open_lab_panel(self):
        if self.tune_panel.isVisible():
            self._close_tune_panel()
        self._rebuild_lab_panel()
        self._position_lab_panel()
        self.lab_panel.show()
        self.hud_btn_lab.setChecked(True)
        self.hud_timer.stop()  # Suspend auto-hide while in LAB

    def _close_lab_panel(self):
        self.lab_panel.hide()
        self.hud_btn_lab.setChecked(False)
        if not self.tune_panel.isVisible():
            self.hud_timer.start(2500)

    def _position_lab_panel(self):
        hud_pos = self.hud.pos()
        lab_x = hud_pos.x()
        lab_y = max(10, hud_pos.y() - min(460, self.lab_panel.sizeHint().height()) - 8)
        self.lab_panel.setGeometry(lab_x, lab_y, 340, min(460, self.lab_panel.sizeHint().height()))

    def _rebuild_lab_panel(self):
        # Update identity badge
        if self._local_shader_active and self._local_shader_path:
            self.lbl_lab_identity.setText(f"MODE: LOCAL — {self._local_shader_path.stem.upper()}")
            self.lbl_lab_identity.setStyleSheet(
                "color: #ffaa00; font-family: monospace; font-size: 10px; font-weight: bold; background: #261e12; padding: 4px 6px; border-radius: 3px; border: 1px solid #4a361c;"
            )
        else:
            vis = self.current_visualizer
            self.lbl_lab_identity.setText(f"MODE: OFFICIAL — {vis.get_name().upper()}")
            self.lbl_lab_identity.setStyleSheet(
                "color: #00f0ff; font-family: monospace; font-size: 10px; font-weight: bold; background: #131624; padding: 4px 6px; border-radius: 3px; border: 1px solid #20263c;"
            )

        while self.lab_controls_layout.count() > 0:
            item = self.lab_controls_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        meta = self.gpu_canvas.metadata
        if not meta or not meta.parameters:
            lbl_none = QLabel("(No authoring parameters declared)", self.lab_controls_widget)
            lbl_none.setStyleSheet("color: #606880; font-family: monospace; font-size: 10px; font-style: italic;")
            self.lab_controls_layout.addWidget(lbl_none)
            self.lab_controls_layout.addStretch()
            self._position_lab_panel()
            return

        for p_name, param in meta.parameters.items():
            card = QFrame(self.lab_controls_widget)
            card.setStyleSheet("background-color: #141726; border: 1px solid #232840; border-radius: 3px;")
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(6, 4, 6, 4)
            c_layout.setSpacing(2)

            if param.param_type == "bool":
                curr_b = bool(self.gpu_canvas.current_params.get(p_name, param.default_value))
                chk = QCheckBox(param.display_name, card)
                chk.setChecked(curr_b)
                chk.setStyleSheet("""
                    QCheckBox {
                        color: #00f0ff;
                        font-family: monospace;
                        font-size: 10px;
                        font-weight: bold;
                        border: none;
                    }
                    QCheckBox::indicator {
                        width: 12px;
                        height: 12px;
                        background: #181c2c;
                        border: 1px solid #00f0ff;
                        border-radius: 2px;
                    }
                    QCheckBox::indicator:checked {
                        background: #00f0ff;
                    }
                """)
                def make_chk_cb(name=p_name):
                    def on_chk(checked: bool):
                        self.gpu_canvas.set_param_value(name, checked)
                        self._persist_parameters()
                    return on_chk
                chk.toggled.connect(make_chk_cb())
                c_layout.addWidget(chk)

            elif param.param_type == "color":
                curr_c = str(self.gpu_canvas.current_params.get(p_name, param.default_value))
                h_row = QHBoxLayout()
                lbl_name = QLabel(param.display_name, card)
                lbl_name.setStyleSheet("color: #00f0ff; font-family: monospace; font-size: 10px; font-weight: bold; border: none;")
                h_row.addWidget(lbl_name)
                h_row.addStretch()

                btn_color = QPushButton(curr_c, card)
                btn_color.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {curr_c};
                        color: #000000;
                        font-family: monospace;
                        font-size: 9px;
                        font-weight: bold;
                        border: 1px solid #ffffff;
                        border-radius: 2px;
                        padding: 1px 5px;
                    }}
                """)
                def make_color_cb(name=p_name, btn=btn_color):
                    def on_color_click():
                        init_qcol = QColor(self.gpu_canvas.current_params.get(name, "#00E5FF"))
                        picked = _open_styled_color_dialog(init_qcol, self, f"Select {name}")
                        if picked and picked.isValid():
                            hex_col = picked.name().upper()
                            self.gpu_canvas.set_param_value(name, hex_col)
                            btn.setText(hex_col)
                            btn.setStyleSheet(f"""
                                QPushButton {{
                                    background-color: {hex_col};
                                    color: #000000;
                                    font-family: monospace;
                                    font-size: 9px;
                                    font-weight: bold;
                                    border: 1px solid #ffffff;
                                    border-radius: 2px;
                                    padding: 1px 5px;
                                }}
                            """)
                            self._persist_parameters()
                    return on_color_click
                btn_color.clicked.connect(make_color_cb())
                h_row.addWidget(btn_color)
                c_layout.addLayout(h_row)

            else:
                # float parameter
                h_row = QHBoxLayout()
                lbl_name = QLabel(param.display_name, card)
                lbl_name.setStyleSheet("color: #00f0ff; font-size: 10px; font-weight: bold; border: none;")
                h_row.addWidget(lbl_name)
                h_row.addStretch()

                curr_v = float(self.gpu_canvas.current_params.get(p_name, param.default_value))
                lbl_val = QLabel(f"{curr_v:5.2f}", card)
                lbl_val.setStyleSheet("color: #ffaa00; font-size: 10px; border: none;")
                h_row.addWidget(lbl_val)
                c_layout.addLayout(h_row)

                slider = QSlider(Qt.Horizontal, card)
                slider.setRange(0, 1000)
                slider.setStyleSheet("""
                    QSlider::groove:horizontal { height: 4px; background: #1c2035; border-radius: 2px; }
                    QSlider::sub-page:horizontal { background: #00f0ff; border-radius: 2px; }
                    QSlider::handle:horizontal { background: #ffffff; border: 1px solid #00f0ff; width: 10px; margin: -3px 0; border-radius: 5px; }
                """)
                
                val_span = max(0.0001, param.max_value - param.min_value)
                init_pos = int(round(((curr_v - param.min_value) / val_span) * 1000.0))
                slider.setValue(max(0, min(1000, init_pos)))

                def make_slider_cb(name=p_name, p=param, l=lbl_val):
                    def on_slider_move(val_int: int):
                        mapped_val = p.min_value + (val_int / 1000.0) * (p.max_value - p.min_value)
                        self.gpu_canvas.set_param_value(name, mapped_val)
                        l.setText(f"{mapped_val:5.2f}")
                        self._persist_parameters()
                    return on_slider_move

                slider.valueChanged.connect(make_slider_cb())
                c_layout.addWidget(slider)

            self.lab_controls_layout.addWidget(card)

        self.lab_controls_layout.addStretch()
        self._position_lab_panel()

    def _load_local_shader_dialog(self):
        """Loads a local GLSL shader into RETINA MELT from user_shaders/."""
        pkg_root = Path(__file__).resolve().parent.parent.parent.parent
        user_dir = pkg_root / "user_shaders"
        start_dir = str(user_dir) if user_dir.exists() else str(pkg_root)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Local GLSL Shader",
            start_dir,
            "GLSL Shaders (*.frag *.glsl *.txt);;All Files (*.*)"
        )
        if not file_path:
            return

        p = Path(file_path)
        ok = self.gpu_canvas.load_shader_file(p)
        if ok:
            self._local_shader_path = p
            self._local_shader_active = True
            self.surface_layout.setCurrentIndex(1)
            self._update_mode_button_text()
            self._rebuild_lab_panel()
            self.lab_diag_view.setText(f"[OK] Loaded '{p.name}' successfully.")
            self.lab_diag_view.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 9px; background: #0e111a; padding: 4px 6px; border: 1px solid #1a2032; border-radius: 2px;")
        else:
            err = self.gpu_canvas.last_error_log or "Shader compilation/link failed."
            self.lab_diag_view.setText(f"[ERROR] Failed to load '{p.name}':\n{err}")
            self.lab_diag_view.setStyleSheet("color: #ff0077; font-family: monospace; font-size: 9px; background: #260f1c; padding: 4px 6px; border: 1px solid #4a1c32; border-radius: 2px;")

    def _reload_lab_shader(self):
        """Hot-reloads the active shader source from disk without stopping playback."""
        ok = self.gpu_canvas.reload_current_shader()
        if ok:
            self._rebuild_lab_panel()
            name = self.gpu_canvas.active_shader_name or "shader"
            self.lab_diag_view.setText(f"[OK] Reloaded '{name}' successfully.")
            self.lab_diag_view.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 9px; background: #0e111a; padding: 4px 6px; border: 1px solid #1a2032; border-radius: 2px;")
        else:
            err = self.gpu_canvas.last_error_log or "Compile error during reload."
            self.lab_diag_view.setText(f"[ERROR] Reload failed:\n{err}")
            self.lab_diag_view.setStyleSheet("color: #ff0077; font-family: monospace; font-size: 9px; background: #260f1c; padding: 4px 6px; border: 1px solid #4a1c32; border-radius: 2px;")

    def _save_lab_preset_dialog(self):
        """Saves current typed parameter state to a JSON preset file."""
        if not self.gpu_canvas.metadata or not self.gpu_canvas.metadata.parameters:
            self.lab_diag_view.setText("[PRESET] No parameters available to save.")
            return

        shader_id = self.gpu_canvas.active_shader_name or "shader"
        preset_data = create_shader_preset(shader_id, self.gpu_canvas.current_params)

        pkg_root = Path(__file__).resolve().parent.parent.parent.parent
        user_dir = pkg_root / "user_shaders"
        default_fn = f"{shader_id}_preset.json"
        start_path = str(user_dir / default_fn) if user_dir.exists() else default_fn

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Shader Preset",
            start_path,
            "ToroidAMP Shader Preset (*.json);;All Files (*.*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(preset_data, f, indent=2)
                self.lab_diag_view.setText(f"[PRESET] Saved to '{Path(file_path).name}'.")
                self.lab_diag_view.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 9px; background: #0e111a; padding: 4px 6px; border: 1px solid #1a2032; border-radius: 2px;")
            except Exception as e:
                self.lab_diag_view.setText(f"[PRESET ERROR] Save failed: {e}")
                self.lab_diag_view.setStyleSheet("color: #ff0077; font-family: monospace; font-size: 9px; background: #260f1c; padding: 4px 6px; border: 1px solid #4a1c32; border-radius: 2px;")

    def _load_lab_preset_dialog(self):
        """Loads and applies a JSON preset file to the active visualizer."""
        pkg_root = Path(__file__).resolve().parent.parent.parent.parent
        user_dir = pkg_root / "user_shaders"
        start_dir = str(user_dir) if user_dir.exists() else str(pkg_root)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Shader Preset",
            start_dir,
            "ToroidAMP Shader Preset (*.json);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ok, msg, count = parse_and_apply_preset(
                data,
                self.gpu_canvas.active_shader_name or "",
                self.gpu_canvas.metadata,
                self.gpu_canvas.current_params
            )
            if ok:
                self._rebuild_lab_panel()
                self._persist_parameters()
                self.lab_diag_view.setText(f"[PRESET OK] {msg}")
                self.lab_diag_view.setStyleSheet("color: #00ffcc; font-family: monospace; font-size: 9px; background: #0e111a; padding: 4px 6px; border: 1px solid #1a2032; border-radius: 2px;")
            else:
                self.lab_diag_view.setText(f"[PRESET ERROR] {msg}")
                self.lab_diag_view.setStyleSheet("color: #ff0077; font-family: monospace; font-size: 9px; background: #260f1c; padding: 4px 6px; border: 1px solid #4a1c32; border-radius: 2px;")
        except Exception as e:
            self.lab_diag_view.setText(f"[PRESET ERROR] {e}")
            self.lab_diag_view.setStyleSheet("color: #ff0077; font-family: monospace; font-size: 9px; background: #260f1c; padding: 4px 6px; border: 1px solid #4a1c32; border-radius: 2px;")

    # --- EVENT & LIFECYCLE MANAGEMENT ---

    def eventFilter(self, watched, event):
        """Intercepts background clicks on viewport canvases to control HUD pin/hide."""
        if watched in (self.vis_label, self.gpu_canvas, self.surface_container):
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.show_and_pin_hud()
                    return True
                elif event.button() == Qt.RightButton:
                    self.hide_hud_immediately()
                    return True
        return super().eventFilter(watched, event)

    def show_and_pin_hud(self):
        """LEFT CLICK: Explicitly reveals and pins HUD controls."""
        self._hud_state = "HUD_PINNED"
        self.hud_timer.stop()
        self.hud.show()
        if self.tune_panel.isVisible():
            self.tune_panel.show()
        if self.lab_panel.isVisible():
            self.lab_panel.show()

    def hide_hud_immediately(self):
        """RIGHT CLICK: Explicitly hides HUD controls and closes TUNE and LAB panels."""
        self._hud_state = "HUD_HIDDEN"
        self.hud_timer.stop()
        if self.tune_panel.isVisible():
            self._close_tune_panel()
        if self.lab_panel.isVisible():
            self._close_lab_panel()
        self.hud.hide()

    def _on_hud_timer_timeout(self):
        """Auto-hide timeout fires only when HUD is in transient HUD_VISIBLE state."""
        if self._hud_state == "HUD_VISIBLE" and not self.tune_panel.isVisible() and not self.lab_panel.isVisible():
            self._hud_state = "HUD_HIDDEN"
            self.hud.hide()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.show_and_pin_hud()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.hide_hud_immediately()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._hud_state == "HUD_HIDDEN":
            self._hud_state = "HUD_VISIBLE"
            self.hud.show()
            self.hud_timer.start(2500)
        elif self._hud_state == "HUD_VISIBLE" and not self.tune_panel.isVisible() and not self.lab_panel.isVisible():
            self.hud_timer.start(2500)
        event.accept()

    def show_fullscreen_experience(self):
        screen_geom = QGuiApplication.primaryScreen().geometry()
        self.surf_w = screen_geom.width()
        self.surf_h = screen_geom.height()
        self.surface = pygame.Surface((self.surf_w, self.surf_h))

        self._apply_visualizer_selection()

        self.setGeometry(screen_geom)
        self.hud.move((self.surf_w - self.hud.width()) // 2, self.surf_h - 95)
        self.show_and_pin_hud()
        self.showFullScreen()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Escape, Qt.Key_F):
            if self.lab_panel.isVisible():
                self._close_lab_panel()
            elif self.tune_panel.isVisible():
                self._close_tune_panel()
            else:
                self.exit_requested.emit()
        elif event.key() == Qt.Key_Space:
            self.play_toggled.emit()
        elif event.key() == Qt.Key_M:
            self._cycle_visualizer_mode()
        elif event.key() == Qt.Key_T:
            self._toggle_tune_panel()
        elif event.key() == Qt.Key_L:
            self._toggle_lab_panel()
        elif event.key() == Qt.Key_R:
            if self.lab_panel.isVisible() or self._local_shader_active:
                self._reload_lab_shader()
        elif event.key() == Qt.Key_H:
            if self.hud.isVisible():
                self.hide_hud_immediately()
            else:
                self.show_and_pin_hud()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        super().closeEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)

    def update_telemetry(self, title: str, time_str: str, is_playing: bool):
        self.hud_marquee.set_marquee_text(title)
        self.hud_time.setText(time_str)
        self.hud_btn_play.setText("❚❚" if is_playing else "►")

    def render_frame(self, frame: AudioFrame, dt: float):
        if not self.isVisible():
            return
        try:
            vis = self.current_visualizer
            is_gpu = getattr(vis, "is_gpu", lambda: False)() or self._local_shader_active
            if is_gpu:
                self.gpu_canvas.update_audio_frame(frame)
                self.gpu_canvas.update()
            else:
                self.surface.fill((0, 0, 0))
                vis.render(self.surface, frame, dt)
                raw_data = pygame.image.tobytes(self.surface, "RGBA")
                qimg = QImage(raw_data, self.surf_w, self.surf_h, QImage.Format.Format_RGBA8888)
                self.vis_label.setPixmap(QPixmap.fromImage(qimg))
        except Exception:
            pass


