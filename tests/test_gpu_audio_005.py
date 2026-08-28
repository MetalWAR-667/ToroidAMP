"""
tests/test_gpu_audio_005.py — GPU-AUDIO-005: Bounded Auto Musicalization

Validates:
1.  Deterministic automatic mapping (same shader -> same result, repeatedly).
2.  Bounded relative modulation formula matches the documented policy.
3.  Zero-base fallback.
4.  Negative base.
5.  Range clamping to the parameter's declared min/max.
6.  Silence resolves exactly to BASE (relative mode, incl. base == 0).
7.  Manual vs auto ownership (musicalize never overwrites manual work).
8.  Clearing auto bindings leaves manual ones intact.
9.  Shader-switch isolation (no binding leakage across different shaders).
10. Hot-reload preservation of surviving auto bindings.
11. No source-file modification.
12. Integrated LAB MUSICALIZE action (real UI click).
13. Standalone Lab parity.
14. AUTO REACT remains independent of MUSICALIZE.
"""

import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtTest import QTest

from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.visualizers.gpu_canvas import GLVisualizerCanvas

REPO_ROOT = Path(__file__).resolve().parent.parent


def _frame(bass=0.0, mids=0.0, treble=0.0, rms=0.0, peak=0.0, beat=False, strong_beat=False):
    return AudioFrame(
        rms=rms, peak=peak, bass=bass, mids=mids, treble=treble,
        spectrum=tuple([0.0] * 64), waveform=tuple([0.0] * 128),
        beat=beat, strong_beat=strong_beat,
    )


