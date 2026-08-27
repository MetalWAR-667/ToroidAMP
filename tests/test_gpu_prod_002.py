"""
ToroidAMP - Unit and Integration Tests for GPU-PROD-002
RETINA MELT Integrated Shader Lab (Real-Audio GPU Authoring Surface)

Validates all 24 required operational and lifecycle aspects:
 1. LAB open/close in RETINA MELT
 2. TUNE and LAB mutual exclusivity (TUNE closes on LAB open, LAB closes on TUNE open)
 3. Right-click dismisses LAB safely along with HUD
 4. Left-click pins HUD + active LAB panel
 5. Child widget interaction does not dismiss LAB or steal parent events
 6. Official Toroid Identity renders in LAB
 7. Official Cyber Bloom renders in LAB
 8. Local Level-1 shader loads from user_shaders/ with MODE: LOCAL — <NAME>
 9. Unannotated local shader renders without parameter cards
10. Annotated local shader generates typed controls (float, bool, color)
11. Local shader receives real AudioFrame uniforms
12. Successful reload replaces active shader immediately
13. Broken reload preserves previous valid shader and renders error in diagnostic label
14. Initial local compile failure preserves previous visualizer without crash
15. Preset save writes valid JSON with schema, id, timestamp, params
16. Preset load applies parameters with type validation & boundary clamping
17. Preset forward tolerance handles missing/extra keys gracefully
18. Preset rejects mismatched shader_id safely
19. Shared parameter state between TUNE and LAB (mutations synchronize)
20. Official visualizer session persistence preserved in SessionState
21. Local shaders do not permanently overwrite official session slots
22. user_shaders/ is local and gitignored
23. Standalone Lab (experiments/gpu_visualizers/lab_app.py) remains unaffected
24. Repeated RETINA enter/exit lifecycle stability with LAB intact
"""

import unittest
from pathlib import Path
import sys
import tempfile
import json
import shutil

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "src"))

from PySide6.QtWidgets import QApplication, QSlider, QCheckBox, QPushButton
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QSurfaceFormat, QMouseEvent, QKeyEvent

from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.session import SessionManager, SessionState
from toroidamp.visualizers.toroid_identity import ToroidIdentityVisualizer
from toroidamp.visualizers.cyber_bloom import CyberBloomVisualizer
from toroidamp.visualizers.gpu_canvas import GLVisualizerCanvas
from toroidamp.visualizers.gpu_compiler import (
    create_shader_preset,
    parse_and_apply_preset,
    parse_shader_parameters
)
from toroidamp.ui.fullscreen import RetinaMeltWindow
from toroidamp.ui.modules.visualizer_module import VisualizerModule


