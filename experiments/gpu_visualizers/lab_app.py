"""
ToroidAMP - EXP-VISLAB-001 / GPU-OFFICIAL-001: GPU Visualizer Authoring Lab

Features:
- Live GLSL Preview with dynamic resizing and fullscreen (F11/ESC)
- Official & Experimental Composition Selection
- Packaged Texture Management (taTexture0 for official shaders)
- External Local Shader Loader (.frag, .glsl, .txt) with user_shaders default directory
- Real-time Exposed Parameter Controls (sliders with immediate uniform binding, no recompilation)
- Reset Parameters to declared defaults
- Real Audio + Deterministic Synthetic Audio Profiles (silence, orchestral, metal, electronic, ambient)
- Manual Event Injection ([ BEAT ], [ STRONG BEAT ])
- Failure Isolation & Shader Recompilation Diagnostics
- Performance Telemetry (FPS, CPU paint timing, viewport resolution)
"""

import os
import sys
import time
import math
from pathlib import Path
from typing import Optional, List, Dict

# Ensure project paths
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "src"))

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QSurfaceFormat, QMouseEvent, QKeyEvent, QPainter, QColor, QFont, QImage
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QTextEdit, QFileDialog, QSlider,
    QComboBox, QScrollArea, QProgressBar, QGridLayout, QSizePolicy, QButtonGroup
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtOpenGL import (
    QOpenGLShader, QOpenGLShaderProgram, QOpenGLBuffer, QOpenGLVertexArrayObject,
    QOpenGLTexture
)

from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.visualizers.gpu_compiler import (
    classify_and_wrap_source, ShaderMetadata, ShaderParameter,
    VERTEX_SHADER_SOURCE, FALLBACK_FRAG_SOURCE
)
from toroidamp.visualizers.gpu_canvas import GLVisualizerCanvas
from experiments.visualizers.profiles import PROFILES, PROFILE_ORDER, SyntheticProfile


class AudioTelemetryMiniWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.frame: Optional[AudioFrame] = None

    def update_frame(self, frame: AudioFrame):
        self.frame = frame
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 12, 18))
        
        if not self.frame:
            return

        w = self.width()
        h = self.height()
        
        spec = self.frame.spectrum
        bar_count = min(32, len(spec))
        bw = (w * 0.5) / max(1, bar_count)
        
        for i in range(bar_count):
            bh = spec[i * 2] * (h - 10)
            painter.fillRect(int(i * bw), int(h - bh), int(bw - 1), int(bh), QColor(0, 240, 255, 180))

        rx = int(w * 0.55)
        meter_w = int((w - rx - 20) / 4)
        
        bands = [
            ("RMS", self.frame.rms, QColor(0, 255, 200)),
            ("BAS", self.frame.bass, QColor(255, 0, 120)),
            ("MID", self.frame.mids, QColor(0, 240, 255)),
            ("TRE", self.frame.treble, QColor(255, 180, 0))
        ]
        
        font = QFont("monospace", 7)
        painter.setFont(font)

        for idx, (lbl, val, col) in enumerate(bands):
            bx = rx + idx * (meter_w + 4)
            bh = val * (h - 18)
            painter.fillRect(bx, 14, meter_w, h - 18, QColor(25, 30, 45))
            painter.fillRect(bx, int(h - bh), meter_w, int(bh), col)
            painter.setPen(QColor(180, 190, 210))
            painter.drawText(bx, 10, lbl)

        if self.frame.strong_beat:
            painter.fillRect(w - 14, 4, 10, 10, QColor(255, 0, 80))
        elif self.frame.beat:
            painter.fillRect(w - 14, 4, 10, 10, QColor(0, 255, 150))
        else:
            painter.fillRect(w - 14, 4, 10, 10, QColor(40, 45, 60))


class GPUAuthoringLabWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ToroidAMP :: GPU Visualizer Authoring Lab & Official Preview")
        self.resize(1160, 740)
        self.setStyleSheet("background-color: #0c0e16; color: #ffffff; font-family: monospace;")

        self.base_dir = Path(__file__).resolve().parent
        self.exp_shader_dir = self.base_dir / "shaders"
        self.user_shader_dir = repo_root / "user_shaders"
        self.official_shader_dir = repo_root / "src" / "toroidamp" / "assets" / "official_shaders"

        self.active_profile_name = "electronic"
        self.profile_instances: Dict[str, SyntheticProfile] = {
            p_name: PROFILES[p_name]() for p_name in PROFILE_ORDER
        }
        self._manual_beat_trigger = False
        self._manual_strong_beat_trigger = False

        # GPU-AUDIO-003: at most one inline AUDIO source selector expanded at
        # a time across all parameter cards. Reset on every panel rebuild.
        self._active_audio_selector_frame: Optional[QFrame] = None

        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        top_bar = QFrame(self)
        top_bar.setFixedHeight(40)
        top_bar.setStyleSheet("background-color: #131624; border: 1px solid #222638; border-radius: 4px;")
        t_layout = QHBoxLayout(top_bar)
        t_layout.setContentsMargins(8, 4, 8, 4)
        t_layout.setSpacing(6)

        btn_style = """
            QPushButton {
                background: #1a1e30;
                border: 1px solid #00f0ff;
                border-radius: 3px;
                color: #00f0ff;
                font-family: monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 4px 7px;
            }
            QPushButton:hover { background: #00f0ff; color: #000000; }
        """
        btn_gold_style = """
            QPushButton {
                background: #282012;
                border: 1px solid #ffaa00;
                border-radius: 3px;
                color: #ffaa00;
                font-family: monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 4px 7px;
            }
            QPushButton:hover { background: #ffaa00; color: #000000; }
        """
        btn_pink_style = """
            QPushButton {
                background: #281424;
                border: 1px solid #ff0077;
                border-radius: 3px;
                color: #ff0077;
                font-family: monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 4px 7px;
            }
            QPushButton:hover { background: #ff0077; color: #ffffff; }
        """

        self.btn_off_toroid = QPushButton("★ TOROID IDENTITY", top_bar)
        self.btn_off_toroid.setStyleSheet(btn_gold_style)
        self.btn_off_toroid.clicked.connect(lambda: self.switch_shader_path(self.official_shader_dir / "toroid_identity.frag"))
        t_layout.addWidget(self.btn_off_toroid)

        self.btn_off_bloom = QPushButton("★ CYBER BLOOM", top_bar)
        self.btn_off_bloom.setStyleSheet(btn_gold_style)
        self.btn_off_bloom.clicked.connect(lambda: self.switch_shader_path(self.official_shader_dir / "cyber_bloom.frag"))
        t_layout.addWidget(self.btn_off_bloom)

        self.btn_off_ref = QPushButton("★ MINIMAL REF", top_bar)
        self.btn_off_ref.setStyleSheet(btn_gold_style)
        self.btn_off_ref.clicked.connect(lambda: self.switch_shader_path(self.official_shader_dir / "minimal_reference.frag"))
        t_layout.addWidget(self.btn_off_ref)

        self.btn_shader_a = QPushButton("[ PLASMA ]", top_bar)
        self.btn_shader_a.setStyleSheet(btn_style)
        self.btn_shader_a.clicked.connect(lambda: self.switch_shader_path(self.exp_shader_dir / "shader_a_plasma.frag"))
        t_layout.addWidget(self.btn_shader_a)

        self.btn_shader_b = QPushButton("[ RAYMARCH ]", top_bar)
        self.btn_shader_b.setStyleSheet(btn_style)
        self.btn_shader_b.clicked.connect(lambda: self.switch_shader_path(self.exp_shader_dir / "shader_b_raymarch.frag"))
        t_layout.addWidget(self.btn_shader_b)

        t_layout.addStretch()

        self.btn_load_preset = QPushButton("⇲ LOAD PRESET", top_bar)
        self.btn_load_preset.setStyleSheet(btn_style)
        self.btn_load_preset.clicked.connect(self.load_preset_dialog)
        t_layout.addWidget(self.btn_load_preset)

        self.btn_save_preset = QPushButton("⇱ SAVE PRESET", top_bar)
        self.btn_save_preset.setStyleSheet(btn_style)
        self.btn_save_preset.clicked.connect(self.save_preset_dialog)
        t_layout.addWidget(self.btn_save_preset)

        self.btn_load = QPushButton("📁 LOAD SHADER...", top_bar)
        self.btn_load.setStyleSheet(btn_style)
        self.btn_load.clicked.connect(self.load_external_shader_dialog)
        t_layout.addWidget(self.btn_load)

        self.btn_reload = QPushButton("⟳ RELOAD (R)", top_bar)
        self.btn_reload.setStyleSheet(btn_style)
        self.btn_reload.clicked.connect(self.reload_shader)
        t_layout.addWidget(self.btn_reload)

        self.btn_auto_react = QPushButton("⚡ AUTO REACT", top_bar)
        self.btn_auto_react.setCheckable(True)
        self.btn_auto_react.setChecked(False)
        self.btn_auto_react.setStyleSheet("""
            QPushButton { background-color: #1a1e2e; color: #a0aab8; border: 1px solid #2e384d; border-radius: 3px; font-family: monospace; font-size: 10px; padding: 4px 8px; }
            QPushButton:hover { background-color: #252b42; color: #ffffff; }
            QPushButton:checked { background-color: #ff0077; border: 1px solid #ff0077; color: #ffffff; font-weight: bold; }
        """)
        self.btn_auto_react.toggled.connect(self.toggle_auto_react)
        t_layout.addWidget(self.btn_auto_react)

        self.btn_broken = QPushButton("⚠ BREAK", top_bar)
        self.btn_broken.setStyleSheet(btn_pink_style)
        self.btn_broken.clicked.connect(self.test_broken_shader)
        t_layout.addWidget(self.btn_broken)

        self.btn_fs = QPushButton("⛶ FULLSCREEN (F11)", top_bar)
        self.btn_fs.setStyleSheet(btn_style)
        self.btn_fs.clicked.connect(self.toggle_fullscreen)
        t_layout.addWidget(self.btn_fs)

        main_layout.addWidget(top_bar)

        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(6)

        self.canvas = GLVisualizerCanvas(self)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        middle_layout.addWidget(self.canvas, stretch=3)

        side_panel = QFrame(self)
        side_panel.setFixedWidth(320)
        side_panel.setStyleSheet("background-color: #121422; border: 1px solid #1f2338; border-radius: 4px;")
        s_layout = QVBoxLayout(side_panel)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(6)

        lbl_audio_hdr = QLabel("AUDIO SOURCE & TELEMETRY", side_panel)
        lbl_audio_hdr.setStyleSheet("color: #00ffcc; font-size: 10px; font-weight: bold;")
        s_layout.addWidget(lbl_audio_hdr)

        h_audio_sel = QHBoxLayout()
        self.combo_profiles = QComboBox(side_panel)
        self.combo_profiles.addItems([f"SYNTHETIC: {p.upper()}" for p in PROFILE_ORDER])
        self.combo_profiles.setCurrentIndex(PROFILE_ORDER.index("electronic"))
        self.combo_profiles.currentIndexChanged.connect(self._on_profile_changed)
        self.combo_profiles.setStyleSheet("""
            QComboBox {
                background: #181c2c;
                border: 1px solid #2a304a;
                color: #ffffff;
                font-size: 10px;
                padding: 2px 4px;
            }
        """)
        h_audio_sel.addWidget(self.combo_profiles)
        s_layout.addLayout(h_audio_sel)

        self.telemetry_widget = AudioTelemetryMiniWidget(side_panel)
        s_layout.addWidget(self.telemetry_widget)

        h_triggers = QHBoxLayout()
        self.btn_trig_beat = QPushButton("⚡ BEAT", side_panel)
        self.btn_trig_beat.setStyleSheet(btn_style)
        self.btn_trig_beat.clicked.connect(self._inject_manual_beat)
        h_triggers.addWidget(self.btn_trig_beat)

        self.btn_trig_strong = QPushButton("💥 STRONG BEAT", side_panel)
        self.btn_trig_strong.setStyleSheet(btn_pink_style)
        self.btn_trig_strong.clicked.connect(self._inject_manual_strong_beat)
        h_triggers.addWidget(self.btn_trig_strong)
        s_layout.addLayout(h_triggers)

        sep = QFrame(side_panel)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #252a42;")
        s_layout.addWidget(sep)

        h_param_hdr = QHBoxLayout()
        lbl_param_hdr = QLabel("EXPOSED PARAMETERS", side_panel)
        lbl_param_hdr.setStyleSheet("color: #ffaa00; font-size: 10px; font-weight: bold;")
        h_param_hdr.addWidget(lbl_param_hdr)
        h_param_hdr.addStretch()

        self.btn_reset_params = QPushButton("↺ RESET", side_panel)
        self.btn_reset_params.setStyleSheet(btn_style)
        self.btn_reset_params.clicked.connect(self.reset_parameters)
        h_param_hdr.addWidget(self.btn_reset_params)
        s_layout.addLayout(h_param_hdr)

        self.param_scroll = QScrollArea(side_panel)
        self.param_scroll.setWidgetResizable(True)
        self.param_scroll.setStyleSheet("background-color: #0e101a; border: 1px solid #1a1e30;")
        self.param_container = QWidget()
        self.param_layout = QVBoxLayout(self.param_container)
        self.param_layout.setContentsMargins(6, 6, 6, 6)
        self.param_layout.setSpacing(8)
        self.param_layout.addStretch()
        self.param_scroll.setWidget(self.param_container)
        s_layout.addWidget(self.param_scroll, stretch=1)

        middle_layout.addWidget(side_panel)
        main_layout.addLayout(middle_layout, stretch=1)

        self.error_view = QTextEdit(self)
        self.error_view.setFixedHeight(60)
        self.error_view.setReadOnly(True)
        self.error_view.setStyleSheet("""
            QTextEdit {
                background-color: #090a10;
                border: 1px solid #2d1624;
                color: #ff5577;
                font-family: monospace;
                font-size: 10px;
            }
        """)
        main_layout.addWidget(self.error_view)

        bot_bar = QFrame(self)
        bot_bar.setFixedHeight(24)
        bot_bar.setStyleSheet("background-color: #0a0b12; border: 1px solid #1a1d2e; border-radius: 2px;")
        b_layout = QHBoxLayout(bot_bar)
        b_layout.setContentsMargins(8, 0, 8, 0)

        self.lbl_shader_status = QLabel("ACTIVE: None", bot_bar)
        self.lbl_shader_status.setStyleSheet("color: #00ffcc; font-size: 10px; font-weight: bold;")
        b_layout.addWidget(self.lbl_shader_status)

        b_layout.addStretch()

        self.lbl_telemetry = QLabel("FPS: 60.0 | CPU Paint: 0.00 ms | Res: 0x0", bot_bar)
        self.lbl_telemetry.setStyleSheet("color: #ffaa00; font-size: 10px; font-weight: bold;")
        b_layout.addWidget(self.lbl_telemetry)

        main_layout.addWidget(bot_bar)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(16)

        self._initial_load_done = False
        self._param_slider_widgets: Dict[str, QSlider] = {}
        self._param_val_labels: Dict[str, QLabel] = {}

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_load_done:
            self._initial_load_done = True
            self.switch_shader_path(self.official_shader_dir / "toroid_identity.frag")

    def toggle_auto_react(self, checked: bool):
        self.canvas.set_auto_react(checked)
        self.canvas.update()

    def switch_shader_path(self, target_path: Path):
        self.btn_auto_react.setChecked(False)
        self.canvas.set_auto_react(False)
        ok = self.canvas.load_shader_file(target_path)
        self._rebuild_parameter_ui()
        self._update_ui_state(ok)

    def load_external_shader_dialog(self):
        start_dir = str(self.user_shader_dir) if self.user_shader_dir.exists() else str(repo_root)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open GLSL / Fragment Shader",
            start_dir,
            "Shader Files (*.frag *.glsl *.txt);;All Files (*.*)"
        )
        if file_path:
            p = Path(file_path)
            self.switch_shader_path(p)

    def reload_shader(self):
        ok = self.canvas.reload_current_shader()
        self._rebuild_parameter_ui()
        self._update_ui_state(ok)

    def test_broken_shader(self):
        broken_path = self.exp_shader_dir / "broken_shader_test.frag"
        with open(broken_path, "w", encoding="utf-8") as f:
            f.write("// Intentional Broken Shader\nvoid main() {\n   float a = vec3(1.0, 2.0);\n   fragColor = invalidSyntax;\n}\n")
        ok = self.canvas.load_shader_file(broken_path)
        self._update_ui_state(ok)
        if broken_path.exists():
            broken_path.unlink(missing_ok=True)

    def save_preset_dialog(self):
        """Saves current authoring parameter values to a JSON preset file."""
        if not self.canvas.metadata or not self.canvas.metadata.parameters:
            self.error_view.setText("[PRESET] No tunable parameters available to save.")
            return

        import json
        shader_id = self.canvas.active_shader_name or "shader"
        preset_data = {
            "format": "toroidamp_shader_preset",
            "version": 1,
            "shader": shader_id,
            "parameters": dict(self.canvas.current_params)
        }

        default_fn = f"{shader_id}_preset.json"
        start_path = str(self.user_shader_dir / default_fn) if self.user_shader_dir.exists() else default_fn
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
                self.error_view.setText(f"[PRESET] Saved preset to '{Path(file_path).name}'.")
            except Exception as e:
                self.error_view.setText(f"[PRESET ERROR] Failed to save preset: {e}")

    def load_preset_dialog(self):
        """Loads and validates a JSON preset file, applying typed values to parameters and UI."""
        import json
        start_path = str(self.user_shader_dir) if self.user_shader_dir.exists() else str(repo_root)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Shader Preset",
            start_path,
            "ToroidAMP Shader Preset (*.json);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.error_view.setText(f"[PRESET ERROR] Malformed JSON file: {e}")
            return

        if not isinstance(data, dict) or data.get("format") != "toroidamp_shader_preset":
            self.error_view.setText("[PRESET ERROR] Invalid preset format (expected format: 'toroidamp_shader_preset').")
            return

        preset_shader = data.get("shader", "")
        curr_shader = self.canvas.active_shader_name or ""
        if preset_shader and curr_shader and preset_shader.lower() != curr_shader.lower():
            self.error_view.setText(f"[PRESET WARNING] Preset was saved for '{preset_shader}', but active shader is '{curr_shader}'. Mismatched parameters may be ignored.")

        raw_params = data.get("parameters", {})
        if not isinstance(raw_params, dict):
            self.error_view.setText("[PRESET ERROR] Missing or invalid 'parameters' dictionary in preset.")
            return

        if self.canvas.metadata:
            from toroidamp.visualizers.gpu_compiler import hex_to_rgb_normalized
            applied_count = 0
            for p_name, param in self.canvas.metadata.parameters.items():
                if p_name in raw_params:
                    val = raw_params[p_name]
                    if param.param_type == "float":
                        try:
                            f_val = float(val)
                            f_val = max(param.min_value, min(param.max_value, f_val))
                            self.canvas.set_param_value(p_name, f_val)
                            applied_count += 1
                        except (ValueError, TypeError):
                            pass
                    elif param.param_type == "bool":
                        b_val = val is True or val == 1 or str(val).lower() in ("true", "1")
                        self.canvas.set_param_value(p_name, b_val)
                        applied_count += 1
                    elif param.param_type == "color":
                        c_str = str(val).strip()
                        if hex_to_rgb_normalized(c_str) is not None:
                            self.canvas.set_param_value(p_name, c_str.upper())
                            applied_count += 1

            self._rebuild_parameter_ui()
            self.error_view.setText(f"[PRESET] Successfully loaded preset '{Path(file_path).name}' ({applied_count} parameters applied).")
        else:
            self.error_view.setText("[PRESET ERROR] No active shader metadata available.")

    def _rebuild_parameter_ui(self):
        while self.param_layout.count() > 0:
            item = self.param_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._param_slider_widgets.clear()
        self._param_val_labels.clear()

        # Rebuilding destroys every card (and any expanded selector inside
        # one) — drop the dangling reference rather than pointing at a
        # deleted widget. The selector does not need to reopen automatically.
        self._active_audio_selector_frame = None

        if not self.canvas.metadata or not self.canvas.metadata.parameters:
            lbl_none = QLabel("(No exposed parameters declared)", self.param_container)
            lbl_none.setStyleSheet("color: #606880; font-style: italic; font-size: 10px;")
            self.param_layout.addWidget(lbl_none)
            self.param_layout.addStretch()
            return

        from PySide6.QtWidgets import QCheckBox, QColorDialog

        for p_name, param in self.canvas.metadata.parameters.items():
            card = QFrame(self.param_container)
            card.setStyleSheet("background-color: #141726; border: 1px solid #232840; border-radius: 3px;")
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(6, 4, 6, 4)
            c_layout.setSpacing(2)

            if param.param_type == "bool":
                curr_b = bool(self.canvas.current_params.get(p_name, param.default_value))
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
                        self.canvas.set_param_value(name, checked)
                    return on_chk
                chk.toggled.connect(make_chk_cb())
                c_layout.addWidget(chk)

            elif param.param_type == "color":
                curr_c = str(self.canvas.current_params.get(p_name, param.default_value))
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
                        init_qcol = QColor(self.canvas.current_params.get(name, "#00E5FF"))
                        picked = QColorDialog.getColor(init_qcol, self, f"Select {name}")
                        if picked.isValid():
                            hex_col = picked.name().upper()
                            self.canvas.set_param_value(name, hex_col)
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
                    return on_color_click
                btn_color.clicked.connect(make_color_cb())
                h_row.addWidget(btn_color)
                c_layout.addLayout(h_row)

            else:
                # float parameter
                h_row = QHBoxLayout()
                # GPU-AUDIO-004: identify promoted-const provenance inline —
                # no separate "CONST PANEL", same card, same as the Integrated LAB.
                name_text = f"{param.display_name} [CONST]" if getattr(param, "is_promoted_const", False) else param.display_name
                lbl_name = QLabel(name_text, card)
                lbl_name.setStyleSheet("color: #00f0ff; font-size: 10px; font-weight: bold; border: none;")
                h_row.addWidget(lbl_name)
                h_row.addStretch()

                curr_v = float(self.canvas.current_params.get(p_name, param.default_value))
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
                        self.canvas.set_param_value(name, mapped_val)
                        l.setText(f"{mapped_val:5.2f}")
                    return on_slider_move

                slider.valueChanged.connect(make_slider_cb())
                c_layout.addWidget(slider)

                # Audio Modulation Binding Row (GPU-AUDIO-003)
                curr_src, curr_amt = self.canvas.get_param_audio_binding(p_name)
                h_audio = QHBoxLayout()
                h_audio.setSpacing(4)

                # GPU-AUDIO-003: AUDIO source selector — inline, embedded in
                # the normal QWidget hierarchy (no QMenu/QComboBox/Qt.Popup).
                # A floating popup was tried twice (QComboBox, then
                # QPushButton+QMenu) and both were unreliable inside the
                # Integrated RETINA LAB in real use — see
                # docs/design/10_gpu_audio_003.md. Same interaction model as
                # the Integrated LAB (src/toroidamp/ui/fullscreen.py).
                btn_src = QPushButton(f"AUDIO: {curr_src}", card)
                btn_src.setStyleSheet("""
                    QPushButton {
                        background: #1a1e2e;
                        color: #00f0ff;
                        font-family: monospace;
                        font-size: 8px;
                        font-weight: bold;
                        border: 1px solid #2e384d;
                        border-radius: 2px;
                        padding: 2px 4px;
                    }
                    QPushButton:hover {
                        background: #00f0ff;
                        color: #000000;
                    }
                """)

                lbl_amt = QLabel(f"{curr_amt:+4.2f}", card)
                lbl_amt.setStyleSheet("color: #ff0077; font-family: monospace; font-size: 8px; border: none;")

                slider_amt = QSlider(Qt.Horizontal, card)
                slider_amt.setRange(-200, 200)  # -2.00 .. +2.00
                slider_amt.setValue(int(round(curr_amt * 100.0)))
                slider_amt.setStyleSheet("""
                    QSlider::groove:horizontal { height: 3px; background: #1c2035; border-radius: 1px; }
                    QSlider::sub-page:horizontal { background: #ff0077; border-radius: 1px; }
                    QSlider::handle:horizontal { background: #ff0077; border: 1px solid #ffffff; width: 8px; margin: -2px 0; border-radius: 4px; }
                """)

                h_audio.addWidget(btn_src)
                h_audio.addWidget(lbl_amt)
                h_audio.addWidget(slider_amt)
                c_layout.addLayout(h_audio)

                sources = ["NONE", "BASS", "MIDS", "TREBLE", "BEAT", "STRONG BEAT", "RMS", "PEAK"]

                selector = QFrame(card)
                selector.setStyleSheet("""
                    QFrame {
                        background-color: #121520;
                        border: 1px solid #00f0ff;
                        border-radius: 2px;
                    }
                """)
                selector_grid = QGridLayout(selector)
                selector_grid.setContentsMargins(3, 3, 3, 3)
                selector_grid.setSpacing(2)

                src_btn_style = """
                    QPushButton {
                        background: #1a1e2e;
                        color: #ffffff;
                        font-family: monospace;
                        font-size: 8px;
                        font-weight: bold;
                        border: 1px solid #2e384d;
                        border-radius: 2px;
                        padding: 3px 4px;
                    }
                    QPushButton:hover {
                        border-color: #00f0ff;
                    }
                    QPushButton:checked {
                        background: #00f0ff;
                        color: #000000;
                        border-color: #00f0ff;
                    }
                """
                src_group = QButtonGroup(selector)
                src_group.setExclusive(True)

                def make_audio_source_cb(name=p_name, btn=btn_src, s_amt=slider_amt, sel=selector):
                    def on_source_select(src: str):
                        btn.setText(f"AUDIO: {src}")
                        amt = s_amt.value() / 100.0
                        self.canvas.set_param_audio_binding(name, src, amt)
                        sel.setVisible(False)
                        if self._active_audio_selector_frame is sel:
                            self._active_audio_selector_frame = None
                    return on_source_select

                src_handler = make_audio_source_cb()
                for idx, s in enumerate(sources):
                    src_btn = QPushButton(s, selector)
                    src_btn.setCheckable(True)
                    src_btn.setStyleSheet(src_btn_style)
                    src_btn.setChecked(s == curr_src)

                    def make_select_cb(s_val=s, h=src_handler):
                        return lambda checked: h(s_val) if checked else None
                    src_btn.toggled.connect(make_select_cb())

                    src_group.addButton(src_btn)
                    selector_grid.addWidget(src_btn, idx // 2, idx % 2)

                selector.setVisible(False)
                c_layout.addWidget(selector)

                def make_toggle_selector_cb(sel=selector):
                    def on_toggle_selector():
                        opening = not sel.isVisible()
                        prev = self._active_audio_selector_frame
                        if prev is not None and prev is not sel:
                            prev.setVisible(False)
                        sel.setVisible(opening)
                        self._active_audio_selector_frame = sel if opening else None
                    return on_toggle_selector

                btn_src.clicked.connect(make_toggle_selector_cb())

                def make_audio_amt_cb(name=p_name, btn=btn_src, s_amt=slider_amt, l_amt=lbl_amt):
                    def on_amt_change():
                        src, _ = self.canvas.get_param_audio_binding(name)
                        amt = s_amt.value() / 100.0
                        l_amt.setText(f"{amt:+4.2f}")
                        self.canvas.set_param_audio_binding(name, src, amt)
                    return on_amt_change

                slider_amt.valueChanged.connect(make_audio_amt_cb())

                self._param_slider_widgets[p_name] = slider
                self._param_val_labels[p_name] = lbl_val

            self.param_layout.addWidget(card)

        self.param_layout.addStretch()

    def reset_parameters(self):
        self.canvas.reset_params()
        self._rebuild_parameter_ui()

    def _on_profile_changed(self, idx: int):
        if 0 <= idx < len(PROFILE_ORDER):
            self.active_profile_name = PROFILE_ORDER[idx]

    def _inject_manual_beat(self):
        self._manual_beat_trigger = True

    def _inject_manual_strong_beat(self):
        self._manual_strong_beat_trigger = True

    def _update_ui_state(self, compile_ok: bool):
        mode_str = f"ACTIVE: {self.canvas.active_shader_name}"
        if self.canvas.metadata:
            mode_str += f" ({self.canvas.metadata.description})"
        if self.canvas.is_using_fallback:
            mode_str += " [FALLBACK SAFETY MODE]"
        self.lbl_shader_status.setText(mode_str)

        if not compile_ok or self.canvas.last_error_log:
            self.error_view.setText(self.canvas.last_error_log)
        else:
            self.error_view.setText(f"[OK] Shader '{self.canvas.active_shader_name}' compiled & linked successfully.")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.btn_fs.setText("⛶ FULLSCREEN (F11)")
        else:
            self.showFullScreen()
            self.btn_fs.setText("✕ EXIT FULLSCREEN (ESC/F11)")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_F11, Qt.Key_F):
            self.toggle_fullscreen()
        elif event.key() == Qt.Key_Escape and self.isFullScreen():
            self.toggle_fullscreen()
        elif event.key() == Qt.Key_R:
            self.reload_shader()
        elif event.key() == Qt.Key_Space:
            self._inject_manual_beat()
        elif event.key() == Qt.Key_Return:
            self._inject_manual_strong_beat()
        elif event.key() == Qt.Key_1:
            self.switch_shader_path(self.official_shader_dir / "toroid_identity.frag")
        elif event.key() == Qt.Key_2:
            self.switch_shader_path(self.official_shader_dir / "minimal_reference.frag")
        elif event.key() == Qt.Key_3:
            self.switch_shader_path(self.exp_shader_dir / "shader_a_plasma.frag")
        elif event.key() == Qt.Key_4:
            self.switch_shader_path(self.exp_shader_dir / "shader_b_raymarch.frag")
        else:
            super().keyPressEvent(event)

    def _on_tick(self):
        prof = self.profile_instances.get(self.active_profile_name)
        if prof:
            if self._manual_beat_trigger:
                prof.inject_beat(strong=False)
                self._manual_beat_trigger = False
            if self._manual_strong_beat_trigger:
                prof.inject_beat(strong=True)
                self._manual_strong_beat_trigger = False

            frame = prof.tick(0.016)
        else:
            frame = AudioFrame(0.0, 0.0, 0.0, 0.0, 0.0, tuple([0.0]*64), tuple([0.0]*128), False, False)

        self.telemetry_widget.update_frame(frame)
        self.canvas.update_audio_frame(frame)
        self.canvas.update()

        times = self.canvas.frame_times
        if times:
            w, h = self.canvas.width(), self.canvas.height()
            self.lbl_telemetry.setText(
                f"FPS: {self.canvas.last_fps:5.1f} | CPU Paint: {self.canvas.last_render_dt_ms:5.2f} ms | Res: {w}x{h}"
            )

    def closeEvent(self, event):
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.cleanupGL()
        super().closeEvent(event)


def run_gpu_lab():
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication.instance() or QApplication(sys.argv)
    lab = GPUAuthoringLabWindow()
    lab.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_gpu_lab())