class TestGPUAudio005BoundedAutoMusicalization(unittest.TestCase):
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

    # -- 1: determinism ------------------------------------------------------

    def test_01_deterministic_automatic_mapping(self):
        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        results = []
        for _ in range(3):
            c = GLVisualizerCanvas()
            c.load_shader_file(shader)
            applied = c.musicalize()
            results.append(applied)
            c.cleanupGL()
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertTrue(len(results[0]) > 0)

    # -- 2: relative formula matches documented policy -----------------------

    def test_02_relative_formula_matches_documented_examples(self):
        # base=24.0, audio=0.8, amount=+0.10 -> 25.92
        self.assertAlmostEqual(
            GLVisualizerCanvas._apply_audio_modulation(24.0, 0.8, 0.10, "relative"), 25.92
        )
        # base=0.2, audio=0.8, amount=+0.10 -> 0.216
        self.assertAlmostEqual(
            GLVisualizerCanvas._apply_audio_modulation(0.2, 0.8, 0.10, "relative"), 0.216
        )

    def test_02b_amounts_stay_within_conservative_bounds(self):
        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        self.canvas.load_shader_file(shader)
        applied = self.canvas.musicalize()
        for name, (source, amount) in applied.items():
            self.assertLessEqual(abs(amount), 0.15, f"{name} amount {amount} exceeds conservative bound")

    # -- 3: zero-base fallback ------------------------------------------------

    def test_03_zero_base_fallback_is_not_degenerate(self):
        final = GLVisualizerCanvas._apply_audio_modulation(0.0, 0.8, 0.10, "relative")
        # Pure multiplicative relative modulation of 0.0 would always be 0.0
        # (the whole point of the fallback) — assert the fallback actually
        # produces motion instead.
        self.assertNotEqual(final, 0.0)
        self.assertAlmostEqual(final, 0.0 + (0.8 * 0.10))

    def test_03b_silence_at_zero_base_is_exactly_zero(self):
        final = GLVisualizerCanvas._apply_audio_modulation(0.0, 0.0, 0.10, "relative")
        self.assertEqual(final, 0.0)

    # -- 4: negative base -------------------------------------------------

    def test_04_negative_base_preserves_sign_and_bounded_deviation(self):
        final = GLVisualizerCanvas._apply_audio_modulation(-2.0, 0.8, 0.10, "relative")
        self.assertAlmostEqual(final, -2.16)
        self.assertLess(final, 0.0)

    # -- 5: range clamping --------------------------------------------------

    def test_05_final_value_clamped_to_declared_range(self):
        # Deliberately oversized amount to force an out-of-range result absent clamping.
        final = GLVisualizerCanvas._apply_audio_modulation(
            9.0, 1.0, 5.0, "relative", min_value=0.0, max_value=10.0
        )
        self.assertEqual(final, 10.0)
        final_lo = GLVisualizerCanvas._apply_audio_modulation(
            1.0, 1.0, -5.0, "relative", min_value=0.0, max_value=10.0
        )
        self.assertEqual(final_lo, 0.0)

    def test_05b_absolute_manual_mode_remains_unclamped(self):
        """Manual/absolute bindings keep the pre-existing GPU-AUDIO-003 unclamped behavior."""
        final = GLVisualizerCanvas._apply_audio_modulation(
            9.0, 1.0, 5.0, "absolute", min_value=0.0, max_value=10.0
        )
        self.assertEqual(final, 14.0)

    # -- 6: silence == exact BASE --------------------------------------------

    def test_06_silence_resolves_exactly_to_base_relative_mode(self):
        for base in (24.0, 0.2, 0.0, -1.5):
            final = GLVisualizerCanvas._apply_audio_modulation(base, 0.0, 0.12, "relative", -50.0, 50.0)
            self.assertEqual(final, base)

    # -- 7: manual vs auto ownership ------------------------------------------

    def test_07_musicalize_never_overwrites_manual_binding(self):
        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        self.canvas.load_shader_file(shader)
        self.canvas.set_param_audio_binding("u_zoom", "TREBLE", 0.42)  # manual, absolute (default)

        self.canvas.musicalize()

        src, amt, mode, origin = self.canvas.get_param_audio_binding_full("u_zoom")
        self.assertEqual((src, amt), ("TREBLE", 0.42))
        self.assertEqual(mode, "absolute")
        self.assertEqual(origin, "manual")

    def test_07b_musicalize_generates_relative_auto_bindings(self):
        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        self.canvas.load_shader_file(shader)
        applied = self.canvas.musicalize()
        self.assertTrue(applied)
        for name in applied:
            _src, _amt, mode, origin = self.canvas.get_param_audio_binding_full(name)
            self.assertEqual(mode, "relative")
            self.assertEqual(origin, "auto")
            self.assertTrue(self.canvas.is_param_binding_auto(name))

    def test_07c_manual_edit_of_auto_binding_takes_ownership(self):
        """Editing an auto-generated binding through the normal manual API re-classifies it manual/absolute."""
        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        self.canvas.load_shader_file(shader)
        self.canvas.musicalize()
        self.assertTrue(self.canvas.is_param_binding_auto("u_zoom"))

        # Simulates the LAB's source-select / amount-slider handlers, which
        # always call set_param_audio_binding with positional args only.
        self.canvas.set_param_audio_binding("u_zoom", "PEAK", 0.33)

        self.assertFalse(self.canvas.is_param_binding_auto("u_zoom"))
        src, amt, mode, origin = self.canvas.get_param_audio_binding_full("u_zoom")
        self.assertEqual((src, amt, mode, origin), ("PEAK", 0.33, "absolute", "manual"))

    # -- 8: clear auto --------------------------------------------------------

    def test_08_clear_auto_bindings_preserves_manual(self):
        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        self.canvas.load_shader_file(shader)
        self.canvas.set_param_audio_binding("u_zoom", "TREBLE", 0.42)  # manual
        applied = self.canvas.musicalize()  # auto-fills u_speed, u_glow (u_zoom is manual, skipped)
        self.assertNotIn("u_zoom", applied)
        self.assertIn("u_speed", applied)

        n_cleared = self.canvas.clear_auto_bindings()
        self.assertEqual(n_cleared, len(applied))

        # Manual binding survives.
        self.assertEqual(self.canvas.get_param_audio_binding("u_zoom"), ("TREBLE", 0.42))
        # Auto-generated ones are gone -> back to BASE (no binding).
        for name in applied:
            self.assertEqual(self.canvas.get_param_audio_binding(name), ("NONE", 0.0))

    # -- 9: shader-switch isolation -------------------------------------------

    def test_09_shader_switch_does_not_leak_bindings(self):
        shader_a = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        shader_b = REPO_ROOT / "user_shaders" / "test_const_promotion_demo.frag"

        self.canvas.load_shader_file(shader_a)
        self.canvas.musicalize()
        self.assertTrue(self.canvas.audio_bindings)

        self.canvas.load_shader_file(shader_b)
        self.assertEqual(self.canvas.audio_bindings, {})

    # -- 10: hot reload preservation -------------------------------------------

    def test_10_hot_reload_preserves_surviving_auto_binding(self):
        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        self.canvas.load_shader_file(shader)
        applied = self.canvas.musicalize()
        self.assertTrue(applied)
        before = dict(self.canvas.audio_bindings)

        self.canvas.reload_current_shader()

        after = dict(self.canvas.audio_bindings)
        self.assertEqual(before, after)

    # -- 11: source preservation -------------------------------------------

    def test_11_musicalize_does_not_modify_source_file(self):
        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        before = shader.read_bytes()
        self.canvas.load_shader_file(shader)
        self.canvas.musicalize()
        self.canvas.reload_current_shader()
        after = shader.read_bytes()
        self.assertEqual(before, after)

    # -- 12: Integrated LAB MUSICALIZE action (real UI) -----------------------

    def test_12_integrated_lab_musicalize_button_creates_visible_bindings(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager

        session_mgr = SessionManager()
        win = RetinaMeltWindow(session_manager=session_mgr)
        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        win.gpu_canvas.load_shader_file(shader)
        win._local_shader_active = True
        win.show()
        win._open_lab_panel()
        QApplication.processEvents()

        self.assertTrue(hasattr(win, "btn_lab_musicalize"))
        self.assertTrue(hasattr(win, "btn_lab_clear_auto"))

        QTest.mouseClick(win.btn_lab_musicalize, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)
        QApplication.processEvents()

        self.assertTrue(win.gpu_canvas.audio_bindings)
        # At least one card now shows the [AUTO] provenance badge.
        audio_buttons = [b for b in win.lab_controls_widget.findChildren(QPushButton) if b.text().startswith("AUDIO:")]
        self.assertTrue(any("[AUTO]" in b.text() for b in audio_buttons))

        QTest.mouseClick(win.btn_lab_clear_auto, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)
        QApplication.processEvents()
        self.assertEqual(win.gpu_canvas.audio_bindings, {})

        win.close()

    # -- 13: Standalone Lab parity ---------------------------------------------

    def test_13_standalone_lab_has_musicalize_controls(self):
        import importlib.util
        lab_app_path = REPO_ROOT / "experiments" / "gpu_visualizers" / "lab_app.py"
        spec = importlib.util.spec_from_file_location("lab_app_gpu005", lab_app_path)
        lab_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lab_app)

        win = lab_app.GPUAuthoringLabWindow()
        self.assertTrue(hasattr(win, "btn_musicalize"))
        self.assertTrue(hasattr(win, "btn_clear_auto"))

        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        win.switch_shader_path(shader)
        win.musicalize_shader()
        self.assertTrue(win.canvas.audio_bindings)
        win.clear_auto_musicalize()
        self.assertEqual(win.canvas.audio_bindings, {})
        win.close()

    # -- 14: AUTO REACT independence -------------------------------------------

    def test_14_auto_react_independent_of_musicalize(self):
        shader = REPO_ROOT / "user_shaders" / "test_discovered_params.frag"
        self.canvas.load_shader_file(shader)
        self.canvas.set_auto_react(True)
        self.canvas.musicalize()
        # musicalize() never touches auto_react, and set_auto_react never touches audio_bindings.
        self.assertTrue(self.canvas.auto_react)
        self.assertTrue(self.canvas.audio_bindings)
        self.canvas.clear_auto_bindings()
        self.assertTrue(self.canvas.auto_react)  # unaffected by clearing musicalized bindings

    # -- Additional coverage: promoted-const category (category B) -----------

    def test_15_musicalize_works_on_promoted_const_parameters(self):
        shader = REPO_ROOT / "user_shaders" / "test_const_promotion_demo.frag"
        self.canvas.load_shader_file(shader)
        self.assertIn("SPEED", self.canvas.metadata.parameters)

        applied = self.canvas.musicalize()
        self.assertIn("SPEED", applied)
        self.assertNotIn("STEPS", applied)  # excluded const (int loop bound) never appears at all

    # -- Additional coverage: official reference shader (category A) ---------

    def test_16_musicalize_works_on_audio_reactive_reference(self):
        official = REPO_ROOT / "src" / "toroidamp" / "assets" / "official_shaders" / "audio_reactive_reference.frag"
        self.canvas.load_shader_file(official)
        applied = self.canvas.musicalize()
        self.assertTrue(applied)
        self.assertTrue(set(applied.keys()).issubset(set(self.canvas.metadata.parameters.keys())))