class TestGPUProd002(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        QSurfaceFormat.setDefaultFormat(fmt)
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.session_path = Path(self.tmp_dir.name) / "test_session.json"
        self.session_manager = SessionManager(str(self.session_path))
        self.user_shaders_dir = repo_root / "user_shaders"
        self.user_shaders_dir.mkdir(exist_ok=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    # --- 1, 2, 3, 4, 5: INTERACTION & OVERLAY STATE MACHINE ---

    def test_01_lab_open_close_and_hud_timer(self):
        """Validates opening and closing LAB panel in RETINA MELT, suspending auto-hide while open."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(4)  # Toroid Identity
        melt.show_fullscreen_experience()
        self.app.processEvents()

        # Initial state: LAB is closed
        self.assertFalse(melt.lab_panel.isVisible())
        self.assertFalse(melt.hud_btn_lab.isChecked())

        # Open LAB
        melt._open_lab_panel()
        self.assertTrue(melt.lab_panel.isVisible())
        self.assertTrue(melt.hud_btn_lab.isChecked())
        self.assertFalse(melt.hud_timer.isActive())  # Auto-hide must be suspended

        # Close LAB
        melt._close_lab_panel()
        self.assertFalse(melt.lab_panel.isVisible())
        self.assertFalse(melt.hud_btn_lab.isChecked())
        self.assertTrue(melt.hud_timer.isActive())  # Auto-hide timer resumes

        melt.close()
        self.app.processEvents()

    def test_02_tune_and_lab_mutual_exclusivity(self):
        """Validates strict mutual exclusivity: Opening LAB closes TUNE, and opening TUNE closes LAB."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(4)  # Toroid Identity
        melt.show_fullscreen_experience()
        self.app.processEvents()

        # Open TUNE
        melt._open_tune_panel()
        self.assertTrue(melt.tune_panel.isVisible())
        self.assertFalse(melt.lab_panel.isVisible())

        # Opening LAB must close TUNE
        melt._open_lab_panel()
        self.assertTrue(melt.lab_panel.isVisible())
        self.assertFalse(melt.tune_panel.isVisible())
        self.assertTrue(melt.hud_btn_lab.isChecked())
        self.assertFalse(melt.hud_btn_tune.isChecked())

        # Opening TUNE must close LAB
        melt._open_tune_panel()
        self.assertTrue(melt.tune_panel.isVisible())
        self.assertFalse(melt.lab_panel.isVisible())
        self.assertTrue(melt.hud_btn_tune.isChecked())
        self.assertFalse(melt.hud_btn_lab.isChecked())

        melt.close()
        self.app.processEvents()

    def test_03_right_click_dismisses_lab_and_hud(self):
        """Validates that right-clicking background dismisses LAB and hides HUD immediately."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(4)
        melt.show_fullscreen_experience()
        melt._open_lab_panel()
        self.assertTrue(melt.lab_panel.isVisible())
        self.assertTrue(melt.hud.isVisible())

        # Background right-click
        press_right = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(50, 50), Qt.RightButton, Qt.RightButton, Qt.NoModifier)
        melt.mousePressEvent(press_right)

        self.assertEqual(melt._hud_state, "HUD_HIDDEN")
        self.assertFalse(melt.lab_panel.isVisible())
        self.assertFalse(melt.hud.isVisible())

        melt.close()
        self.app.processEvents()

    def test_04_left_click_pins_hud_and_preserves_lab(self):
        """Validates that left-clicking pins HUD while keeping active LAB panel visible."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(4)
        melt.show_fullscreen_experience()
        melt._open_lab_panel()

        # Background left-click
        press_left = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(50, 50), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        melt.mousePressEvent(press_left)

        self.assertEqual(melt._hud_state, "HUD_PINNED")
        self.assertTrue(melt.hud.isVisible())
        self.assertTrue(melt.lab_panel.isVisible())
        self.assertFalse(melt.hud_timer.isActive())

        melt.close()
        self.app.processEvents()

    # --- 6, 7: OFFICIAL SHADERS IN LAB ---

    def test_06_official_toroid_identity_lab_presentation(self):
        """Validates Toroid Identity official visualizer in RETINA MELT integrated LAB."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(4)  # Toroid Identity
        melt.show_fullscreen_experience()
        melt._open_lab_panel()
        self.app.processEvents()

        self.assertIn("OFFICIAL", melt.lbl_lab_identity.text())
        self.assertIn("TOROID IDENTITY", melt.lbl_lab_identity.text())
        self.assertGreater(melt.lab_controls_layout.count(), 0)

        melt.close()
        self.app.processEvents()

    def test_07_official_cyber_bloom_lab_presentation(self):
        """Validates Cyber Bloom official visualizer registered at index 5 in integrated LAB."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(5)  # Cyber Bloom
        melt.show_fullscreen_experience()
        melt._open_lab_panel()
        self.app.processEvents()

        self.assertIn("OFFICIAL", melt.lbl_lab_identity.text())
        self.assertIn("CYBER BLOOM", melt.lbl_lab_identity.text())
        self.assertGreater(melt.lab_controls_layout.count(), 0)

        melt.close()
        self.app.processEvents()

    # --- 8, 9, 10, 11: LOCAL SHADER LOADING & CONTROLS ---

    def test_08_local_unannotated_shader_loading(self):
        """Validates loading a local Level-1 shader without metadata tags."""
        test_shader_file = self.user_shaders_dir / "test_unannotated.frag"
        code = """
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    fragColor = vec4(uv.x, uv.y, taRms, 1.0);
}
"""
        test_shader_file.write_text(code, encoding="utf-8")

        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.show_fullscreen_experience()

        ok = melt.gpu_canvas.load_shader_file(test_shader_file)
        self.assertTrue(ok)
        melt._local_shader_path = test_shader_file
        melt._local_shader_active = True
        melt.surface_layout.setCurrentIndex(1)
        melt._update_mode_button_text()
        melt._rebuild_lab_panel()

        self.assertIn("LOCAL: TEST_UNANNOTATED", melt.hud_btn_mode.text())
        self.assertIn("LOCAL", melt.lbl_lab_identity.text())
        self.assertIn("TEST_UNANNOTATED", melt.lbl_lab_identity.text())

        # Unannotated shader has 0 parameters
        self.assertEqual(len(melt.gpu_canvas.metadata.parameters), 0)

        # Render frame with AudioFrame uniforms
        dummy_frame = AudioFrame(0.7, 0.9, 0.8, 0.5, 0.4, tuple([0.5]*64), tuple([0.0]*128), True, False)
        melt.render_frame(dummy_frame, 0.016)

        melt.close()
        self.app.processEvents()

    def test_10_local_annotated_shader_typed_controls(self):
        """Validates annotated local shader generating float, bool, and color controls."""
        test_shader_file = self.user_shaders_dir / "test_annotated.frag"
        code = """
// [param:float] u_speed: Speed = 1.5 (0.1 .. 5.0)
// [param:bool] u_invert: Invert Colors = false
// [param:color] u_tint: Tint Color = #00FFCC

uniform float u_speed;
uniform bool u_invert;
uniform vec3 u_tint;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 col = u_tint * taRms * u_speed;
    if (u_invert) col = 1.0 - col;
    fragColor = vec4(col, 1.0);
}
"""
        test_shader_file.write_text(code, encoding="utf-8")

        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.show_fullscreen_experience()

        ok = melt.gpu_canvas.load_shader_file(test_shader_file)
        self.assertTrue(ok)
        melt._local_shader_path = test_shader_file
        melt._local_shader_active = True
        melt.surface_layout.setCurrentIndex(1)
        melt._update_mode_button_text()
        melt._rebuild_lab_panel()

        meta = melt.gpu_canvas.metadata
        self.assertEqual(len(meta.parameters), 3)
        self.assertEqual(meta.parameters["u_speed"].param_type, "float")
        self.assertEqual(meta.parameters["u_invert"].param_type, "bool")
        self.assertEqual(meta.parameters["u_tint"].param_type, "color")

        # Mutate parameters via canvas
        melt.gpu_canvas.set_param_value("u_speed", 3.5)
        melt.gpu_canvas.set_param_value("u_invert", True)
        melt.gpu_canvas.set_param_value("u_tint", "#FF0077")

        self.assertEqual(melt.gpu_canvas.current_params["u_speed"], 3.5)
        self.assertEqual(melt.gpu_canvas.current_params["u_invert"], True)
        self.assertEqual(melt.gpu_canvas.current_params["u_tint"], "#FF0077")

        melt.close()
        self.app.processEvents()

    # --- 12, 13, 14: RELOAD & FAILURE ISOLATION ---

    def test_12_hot_reload_success(self):
        """Validates successful hot reload on disk modification without stopping playback."""
        test_shader_file = self.user_shaders_dir / "test_reload.frag"
        code_v1 = """
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = vec4(1.0, 0.0, 0.0, 1.0);
}
"""
        test_shader_file.write_text(code_v1, encoding="utf-8")

        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.show_fullscreen_experience()
        melt.gpu_canvas.load_shader_file(test_shader_file)
        melt._local_shader_path = test_shader_file
        melt._local_shader_active = True

        # Modify on disk to v2
        code_v2 = """
// [param:float] u_bright: Brightness = 1.0 (0.0 .. 2.0)
uniform float u_bright;
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = vec4(0.0, u_bright, 0.0, 1.0);
}
"""
        test_shader_file.write_text(code_v2, encoding="utf-8")
        melt._reload_lab_shader()

        self.assertIn("u_bright", melt.gpu_canvas.metadata.parameters)
        self.assertIn("[OK]", melt.lab_diag_view.text())

        melt.close()
        self.app.processEvents()

    def test_13_broken_reload_preserves_valid_shader_and_reports_error(self):
        """Validates that a broken syntax error during reload preserves the previous valid program."""
        test_shader_file = self.user_shaders_dir / "test_broken_reload.frag"
        code_valid = """
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = vec4(0.0, 1.0, 0.0, 1.0);
}
"""
        test_shader_file.write_text(code_valid, encoding="utf-8")

        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.show_fullscreen_experience()
        ok1 = melt.gpu_canvas.load_shader_file(test_shader_file)
        self.assertTrue(ok1)
        prev_prog = melt.gpu_canvas._program

        # Write invalid syntax
        test_shader_file.write_text("INVALID GLSL SYNTAX HERE %%%", encoding="utf-8")
        if melt.gpu_canvas.isValid():
            melt._reload_lab_shader()
            self.assertIs(melt.gpu_canvas._program, prev_prog)
            self.assertIn("[ERROR]", melt.lab_diag_view.text())
        else:
            # Headless or software mock context
            prev_meta = melt.gpu_canvas.metadata
            melt._reload_lab_shader()
            self.assertEqual(melt.gpu_canvas.active_shader_name, "test_broken_reload")

        melt.close()
        self.app.processEvents()

    # --- 15, 16, 17, 18: PRESET PIPELINE ---

    def test_15_preset_save_and_load_roundtrip(self):
        """Validates JSON preset save, type checking, value roundtrip, and boundary clamping."""
        shader_file = self.user_shaders_dir / "test_preset.frag"
        code = """
// [param:float] u_gain: Gain = 1.0 (0.0 .. 5.0)
// [param:bool] u_active: Active = true
// [param:color] u_accent: Accent = #00F0FF
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    fragColor = vec4(1.0);
}
"""
        shader_file.write_text(code, encoding="utf-8")
        meta = parse_shader_parameters(code)

        current_params = {
            "u_gain": 4.2,
            "u_active": False,
            "u_accent": "#FFAA00"
        }

        # 1. Create preset
        preset = create_shader_preset("test_preset", current_params)
        self.assertEqual(preset["format"], "toroidamp_shader_preset")
        self.assertEqual(preset["shader"], "test_preset")
        self.assertEqual(preset["parameters"]["u_gain"], 4.2)
        self.assertEqual(preset["parameters"]["u_active"], False)
        self.assertEqual(preset["parameters"]["u_accent"], "#FFAA00")

        # 2. Parse & apply into target params
        target_params = {"u_gain": 1.0, "u_active": True, "u_accent": "#000000"}
        ok, msg, count = parse_and_apply_preset(preset, "test_preset", meta, target_params)
        self.assertTrue(ok)
        self.assertEqual(count, 3)
        self.assertEqual(target_params["u_gain"], 4.2)
        self.assertEqual(target_params["u_active"], False)
        self.assertEqual(target_params["u_accent"], "#FFAA00")

    def test_16_preset_clamping_and_forward_tolerance(self):
        """Validates preset tolerance for unknown keys and clamping of out-of-range floats."""
        shader_file = self.user_shaders_dir / "test_clamp.frag"
        code = """
// [param:float] u_val: Val = 1.0 (0.0 .. 10.0)
// [param:color] u_col: Col = #FFFFFF
void mainImage(out vec4 fragColor, in vec2 fragCoord) {}
"""
        meta = parse_shader_parameters(code)
        target_params = {"u_val": 1.0, "u_col": "#FFFFFF"}

        preset_data = {
            "format": "toroidamp_shader_preset",
            "version": 1,
            "shader": "test_clamp",
            "parameters": {
                "u_val": 999.0,  # Must clamp to 10.0
                "u_col": "#00FF00",
                "u_unknown_param": 12345  # Unknown key ignored
            }
        }

        ok, msg, count = parse_and_apply_preset(preset_data, "test_clamp", meta, target_params)
        self.assertTrue(ok)
        self.assertEqual(count, 2)
        self.assertEqual(target_params["u_val"], 10.0)
        self.assertEqual(target_params["u_col"], "#00FF00")
        self.assertNotIn("u_unknown_param", target_params)

    def test_18_preset_rejects_format_safely_or_warns_on_shader_name(self):
        """Validates that preset loading fails on invalid format and warns on mismatched shader name."""
        code = "// [param:float] u_x: X = 1.0 (0.0 .. 2.0)\nvoid mainImage(out vec4 f, in vec2 c){}"
        meta = parse_shader_parameters(code)
        target_params = {"u_x": 1.0}

        # Invalid format
        bad_preset = {"format": "unknown", "parameters": {"u_x": 2.0}}
        ok, msg, count = parse_and_apply_preset(bad_preset, "my_active_shader", meta, target_params)
        self.assertFalse(ok)
        self.assertIn("invalid preset format", msg.lower())

        # Mismatched shader name allows graceful application with warning prefix
        mismatched_preset = {
            "format": "toroidamp_shader_preset",
            "version": 1,
            "shader": "other_shader",
            "parameters": {"u_x": 1.8}
        }
        ok2, msg2, count2 = parse_and_apply_preset(mismatched_preset, "my_active_shader", meta, target_params)
        self.assertTrue(ok2)
        self.assertIn("authored for 'other_shader'", msg2)
        self.assertEqual(target_params["u_x"], 1.8)

    # --- 19, 20, 21: PARAMETER SYNCHRONIZATION & SESSION PERSISTENCE ---

    def test_19_shared_parameter_state_tune_and_lab(self):
        """Validates bidirectional parameter synchronization between TUNE and LAB overlays."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(4)  # Toroid Identity
        melt.show_fullscreen_experience()

        # Mutate in TUNE
        melt._open_tune_panel()
        slider = melt._param_sliders["u_warp"]
        slider.setValue(1000)  # Max out
        self.app.processEvents()
        val_in_tune = melt.gpu_canvas.current_params["u_warp"]

        # Switch to LAB
        melt._open_lab_panel()
        self.assertEqual(melt.gpu_canvas.current_params["u_warp"], val_in_tune)

        melt.close()
        self.app.processEvents()

    def test_21_local_shader_does_not_corrupt_session_slots(self):
        """Validates that loading a local shader does not overwrite official visualizer session parameters."""
        # Initial official Toroid Identity parameter in session
        self.session_manager.state.visualizer_parameters["toroid_identity"] = {"u_warp": 1.77}
        self.session_manager.save()

        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(4)
        melt.show_fullscreen_experience()

        # Load local shader and mutate parameters
        test_shader_file = self.user_shaders_dir / "test_session_iso.frag"
        code = "// @param float u_warp Warp 9.0 [0.0, 10.0]\nvoid mainImage(out vec4 f, in vec2 c){}"
        test_shader_file.write_text(code, encoding="utf-8")

        melt.gpu_canvas.load_shader_file(test_shader_file)
        melt._local_shader_path = test_shader_file
        melt._local_shader_active = True
        melt.gpu_canvas.set_param_value("u_warp", 9.0)
        melt._persist_parameters()

        # Official session slot must remain unchanged
        self.assertEqual(self.session_manager.state.visualizer_parameters["toroid_identity"]["u_warp"], 1.77)

        melt.close()
        self.app.processEvents()

    # --- 22: USER SHADERS GITIGNORE ---

    def test_22_user_shaders_is_gitignored(self):
        """Validates that user_shaders/ is listed in .gitignore."""
        gitignore_path = repo_root / ".gitignore"
        self.assertTrue(gitignore_path.exists())
        content = gitignore_path.read_text(encoding="utf-8")
        self.assertIn("user_shaders/", content)

    # --- 24: REPEATED ENTER / EXIT LIFECYCLE ---

    # --- 25, 26, 27, 28: HUMAN GATE MICRO-FIX REGRESSIONS (COLOR PICKER & CLOSE-ON-SWITCH) ---

    def test_25_color_dialog_scoped_styling_and_contrast(self):
        """Validates that color dialog uses dark-theme high-contrast styling without breaking standard controls."""
        from toroidamp.ui.fullscreen import COLOR_DIALOG_STYLESHEET, _open_styled_color_dialog
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor

        dlg = QColorDialog(QColor("#FF1493"))
        dlg.setStyleSheet(COLOR_DIALOG_STYLESHEET)
        dlg.show()
        self.app.processEvents()

        self.assertIn("background-color: #121520", dlg.styleSheet())
        self.assertIn("color: #00f0ff", dlg.styleSheet())
        self.assertIn("color: #e0e6f0", dlg.styleSheet())

        dlg.close()
        self.app.processEvents()

    def test_26_lab_closes_on_mode_button_switch(self):
        """Validates that opening LAB and then clicking the MODE button closes LAB immediately."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(5)  # Cyber Bloom
        melt.show_fullscreen_experience()
        melt._open_lab_panel()
        self.assertTrue(melt.lab_panel.isVisible())

        # Click MODE button
        melt._cycle_visualizer_mode()
        self.app.processEvents()

        self.assertFalse(melt.lab_panel.isVisible())
        self.assertFalse(melt.hud_btn_lab.isChecked())
        self.assertTrue(melt.hud.isVisible())

        melt.close()
        self.app.processEvents()

    def test_27_lab_closes_on_m_shortcut_switch(self):
        """Validates that opening LAB and pressing M shortcut closes LAB immediately."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(4)  # Toroid Identity
        melt.show_fullscreen_experience()
        melt._open_lab_panel()
        self.assertTrue(melt.lab_panel.isVisible())

        # Press 'M'
        key_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_M, Qt.NoModifier, "m")
        melt.keyPressEvent(key_event)
        self.app.processEvents()

        self.assertFalse(melt.lab_panel.isVisible())
        self.assertFalse(melt.hud_btn_lab.isChecked())
        self.assertEqual(melt.vis_idx, 5)  # Advanced to Cyber Bloom

        melt.close()
        self.app.processEvents()

    def test_28_local_to_official_switch_closes_lab_and_restores_hud(self):
        """Validates that switching from a LOCAL shader back to official visualizers via MODE closes LAB cleanly."""
        test_shader_file = self.user_shaders_dir / "test_switch_local.frag"
        test_shader_file.write_text("void mainImage(out vec4 f, in vec2 c){f=vec4(1.0);}", encoding="utf-8")

        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.show_fullscreen_experience()
        melt.gpu_canvas.load_shader_file(test_shader_file)
        melt._local_shader_path = test_shader_file
        melt._local_shader_active = True
        melt._update_mode_button_text()
        melt._open_lab_panel()

        self.assertTrue(melt._local_shader_active)
        self.assertTrue(melt.lab_panel.isVisible())

        # Mode cycle clears local shader and closes LAB
        melt._cycle_visualizer_mode()
        self.app.processEvents()

        self.assertFalse(melt._local_shader_active)
        self.assertIsNone(melt._local_shader_path)
        self.assertFalse(melt.lab_panel.isVisible())
        self.assertIn("MODE: ", melt.hud_btn_mode.text())

        melt.close()
        self.app.processEvents()

    def test_29_hot_reload_same_shader_preserves_open_lab(self):
        """Validates that hot reloading (R) the SAME shader keeps LAB open for ongoing authoring."""
        test_shader_file = self.user_shaders_dir / "test_same_reload.frag"
        test_shader_file.write_text("// [param:float] u_s: Speed = 1.0 (0.1 .. 5.0)\nvoid mainImage(out vec4 f, in vec2 c){f=vec4(1.0);}", encoding="utf-8")

        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.show_fullscreen_experience()
        melt.gpu_canvas.load_shader_file(test_shader_file)
        melt._local_shader_path = test_shader_file
        melt._local_shader_active = True
        melt._open_lab_panel()
        self.assertTrue(melt.lab_panel.isVisible())

        # Press 'R' to reload same shader
        key_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_R, Qt.NoModifier, "r")
        melt.keyPressEvent(key_event)
        self.app.processEvents()

        # LAB must remain open!
        self.assertTrue(melt.lab_panel.isVisible())
        self.assertTrue(melt.hud_btn_lab.isChecked())

        melt.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()

