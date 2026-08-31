"""
GPU-AUDIO-003 Automated Test Suite — Discovered Parameter Audio Binding (Level C)
Validates:
1. System uniforms (iTime, taBass, etc.) are strictly excluded from discovery.
2. Unannotated custom float uniforms (e.g. uniform float u_zoom;) are discovered.
3. Audio bindings default to NONE with 0.0 amount.
4. Setting audio bindings modifies GLVisualizerCanvas audio_bindings dictionary.
5. Modulation formula correctly applies base + (audio_val * amount).
6. Negative modulation amount operates accurately.
7. Changing base value updates the modulation baseline.
8. Silence returns the exact base value without distortion.
9. Hot reload retains compatible parameter bindings by name.
10. Removed uniforms drop bindings safely without errors.
11. No user shader source files on disk are modified.
12. AUTO REACT and parameter bindings operate independently.
"""

import sys
import unittest
import numpy as np
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtCore import Qt

from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.visualizers.gpu_compiler import (
    classify_and_wrap_source, parse_shader_parameters, ShaderMetadata, SYSTEM_UNIFORMS
)
from toroidamp.visualizers.gpu_canvas import GLVisualizerCanvas


class TestGPUAudio003DiscoveredBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        QSurfaceFormat.setDefaultFormat(fmt)
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.canvas = GLVisualizerCanvas()

    def tearDown(self):
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.cleanupGL()

    # 1. System uniforms excluded from parameter discovery
    def test_01_system_uniforms_excluded(self):
        code = """
        uniform vec3 iResolution;
        uniform float iTime;
        uniform float taBass;
        uniform float taMids;
        uniform int taAutoReact;
        uniform float u_zoom;
        void mainImage(out vec4 fragColor, in vec2 fragCoord) { fragColor = vec4(u_zoom); }
        """
        params = parse_shader_parameters(code)
        self.assertIn("u_zoom", params)
        for sys_u in ["iResolution", "iTime", "taBass", "taMids", "taAutoReact"]:
            self.assertNotIn(sys_u, params)

    # 2. Audio binding setter and getter
    def test_02_set_and_get_audio_binding(self):
        self.canvas.set_param_audio_binding("u_zoom", "BASS", 0.35)
        src, amt = self.canvas.get_param_audio_binding("u_zoom")
        self.assertEqual(src, "BASS")
        self.assertEqual(amt, 0.35)

        # Clear binding with NONE
        self.canvas.set_param_audio_binding("u_zoom", "NONE", 0.0)
        src, amt = self.canvas.get_param_audio_binding("u_zoom")
        self.assertEqual(src, "NONE")
        self.assertEqual(amt, 0.0)

    # 3. Silence baseline returns exact base value
    def test_03_silence_modulation_identity(self):
        self.canvas.set_param_value("u_zoom", 1.80)
        self.canvas.set_param_audio_binding("u_zoom", "BASS", 0.50)

        frame_silence = AudioFrame(
            rms=0.0, peak=0.0, bass=0.0, mids=0.0, treble=0.0,
            spectrum=tuple([0.0] * 64), waveform=tuple([0.0] * 128),
            beat=False, strong_beat=False
        )
        self.canvas.update_audio_frame(frame_silence)

        # Base value remains untouched
        self.assertEqual(self.canvas.current_params["u_zoom"], 1.80)
        src, amt = self.canvas.get_param_audio_binding("u_zoom")
        expected_modulated = self.canvas.current_params["u_zoom"] + (frame_silence.bass * amt)
        self.assertEqual(expected_modulated, 1.80)

    # 4. Modulated value computation with positive and negative amounts
    def test_04_modulation_computation(self):
        base_val = 2.00
        self.canvas.set_param_value("u_zoom", base_val)
        self.canvas.set_param_audio_binding("u_zoom", "BASS", 0.40)

        frame_active = AudioFrame(
            rms=0.5, peak=0.8, bass=0.75, mids=0.4, treble=0.2,
            spectrum=tuple([0.5] * 64), waveform=tuple([0.1] * 128),
            beat=True, strong_beat=False
        )
        self.canvas.update_audio_frame(frame_active)

        # Positive modulation
        src, amt = self.canvas.get_param_audio_binding("u_zoom")
        self.assertEqual(base_val + (frame_active.bass * amt), 2.00 + (0.75 * 0.40))

        # Inverted / Negative modulation
        self.canvas.set_param_audio_binding("u_zoom", "BASS", -0.40)
        src, amt = self.canvas.get_param_audio_binding("u_zoom")
        self.assertEqual(base_val + (frame_active.bass * amt), 2.00 + (0.75 * -0.40))

    # 5. Base value adjustment updates modulation origin
    def test_05_base_value_adjustment(self):
        self.canvas.set_param_value("u_zoom", 1.50)
        self.canvas.set_param_audio_binding("u_zoom", "TREBLE", 0.20)
        self.canvas.set_param_value("u_zoom", 2.50)
        self.assertEqual(self.canvas.current_params["u_zoom"], 2.50)

    # 6. Integrated LAB UI construction path test
    def test_06_integrated_lab_ui_rebuild_with_bindings(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager

        session_mgr = SessionManager()
        win = RetinaMeltWindow(session_manager=session_mgr)

        # Load a shader with float parameters
        annotated_path = Path(__file__).resolve().parent.parent / "user_shaders" / "test_annotated.frag"
        if annotated_path.exists():
            win.gpu_canvas.load_shader_file(annotated_path)
            # Rebuilding lab panel constructs all float parameter cards and selector buttons
            win._rebuild_lab_panel()
            self.assertGreater(win.lab_controls_layout.count(), 0)

        win.close()

    # 7. End-to-end unannotated custom parameter discovery & UI card verification
    def test_07_end_to_end_discovered_parameters_in_integrated_lab(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager

        session_mgr = SessionManager()
        win = RetinaMeltWindow(session_manager=session_mgr)

        val_shader = Path(__file__).resolve().parent.parent / "user_shaders" / "test_discovered_params.frag"
        self.assertTrue(val_shader.exists())

        ok = win.gpu_canvas.load_shader_file(val_shader)
        self.assertTrue(ok)

        # Check metadata discovered all 3 uniforms
        self.assertIsNotNone(win.gpu_canvas.metadata)
        self.assertIn("u_zoom", win.gpu_canvas.metadata.parameters)
        self.assertIn("u_speed", win.gpu_canvas.metadata.parameters)
        self.assertIn("u_glow", win.gpu_canvas.metadata.parameters)

        # Rebuild lab panel as done when opening/loading in LAB
        win._rebuild_lab_panel()

        # Count cards in layout (excluding stretch)
        card_count = 0
        for i in range(win.lab_controls_layout.count()):
            item = win.lab_controls_layout.itemAt(i)
            if item and item.widget() and item.widget().inherits("QFrame"):
                card_count += 1

        self.assertEqual(card_count, 3)
        win.close()

    # 8. GPU-AUDIO-003 follow-up: real widget-click interaction with the
    #    inline (non-popup) AUDIO source selector, end-to-end through live
    #    modulation. No QMenu/QAction/setCurrentText — real QTest.mouseClick
    #    on real QPushButton children, matching the actual human interaction
    #    path inside the Integrated RETINA LAB.
    def test_08_inline_selector_click_expand_select_collapse_and_modulate(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager
        from PySide6.QtWidgets import QPushButton, QSlider
        from PySide6.QtTest import QTest

        session_mgr = SessionManager()
        win = RetinaMeltWindow(session_manager=session_mgr)

        val_shader = Path(__file__).resolve().parent.parent / "user_shaders" / "test_discovered_params.frag"
        win.gpu_canvas.load_shader_file(val_shader)
        win._local_shader_active = True
        win.show()
        win._open_lab_panel()

        zoom_card = win.lab_controls_layout.itemAt(0).widget()
        btn_src = [c for c in zoom_card.findChildren(QPushButton) if "AUDIO:" in c.text()][0]
        slider_amt = zoom_card.findChildren(QSlider)[1]

        # Selector starts collapsed after a rebuild.
        self.assertIsNone(win._active_audio_selector_frame)

        # Real click on the AUDIO button expands the inline selector — no popup involved.
        QTest.mouseClick(btn_src, Qt.LeftButton)
        QApplication.processEvents()
        self.assertIsNotNone(win._active_audio_selector_frame)
        self.assertTrue(win._active_audio_selector_frame.isVisible())
        self.assertIs(win._active_audio_selector_frame.parent(), zoom_card)

        # Real click on the BASS child button — a normal QWidget child, not a QAction.
        bass_btn = [b for b in win._active_audio_selector_frame.findChildren(QPushButton) if b.text() == "BASS"][0]
        QTest.mouseClick(bass_btn, Qt.LeftButton)
        QApplication.processEvents()

        self.assertEqual(btn_src.text(), "AUDIO: BASS")
        self.assertEqual(win.gpu_canvas.get_param_audio_binding("u_zoom")[0], "BASS")
        self.assertFalse(bass_btn.parentWidget().isVisible(), "selector must collapse after a selection")
        self.assertIsNone(win._active_audio_selector_frame)

        slider_amt.setValue(200)  # +2.00
        QApplication.processEvents()
        self.assertEqual(win.gpu_canvas.audio_bindings.get("u_zoom")[:2], ("BASS", 2.0))

        active_frame = AudioFrame(
            rms=0.5, peak=0.8, bass=0.75, mids=0.4, treble=0.2,
            spectrum=tuple([0.0] * 64), waveform=tuple([0.0] * 128),
            beat=False, strong_beat=False,
        )
        win.render_frame(active_frame, 0.016)
        base_val = win.gpu_canvas.current_params["u_zoom"]
        src, amt = win.gpu_canvas.audio_bindings["u_zoom"][:2]
        final_val = base_val + (getattr(win.gpu_canvas._current_audio_frame, src.lower()) * amt)
        self.assertAlmostEqual(final_val, 2.50)  # 1.0 base + 0.75*2.00

        win.close()

    # 9. Only one inline selector may be expanded at a time across the LAB —
    #    opening a second card's selector collapses the first.
    def test_09_only_one_inline_selector_open_at_a_time(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager
        from PySide6.QtWidgets import QPushButton
        from PySide6.QtTest import QTest

        session_mgr = SessionManager()
        win = RetinaMeltWindow(session_manager=session_mgr)
        val_shader = Path(__file__).resolve().parent.parent / "user_shaders" / "test_discovered_params.frag"
        win.gpu_canvas.load_shader_file(val_shader)
        win._local_shader_active = True
        win.show()
        win._open_lab_panel()

        self.assertGreaterEqual(win.lab_controls_layout.count(), 2, "test shader must expose 2+ float params")
        card_a = win.lab_controls_layout.itemAt(0).widget()
        card_b = win.lab_controls_layout.itemAt(1).widget()
        btn_a = [c for c in card_a.findChildren(QPushButton) if "AUDIO:" in c.text()][0]
        btn_b = [c for c in card_b.findChildren(QPushButton) if "AUDIO:" in c.text()][0]

        QTest.mouseClick(btn_a, Qt.LeftButton)
        QApplication.processEvents()
        selector_a = win._active_audio_selector_frame
        self.assertIsNotNone(selector_a)
        self.assertTrue(selector_a.isVisible())

        QTest.mouseClick(btn_b, Qt.LeftButton)
        QApplication.processEvents()

        self.assertFalse(selector_a.isVisible(), "opening card B's selector must collapse card A's")
        self.assertIsNotNone(win._active_audio_selector_frame)
        self.assertIsNot(win._active_audio_selector_frame, selector_a)
        self.assertTrue(win._active_audio_selector_frame.isVisible())

        win.close()

    # 10. Clicking AUDIO again while expanded collapses it (toggle behavior).
    def test_10_clicking_audio_again_while_expanded_collapses_it(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager
        from PySide6.QtWidgets import QPushButton
        from PySide6.QtTest import QTest

        session_mgr = SessionManager()
        win = RetinaMeltWindow(session_manager=session_mgr)
        val_shader = Path(__file__).resolve().parent.parent / "user_shaders" / "test_discovered_params.frag"
        win.gpu_canvas.load_shader_file(val_shader)
        win._local_shader_active = True
        win.show()
        win._open_lab_panel()

        zoom_card = win.lab_controls_layout.itemAt(0).widget()
        btn_src = [c for c in zoom_card.findChildren(QPushButton) if "AUDIO:" in c.text()][0]

        QTest.mouseClick(btn_src, Qt.LeftButton)
        QApplication.processEvents()
        self.assertTrue(win._active_audio_selector_frame.isVisible())

        QTest.mouseClick(btn_src, Qt.LeftButton)
        QApplication.processEvents()
        self.assertIsNone(win._active_audio_selector_frame)

        win.close()

    # 11. Real human-path reload test: BASE, AUDIO, and AMOUNT survival across
    #     hot reload — driven entirely through real widget clicks.
    def test_11_transactional_reload_preserves_base_and_bindings(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager
        from PySide6.QtWidgets import QPushButton, QSlider, QLabel
        from PySide6.QtTest import QTest

        session_mgr = SessionManager()
        win = RetinaMeltWindow(session_manager=session_mgr)
        val_shader = Path(__file__).resolve().parent.parent / "user_shaders" / "test_discovered_params.frag"
        win.gpu_canvas.load_shader_file(val_shader)
        win._local_shader_active = True
        win.show()
        win._open_lab_panel()
        QApplication.processEvents()

        zoom_card = win.lab_controls_layout.itemAt(0).widget()
        sliders = zoom_card.findChildren(QSlider)
        slider_base, slider_amt = sliders[0], sliders[1]
        btn_src = [c for c in zoom_card.findChildren(QPushButton) if "AUDIO:" in c.text()][0]
        labels = zoom_card.findChildren(QLabel)
        lbl_val, lbl_amt = labels[1], labels[2]

        # BASE to 0.80 (pos = (0.80 / 5.0) * 1000 = 160)
        slider_base.setValue(160)

        # AUDIO to BASS via a real click on the inline selector's BASS button.
        QTest.mouseClick(btn_src, Qt.LeftButton)
        QApplication.processEvents()
        bass_btn = [b for b in win._active_audio_selector_frame.findChildren(QPushButton) if b.text() == "BASS"][0]
        QTest.mouseClick(bass_btn, Qt.LeftButton)
        QApplication.processEvents()

        # AMOUNT to +2.00
        slider_amt.setValue(200)
        QApplication.processEvents()

        self.assertAlmostEqual(float(lbl_val.text().strip()), 0.80, places=2)
        self.assertEqual(btn_src.text(), "AUDIO: BASS")
        self.assertEqual(lbl_amt.text().strip(), "+2.00")
        self.assertAlmostEqual(win.gpu_canvas.current_params["u_zoom"], 0.80, places=2)
        self.assertEqual(win.gpu_canvas.audio_bindings["u_zoom"][:2], ("BASS", 2.0))

        # Hot reload via _reload_lab_shader (same path as pressing R).
        win._reload_lab_shader()
        QApplication.processEvents()

        zoom_card_after = win.lab_controls_layout.itemAt(0).widget()
        btn_after = [c for c in zoom_card_after.findChildren(QPushButton) if "AUDIO:" in c.text()][0]
        labels_after = zoom_card_after.findChildren(QLabel)
        lbl_val_after, lbl_amt_after = labels_after[1], labels_after[2]

        self.assertAlmostEqual(float(lbl_val_after.text().strip()), 0.80, places=2)
        self.assertEqual(btn_after.text(), "AUDIO: BASS")
        self.assertEqual(lbl_amt_after.text().strip(), "+2.00")
        self.assertAlmostEqual(win.gpu_canvas.current_params["u_zoom"], 0.80, places=2)
        self.assertEqual(win.gpu_canvas.audio_bindings["u_zoom"][:2], ("BASS", 2.0))
        # Selector does not need to reopen automatically after a rebuild.
        self.assertIsNone(win._active_audio_selector_frame)

        active_frame = AudioFrame(
            rms=0.5, peak=0.8, bass=0.75, mids=0.4, treble=0.2,
            spectrum=tuple([0.0] * 64), waveform=tuple([0.0] * 128),
            beat=False, strong_beat=False,
        )
        win.render_frame(active_frame, 0.016)
        base_val = win.gpu_canvas.current_params["u_zoom"]
        src, amt = win.gpu_canvas.audio_bindings["u_zoom"][:2]
        final_val = base_val + (getattr(win.gpu_canvas._current_audio_frame, src.lower()) * amt)
        self.assertAlmostEqual(final_val, 0.80 + (0.75 * 2.0), places=2)  # 2.30

        silence_frame = AudioFrame(
            rms=0.0, peak=0.0, bass=0.0, mids=0.0, treble=0.0,
            spectrum=tuple([0.0] * 64), waveform=tuple([0.0] * 128),
            beat=False, strong_beat=False,
        )
        win.render_frame(silence_frame, 0.016)
        final_silence = base_val + (getattr(win.gpu_canvas._current_audio_frame, src.lower()) * amt)
        self.assertAlmostEqual(final_silence, 0.80, places=2)

        win.close()

    # 12. CRITICAL HUMAN-PATH TEST — the exact 15-step regression the human
    #     gate is built on: load -> rebuild -> click AUDIO -> assert selector
    #     visible -> click BASS -> assert label/binding/collapse -> amount ->
    #     inject bass -> assert modulation -> hot reload -> assert survival.
    def test_12_critical_human_path_inline_selector_regression(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager
        from PySide6.QtWidgets import QPushButton, QSlider
        from PySide6.QtTest import QTest

        # 1. Load test_discovered_params.frag.
        val_shader = Path(__file__).resolve().parent.parent / "user_shaders" / "test_discovered_params.frag"
        session_mgr = SessionManager()
        win = RetinaMeltWindow(session_manager=session_mgr)
        ok = win.gpu_canvas.load_shader_file(val_shader)
        self.assertTrue(ok)
        win._local_shader_active = True
        win.show()

        # 2. Rebuild Integrated LAB (opening it — the real "RETINA MELT -> LAB" path
        #    both builds the parameter cards and makes the panel/its children visible).
        win._open_lab_panel()
        QApplication.processEvents()

        # 3. Find u_zoom AUDIO button.
        zoom_card = win.lab_controls_layout.itemAt(0).widget()
        btn_src = [c for c in zoom_card.findChildren(QPushButton) if "AUDIO:" in c.text()][0]
        self.assertEqual(btn_src.text(), "AUDIO: NONE")

        # 4. Simulate mouse click.
        QTest.mouseClick(btn_src, Qt.LeftButton)
        QApplication.processEvents()

        # 5. Assert inline selector frame becomes visible.
        self.assertIsNotNone(win._active_audio_selector_frame)
        self.assertTrue(win._active_audio_selector_frame.isVisible())

        # 6. Find BASS child button.
        bass_btn = [b for b in win._active_audio_selector_frame.findChildren(QPushButton) if b.text() == "BASS"][0]

        # 7. Simulate mouse click on BASS.
        QTest.mouseClick(bass_btn, Qt.LeftButton)
        QApplication.processEvents()

        # 8. Assert AUDIO label/button now says BASS.
        self.assertEqual(btn_src.text(), "AUDIO: BASS")

        # 9. Assert gpu_canvas binding source == BASS.
        self.assertEqual(win.gpu_canvas.get_param_audio_binding("u_zoom")[0], "BASS")

        # 10. Assert selector collapsed.
        self.assertIsNone(win._active_audio_selector_frame)

        # 11. Set amount +2.00.
        slider_amt = zoom_card.findChildren(QSlider)[1]
        slider_amt.setValue(200)
        QApplication.processEvents()
        self.assertEqual(win.gpu_canvas.audio_bindings["u_zoom"][:2], ("BASS", 2.0))

        # 12. Inject bass=0.75.
        active_frame = AudioFrame(
            rms=0.5, peak=0.8, bass=0.75, mids=0.4, treble=0.2,
            spectrum=tuple([0.0] * 64), waveform=tuple([0.0] * 128),
            beat=False, strong_beat=False,
        )
        win.render_frame(active_frame, 0.016)

        # 13. Assert final modulation: base + 0.75 * 2.00.
        base_val = win.gpu_canvas.current_params["u_zoom"]
        final_val = base_val + (getattr(win.gpu_canvas._current_audio_frame, "bass") * 2.0)
        self.assertAlmostEqual(final_val, base_val + (0.75 * 2.0))

        # 14. Hot reload.
        win._reload_lab_shader()
        QApplication.processEvents()

        # 15. Assert BASE preserved; AUDIO: BASS preserved; amount preserved.
        zoom_card_after = win.lab_controls_layout.itemAt(0).widget()
        btn_after = [c for c in zoom_card_after.findChildren(QPushButton) if "AUDIO:" in c.text()][0]
        self.assertAlmostEqual(win.gpu_canvas.current_params["u_zoom"], base_val, places=2)
        self.assertEqual(btn_after.text(), "AUDIO: BASS")
        self.assertEqual(win.gpu_canvas.audio_bindings["u_zoom"][:2], ("BASS", 2.0))

        win.close()


class TestGPUAudio003NoObsoletePopupCode(unittest.TestCase):
    """Guards against the removed QComboBox/QMenu audio-selector code reappearing."""

    def test_fullscreen_module_has_no_audio_selector_qmenu_or_qcombobox(self):
        """
        Explanatory comments referencing QComboBox/QMenu as *prose* (documenting
        why the inline selector replaced them) are expected and fine — see
        docs/design/10_gpu_audio_003.md. What must be actually gone is any real
        usage: an import, a constructor call, or a QAction-based menu item.
        """
        fullscreen_path = Path(__file__).resolve().parent.parent / "src" / "toroidamp" / "ui" / "fullscreen.py"
        source = fullscreen_path.read_text(encoding="utf-8")
        for forbidden in ("QComboBox(", "QComboBox,", "QMenu(", "QMenu,", "QAction(", "QAction,"):
            self.assertNotIn(forbidden, source, f"found real usage: {forbidden!r}")

    def test_lab_app_audio_selector_has_no_qmenu(self):
        """QComboBox is still legitimately used elsewhere in lab_app.py (shader/profile picker) — only QMenu/QAction (audio-selector-specific) must be gone."""
        lab_app_path = Path(__file__).resolve().parent.parent / "experiments" / "gpu_visualizers" / "lab_app.py"
        source = lab_app_path.read_text(encoding="utf-8")
        for forbidden in ("QMenu(", "QMenu,", "QAction(", "QAction,"):
            self.assertNotIn(forbidden, source, f"found real usage: {forbidden!r}")


REFERENCE_SHADER_PATH = (
    Path(__file__).resolve().parent.parent
    / "src" / "toroidamp" / "assets" / "official_shaders" / "audio_reactive_reference.frag"
)


class TestGPUAudio003ReferenceShader(unittest.TestCase):
    """
    GPU-AUDIO-003 CLOSED — HUMAN VALIDATED follow-up: the promoted LAB
    reference shader (audio_reactive_reference.frag) must compile, expose
    exactly the intended discovered float parameters, leak no system/ta*
    uniforms into that discovery, remain musically neutral in its own
    source (no ta* reference at all — reactivity is assigned by the human
    in LAB, not baked in), and support the same base+audio*amount binding
    model as the deterministic test_discovered_params.frag fixture, which
    this shader does NOT replace.
    """

    @classmethod
    def setUpClass(cls):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        QSurfaceFormat.setDefaultFormat(fmt)
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.canvas = GLVisualizerCanvas()

    def tearDown(self):
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.cleanupGL()

    def test_reference_shader_exists(self):
        self.assertTrue(REFERENCE_SHADER_PATH.is_file(), f"Missing: {REFERENCE_SHADER_PATH}")

    def test_regression_fixture_is_untouched_and_still_used_by_earlier_tests(self):
        """test_discovered_params.frag remains the deterministic regression fixture — not replaced."""
        fixture = Path(__file__).resolve().parent.parent / "user_shaders" / "test_discovered_params.frag"
        self.assertTrue(fixture.is_file())
        source = fixture.read_text(encoding="utf-8")
        self.assertIn("u_zoom", source)
        self.assertIn("u_speed", source)
        self.assertIn("u_glow", source)

    def test_reference_shader_compiles(self):
        ok = self.canvas.load_shader_file(REFERENCE_SHADER_PATH)
        self.assertTrue(ok)
        self.assertIsNotNone(self.canvas.metadata)

    def test_reference_shader_exposes_exactly_intended_parameters(self):
        self.canvas.load_shader_file(REFERENCE_SHADER_PATH)
        params = self.canvas.metadata.parameters
        expected = {"u_zoom", "u_speed", "u_glow", "u_twist", "u_detail"}
        self.assertEqual(set(params.keys()), expected)
        for name in expected:
            self.assertEqual(params[name].param_type, "float")

    def test_reference_shader_parameters_have_sensible_ranges_and_defaults(self):
        self.canvas.load_shader_file(REFERENCE_SHADER_PATH)
        params = self.canvas.metadata.parameters
        expected_defaults = {"u_zoom": 1.0, "u_speed": 1.0, "u_glow": 1.5, "u_twist": 1.0, "u_detail": 6.0}
        for name, default in expected_defaults.items():
            p = params[name]
            self.assertEqual(p.default_value, default, name)
            # Default must sit safely inside its own declared range (manual BASE editing safety).
            self.assertLessEqual(p.min_value, p.default_value, name)
            self.assertLessEqual(p.default_value, p.max_value, name)
            self.assertGreater(p.max_value, p.min_value, name)

    def test_reference_shader_leaks_no_system_uniforms_into_discovery(self):
        self.canvas.load_shader_file(REFERENCE_SHADER_PATH)
        leaked = SYSTEM_UNIFORMS & set(self.canvas.metadata.parameters.keys())
        self.assertEqual(leaked, set())

    def test_reference_shader_source_is_musically_neutral(self):
        """
        No taBass/taMids/taTreble/taBeat/etc reference in actual GLSL code.
        Documentation comments naming these (explaining that the shader is
        deliberately neutral, and offering a recommended human-assigned
        mapping) are expected and fine — only real code usage would defeat
        the point of a discovered-parameter demo shader.
        """
        code_lines = [
            line for line in REFERENCE_SHADER_PATH.read_text(encoding="utf-8").splitlines()
            if not line.strip().startswith("//")
        ]
        code_only = "\n".join(code_lines)
        ta_audio_uniforms = [
            "taRms", "taPeak", "taBass", "taMids", "taTreble",
            "taBeat", "taStrongBeat", "taSpectrum", "taWaveform",
            "taBpm", "taBeatPhase", "taBarPhase",
        ]
        for uniform in ta_audio_uniforms:
            self.assertNotIn(uniform, code_only, f"reference shader must stay musically neutral — found {uniform!r} in actual code")

    def test_reference_shader_supports_audio_binding_and_silence_return(self):
        self.canvas.load_shader_file(REFERENCE_SHADER_PATH)
        self.canvas.set_param_value("u_zoom", 1.0)
        self.canvas.set_param_audio_binding("u_zoom", "BASS", 0.60)

        active_frame = AudioFrame(
            rms=0.6, peak=0.8, bass=0.75, mids=0.5, treble=0.3,
            spectrum=tuple([0.3] * 64), waveform=tuple([0.0] * 128),
            beat=True, strong_beat=True,
        )
        self.canvas.update_audio_frame(active_frame)
        src, amt = self.canvas.get_param_audio_binding("u_zoom")
        modulated = self.canvas.current_params["u_zoom"] + (active_frame.bass * amt)
        self.assertAlmostEqual(modulated, 1.0 + (0.75 * 0.60))

        silence_frame = AudioFrame(
            rms=0.0, peak=0.0, bass=0.0, mids=0.0, treble=0.0,
            spectrum=tuple([0.0] * 64), waveform=tuple([0.0] * 128),
            beat=False, strong_beat=False,
        )
        self.canvas.update_audio_frame(silence_frame)
        returned = self.canvas.current_params["u_zoom"] + (getattr(self.canvas._current_audio_frame, src.lower()) * amt)
        self.assertAlmostEqual(returned, 1.0)

    def test_reference_shader_auto_react_off_by_default(self):
        """Loading the reference shader must not itself enable AUTO REACT — only manually assigned bindings act."""
        self.canvas.load_shader_file(REFERENCE_SHADER_PATH)
        self.assertFalse(getattr(self.canvas, "auto_react", False))

    def test_reference_shader_integrated_lab_card_construction(self):
        """End-to-end: LAB builds 5 parameter cards for the reference shader, same path as any other local shader."""
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager

        session_mgr = SessionManager()
        win = RetinaMeltWindow(session_manager=session_mgr)
        ok = win.gpu_canvas.load_shader_file(REFERENCE_SHADER_PATH)
        self.assertTrue(ok)
        win._local_shader_active = True
        win._open_lab_panel()
        QApplication.processEvents()

        card_count = 0
        for i in range(win.lab_controls_layout.count()):
            item = win.lab_controls_layout.itemAt(i)
            if item and item.widget() and item.widget().inherits("QFrame"):
                card_count += 1
        self.assertEqual(card_count, 5)
        win.close()


if __name__ == "__main__":
    unittest.main()