class TestGPUAudio005HumanGateDefectA(unittest.TestCase):
    """
    HUMAN GATE DEFECT A — production-path regression.

    Metal's human validation: MUSICALIZE on audio_reactive_reference.frag
    (PASS, visibly reactive) vs test_const_promotion_demo.frag (FAIL, "no
    observable parameter/audio modulation"). Metal's hypothesis: promoted
    const parameters are not reaching the GPU-AUDIO-005 eligible-parameter/
    binding path correctly.

    This class reproduces Metal's exact steps through the REAL production
    path (real RetinaMeltWindow, real MUSICALIZE/CLEAR AUTO button clicks,
    real render_frame() calls) — not a parser/model-only shortcut — and
    asserts every state/UI/modulation-math layer this environment can reach
    without a live OpenGL context (see docstrings below for the one boundary
    that genuinely requires a live context and is therefore a human-gate
    item, not an automated one).

    Result of this audit (see docs/design/12_gpu_audio_005.md, "Human Gate
    Defect A" addendum for the full trace): every layer — detection,
    promotion, metadata, current_params, musicalize() eligibility, the
    4-tuple binding (mode=="relative", origin=="auto"), and
    _apply_audio_modulation() evaluated against the promoted parameter's
    REAL generated range — was found to produce a materially different
    final value under realistic non-zero audio, structurally identical to
    the already-passing audio_reactive_reference.frag path. No divergence
    was found in the binding/modulation pipeline itself. The concrete,
    scoped fix applied was to user_shaders/test_const_promotion_demo.frag's
    own GLSL body (GLOW previously only fed a small near-center hotspot,
    making its ~5% MUSICALIZE deviation hard to perceive; it now also
    scales overall frame exposure) — MUSICALIZE's algorithm/percentages and
    the GPU-AUDIO-004/005 pipeline code were NOT changed.
    """

    @classmethod
    def setUpClass(cls):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        QSurfaceFormat.setDefaultFormat(fmt)
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _strong_frame(self):
        return _frame(bass=0.9, mids=0.85, treble=0.9, rms=0.9, peak=0.95, beat=True, strong_beat=True)

    def _run_production_path(self, shader_path: Path):
        """Steps 1-14 of Metal's exact failed human path, through the real production window."""
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager

        win = RetinaMeltWindow(session_manager=SessionManager())

        # 1-2. Real production shader-loading path (mirrors _load_local_shader_dialog
        # minus the file picker), through the real Integrated RETINA LAB.
        ok = win.gpu_canvas.load_shader_file(shader_path)
        self.assertTrue(ok, f"production load_shader_file failed for {shader_path.name}: {win.gpu_canvas.last_error_log}")
        win._local_shader_active = True
        win._local_shader_path = shader_path
        win.btn_lab_auto_react.setChecked(False)
        win.gpu_canvas.set_auto_react(False)
        win.show()
        win._open_lab_panel()
        QApplication.processEvents()

        # 3-4. Confirm promoted/discovered float cards exist and record BASE.
        base_values = dict(win.gpu_canvas.current_params)
        self.assertTrue(base_values, f"{shader_path.name}: no eligible parameters loaded")

        # 5. Real MUSICALIZE click (not a direct canvas.musicalize() call).
        QTest.mouseClick(win.btn_lab_musicalize, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)
        QApplication.processEvents()

        # 6. Cards visibly updated to AUDIO: <SOURCE> [AUTO]. findChildren can
        # also return stale pre-rebuild widgets pending Qt's deferred
        # deleteLater() in this offscreen/no-exec()-loop test harness (a test
        # artifact, not a production concern under a real running event
        # loop) — so this asserts "at least one fresh [AUTO] card exists",
        # not "every AUDIO button is [AUTO]".
        audio_buttons = [b for b in win.lab_controls_widget.findChildren(QPushButton) if b.text().startswith("AUDIO:")]
        self.assertTrue(any("[AUTO]" in b.text() for b in audio_buttons), "no [AUTO]-tagged card found after MUSICALIZE")

        # 7. gpu_canvas.audio_bindings contains the promoted/discovered names.
        applied_names = [n for n in base_values if win.gpu_canvas.is_param_binding_auto(n)]
        self.assertTrue(applied_names, "musicalize() produced no auto bindings for any loaded parameter")
        for n in applied_names:
            src, amt, mode, origin = win.gpu_canvas.get_param_audio_binding_full(n)
            self.assertEqual(mode, "relative")
            self.assertEqual(origin, "auto")
            self.assertNotEqual(src, "NONE")

        # 8-10. Inject a deliberately strong non-zero AudioFrame and evaluate
        # through the exact same formula/range paintGL calls
        # (GLVisualizerCanvas._apply_audio_modulation, refactored specifically
        # so it is the REAL production formula, not a parallel reimplementation).
        strong = self._strong_frame()
        win.render_frame(strong, 0.016)
        QApplication.processEvents()

        param_meta_map = win.gpu_canvas.metadata.parameters
        materially_different = []
        for n in applied_names:
            base = base_values[n]
            src, amt, mode, _origin = win.gpu_canvas.get_param_audio_binding_full(n)
            audio_val = GLVisualizerCanvas._read_audio_source(src, strong)
            meta_p = param_meta_map.get(n)
            final = GLVisualizerCanvas._apply_audio_modulation(base, audio_val, amt, mode, meta_p.min_value, meta_p.max_value)
            if abs(final - base) > 1e-9:
                materially_different.append((n, base, final))
        self.assertTrue(
            materially_different,
            f"no promoted/discovered parameter's evaluated final value differed from BASE under a strong AudioFrame: {applied_names}"
        )

        # 11-12. Silence resolves exactly to BASE.
        silence = _frame()
        for n in applied_names:
            base = base_values[n]
            src, amt, mode, _origin = win.gpu_canvas.get_param_audio_binding_full(n)
            audio_val = GLVisualizerCanvas._read_audio_source(src, silence)
            meta_p = param_meta_map.get(n)
            final = GLVisualizerCanvas._apply_audio_modulation(base, audio_val, amt, mode, meta_p.min_value, meta_p.max_value)
            self.assertEqual(final, base, f"{n}: silence must resolve exactly to BASE")

        # 13-14. Real CLEAR AUTO click removes the auto bindings.
        QTest.mouseClick(win.btn_lab_clear_auto, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)
        QApplication.processEvents()
        self.assertEqual(win.gpu_canvas.audio_bindings, {})

        win.close()
        return materially_different

    def test_defect_a_production_path_promoted_const_shader(self):
        """
        Metal's exact failed path: test_const_promotion_demo.frag. If this
        fails, it reproduces the reported defect at the automated-test level
        (a real code-path divergence). If it passes (as it does after the
        Defect A audit/fix), the model/state/modulation-math layers are
        proven correct end-to-end, and any remaining "not observable" gap is
        a live-GL visual question for the human gate, not this test.
        """
        shader = REPO_ROOT / "user_shaders" / "test_const_promotion_demo.frag"
        materially_different = self._run_production_path(shader)
        names = {n for n, _b, _f in materially_different}
        self.assertTrue(
            names & {"SPEED", "ZOOM", "GLOW"},
            f"expected at least one of SPEED/ZOOM/GLOW to differ from BASE, got: {materially_different}",
        )

    def test_defect_a_reference_shader_regression(self):
        """audio_reactive_reference.frag (Metal's PASS case) must remain unchanged and keep passing the same production path."""
        shader = REPO_ROOT / "src" / "toroidamp" / "assets" / "official_shaders" / "audio_reactive_reference.frag"
        materially_different = self._run_production_path(shader)
        self.assertTrue(materially_different)


if __name__ == "__main__":
    unittest.main()
