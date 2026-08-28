"""
tests/test_gpu_audio_006b.py — GPU-AUDIO-006B: Runtime Literal Parameterization

Validates:
1.  `float fov = 2.5;` becomes parameterized.
2.  Local variable name/scope remains intact (only the literal token changes).
3.  Default generated uniform value equals the original literal exactly.
4.  `iTime * 0.8` becomes parameterized.
5.  `0.8 * iTime` (reversed operand order) becomes parameterized.
6.  Overlap: `float t = iTime * 0.8;` produces exactly ONE parameter (TIME_SCALE).
7.  Deterministic generated identity across repeated runs.
8.  Multiple candidates in one shader do not collide.
9.  `//` comments ignored.
10. `/* block comments */` ignored (incl. dead-code duplicate, Skinketest-shaped).
11. Production `// [param:float]` annotation discovery remains functional.
12. Loop bounds untouched.
13. Array dimensions untouched.
14. `int` declarations untouched.
15. vec3 literal constructors untouched.
16. Plain numeric `#define` untouched.
17. Source file byte-for-byte unchanged after load/reload.
18. Adapted source is inspectable in memory (`ShaderMetadata.adapted_source`).
19. Integrated LAB parameter cards are generated with an [AUTO PARAM] badge.
20. Manual BASE slider change affects the generated uniform's current value.
21. Manual AUDIO binding works on a generated parameter.
22. MUSICALIZE creates a bounded auto binding on a generated parameter.
23. CLEAR AUTO removes only the auto binding.
24. Silence resolves exactly to BASE.
25. Same-file hot reload preserves surviving generated parameter state.
26. Shader switch clears previous generated audio bindings (isolation).
27. Real 5-shader USER corpus is parameterized without modifying any file.
28. Macro-wrapped `#define T (iTime*6.)` is supported (regex fix regression).
29. Sentinel/extreme-magnitude literals (e.g. `-9e9`) are excluded.
"""

import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.visualizers.gpu_compiler import (
    classify_and_wrap_source,
    find_runtime_literal_candidates,
    parse_shader_parameters,
)
from toroidamp.visualizers.gpu_canvas import GLVisualizerCanvas

REPO_ROOT = Path(__file__).resolve().parent.parent


def _frame(bass=0.0, mids=0.0, treble=0.0, rms=0.0, peak=0.0, beat=False, strong_beat=False):
    return AudioFrame(
        rms=rms, peak=peak, bass=bass, mids=mids, treble=treble,
        spectrum=tuple([0.0] * 64), waveform=tuple([0.0] * 128),
        beat=beat, strong_beat=strong_beat,
    )


class TestGPUAudio006BRuntimeParameterization(unittest.TestCase):
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

    # -- 1-3: local float literal ------------------------------------------

    def test_01_simple_local_float_is_parameterized(self):
        src = "void mainImage(out vec4 o, vec2 u) { float fov = 2.5; o = vec4(fov); }"
        transformed, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 1)
        p = next(iter(generated.values()))
        self.assertEqual(p.auto_param_kind, "local_float")
        self.assertEqual(p.display_name, "fov")

    def test_02_local_variable_name_and_scope_intact(self):
        src = "void mainImage(out vec4 o, vec2 u) { float fov = 2.5; o = vec4(fov, fov, fov, 1.0); }"
        transformed, generated = find_runtime_literal_candidates(src, set())
        uname = next(iter(generated.keys()))
        # "fov" the local variable is unchanged everywhere except its own
        # initializer's literal token, which now reads the generated uniform.
        self.assertIn(f"float fov = {uname};", transformed)
        self.assertIn("o = vec4(fov, fov, fov, 1.0);", transformed)

    def test_03_default_equals_original_literal(self):
        src = "void mainImage(out vec4 o, vec2 u) { float glow = .0015; o = vec4(glow); }"
        _t, generated = find_runtime_literal_candidates(src, set())
        p = next(iter(generated.values()))
        self.assertEqual(p.default_value, 0.0015)
        self.assertEqual(p.current_value, 0.0015)
        self.assertLessEqual(p.min_value, 0.0015)
        self.assertLessEqual(0.0015, p.max_value)

    # -- 4-6: time scale + overlap precedence --------------------------------

    def test_04_itime_times_literal(self):
        src = "void mainImage(out vec4 o, vec2 u) { o = vec4(iTime * 0.8); }"
        _t, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 1)
        p = next(iter(generated.values()))
        self.assertEqual(p.auto_param_kind, "time_scale")
        self.assertEqual(p.default_value, 0.8)

    def test_05_literal_times_itime_reversed(self):
        src = "void mainImage(out vec4 o, vec2 u) { o = vec4(.2*iTime); }"
        _t, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 1)
        p = next(iter(generated.values()))
        self.assertEqual(p.auto_param_kind, "time_scale")
        self.assertAlmostEqual(p.default_value, 0.2)

    def test_06_overlap_produces_exactly_one_parameter(self):
        src = "void mainImage(out vec4 o, vec2 u) { float t = iTime * 0.8; o = vec4(t); }"
        transformed, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 1)
        p = next(iter(generated.values()))
        self.assertEqual(p.auto_param_kind, "time_scale")
        # "t" the local variable keeps its name/scope; only iTime's multiplier moved.
        self.assertIn("float t = iTime *", transformed)

    # -- 7-8: identity determinism / collision-freedom -----------------------

    def test_07_deterministic_identity(self):
        src = "void mainImage(out vec4 o, vec2 u) { float fov = 2.5; o = vec4(iTime*0.8, fov, 0.0, 1.0); }"
        _t1, g1 = find_runtime_literal_candidates(src, set())
        _t2, g2 = find_runtime_literal_candidates(src, set())
        self.assertEqual(set(g1.keys()), set(g2.keys()))

    def test_08_multiple_candidates_do_not_collide(self):
        src = (
            "void mainImage(out vec4 o, vec2 u) {\n"
            "    float t1 = iTime * 0.8;\n"
            "    float t2 = iTime * 0.4;\n"
            "    float fov = 2.5;\n"
            "    float glow = 0.015;\n"
            "    o = vec4(t1, t2, fov, glow);\n"
            "}\n"
        )
        _t, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 4)
        self.assertEqual(len(set(generated.keys())), 4)  # all names unique

    # -- 9-11: comments / annotations ----------------------------------------

    def test_09_line_comments_ignored(self):
        src = "// float dead = 9.0;\nvoid mainImage(out vec4 o, vec2 u) { float live = 1.0; o = vec4(live); }"
        _t, generated = find_runtime_literal_candidates(src, set())
        names = {p.display_name for p in generated.values()}
        self.assertIn("live", names)
        self.assertNotIn("dead", names)

    def test_10_block_comment_dead_code_not_transformed(self):
        """Mirrors the real Skinketest.frag shape: an old full implementation trailing inside /* */."""
        src = (
            "void mainImage(out vec4 o, vec2 u) {\n"
            "    float minDist = 100.0;\n"
            "    o = vec4(minDist);\n"
            "}\n"
            "/*\n"
            "void mainImage(out vec4 o, vec2 u) {\n"
            "    float minDist = 100.0;\n"
            "    o = vec4(minDist);\n"
            "}\n"
            "*/\n"
        )
        transformed, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 1)  # not 2 — dead code must not double-count
        # The commented-out block must remain byte-identical (untouched).
        self.assertIn("/*\nvoid mainImage(out vec4 o, vec2 u) {\n    float minDist = 100.0;", transformed)

    def test_11_annotation_discovery_still_works_alongside_006b(self):
        src = (
            "// [param:float] u_zoom: Zoom = 1.0 (0.3 .. 3.0)\n"
            "void main() { float fov = 2.5; float x = u_zoom * fov; fragColor = vec4(x); }\n"
        )
        _full, meta = classify_and_wrap_source(src, "t")
        self.assertIn("u_zoom", meta.parameters)
        self.assertFalse(meta.parameters["u_zoom"].auto_param_kind)
        fov_params = [p for p in meta.parameters.values() if p.display_name == "fov"]
        self.assertEqual(len(fov_params), 1)
        self.assertEqual(fov_params[0].auto_param_kind, "local_float")

    # -- 12-16: structural exclusions ----------------------------------------

    def test_12_loop_bound_untouched(self):
        src = "void mainImage(out vec4 o, vec2 u) { float t=0.; for (int i = 0; i < 8; i++) { t += 1.0; } o = vec4(t); }"
        _t, generated = find_runtime_literal_candidates(src, set())
        # "t" itself IS eligible (float t = 0.; outside the for-header) but the
        # loop bound "8" and increment must never generate their own params.
        self.assertTrue(all(p.default_value != 8.0 for p in generated.values()))

    def test_13_array_dimension_untouched(self):
        src = "void mainImage(out vec4 o, vec2 u) { vec3 v[5]; v[0] = vec3(1.0); o = vec4(v[0], 1.0); }"
        _t, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 0)

    def test_14_int_declaration_untouched(self):
        src = "void mainImage(out vec4 o, vec2 u) { int count = 5; o = vec4(float(count)); }"
        _t, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 0)

    def test_15_vec3_literal_untouched(self):
        src = "void mainImage(out vec4 o, vec2 u) { vec3 c = vec3(1.0, 0.4, 0.1); o = vec4(c, 1.0); }"
        _t, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 0)

    def test_16_plain_numeric_define_untouched(self):
        src = "#define GLOW 0.015\nvoid mainImage(out vec4 o, vec2 u) { o = vec4(GLOW); }"
        transformed, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 0)
        self.assertIn("#define GLOW 0.015", transformed)

    # -- 17-18: source immutability / adapted-source inspectability ----------

    def test_17_source_file_byte_for_byte_unchanged(self):
        p = REPO_ROOT / "user_shaders" / "shadertoy" / "happy_glow_cruise" / "happy_glow_cruise.frag"
        before = p.read_bytes()
        self.canvas.load_shader_file(p)
        self.canvas.reload_current_shader()
        after = p.read_bytes()
        self.assertEqual(before, after)

    def test_18_adapted_source_inspectable_and_differs_from_raw(self):
        raw = "void mainImage(out vec4 o, vec2 u) { float fov = 2.5; o = vec4(fov); }"
        _full, meta = classify_and_wrap_source(raw, "t")
        self.assertIsNotNone(meta.adapted_source)
        self.assertNotEqual(meta.adapted_source, raw)
        self.assertNotIn("2.5", meta.adapted_source)
        self.assertIn("taAuto_fov_", meta.adapted_source)

    # -- 19: LAB card generation with [AUTO PARAM] badge ----------------------

    def test_19_lab_cards_generated_with_auto_param_badge(self):
        from toroidamp.ui.fullscreen import RetinaMeltWindow
        from toroidamp.session import SessionManager

        win = RetinaMeltWindow(session_manager=SessionManager())
        shader = REPO_ROOT / "user_shaders" / "shadertoy" / "apollo_spiral" / "apollo_spiral.frag"
        ok = win.gpu_canvas.load_shader_file(shader)
        self.assertTrue(ok)
        win._local_shader_active = True
        win.show()
        win._open_lab_panel()
        QApplication.processEvents()

        labels = [l.text() for l in win.lab_controls_widget.findChildren(type(win.lbl_lab_identity)) if "[AUTO PARAM]" in l.text()]
        self.assertTrue(labels, "expected at least one [AUTO PARAM] card label")
        win.close()

    # -- 20-21: manual BASE / AUDIO controls ----------------------------------

    def test_20_manual_base_affects_generated_uniform(self):
        src = "void mainImage(out vec4 o, vec2 u) { float fov = 2.5; o = vec4(fov); }"
        self.canvas.metadata = None
        ok = self.canvas.load_shader_file(self._write_tmp(src))
        self.assertTrue(ok)
        name = next(iter(self.canvas.metadata.parameters.keys()))
        self.canvas.set_param_value(name, 4.2)
        self.assertEqual(self.canvas.current_params[name], 4.2)

    def test_21_manual_audio_binding_works(self):
        src = "void mainImage(out vec4 o, vec2 u) { float fov = 2.5; o = vec4(fov); }"
        self.canvas.load_shader_file(self._write_tmp(src))
        name = next(iter(self.canvas.metadata.parameters.keys()))
        self.canvas.set_param_audio_binding(name, "BASS", 0.5)
        src_name, amt = self.canvas.get_param_audio_binding(name)
        self.assertEqual((src_name, amt), ("BASS", 0.5))

    # -- 22-24: MUSICALIZE integration ----------------------------------------

    def test_22_musicalize_creates_bounded_auto_binding(self):
        src = "void mainImage(out vec4 o, vec2 u) { float fov = 2.5; float glow = 0.015; o = vec4(fov, glow, 0.0, 1.0); }"
        self.canvas.load_shader_file(self._write_tmp(src))
        applied = self.canvas.musicalize()
        self.assertTrue(applied)
        for name, (source, amount) in applied.items():
            _s, _a, mode, origin = self.canvas.get_param_audio_binding_full(name)
            self.assertEqual(mode, "relative")
            self.assertEqual(origin, "auto")
            self.assertLessEqual(abs(amount), 0.15)

    def test_23_clear_auto_removes_only_auto(self):
        src = "void mainImage(out vec4 o, vec2 u) { float fov = 2.5; o = vec4(fov); }"
        self.canvas.load_shader_file(self._write_tmp(src))
        name = next(iter(self.canvas.metadata.parameters.keys()))
        self.canvas.musicalize()
        self.assertTrue(self.canvas.is_param_binding_auto(name))
        n = self.canvas.clear_auto_bindings()
        self.assertEqual(n, 1)
        self.assertEqual(self.canvas.get_param_audio_binding(name), ("NONE", 0.0))

    def test_24_silence_resolves_exactly_to_base(self):
        src = "void mainImage(out vec4 o, vec2 u) { float fov = 2.5; o = vec4(fov); }"
        self.canvas.load_shader_file(self._write_tmp(src))
        name = next(iter(self.canvas.metadata.parameters.keys()))
        self.canvas.musicalize()
        base = self.canvas.current_params[name]
        src_name, amt, mode, _origin = self.canvas.get_param_audio_binding_full(name)
        meta_p = self.canvas.metadata.parameters[name]
        final = GLVisualizerCanvas._apply_audio_modulation(base, 0.0, amt, mode, meta_p.min_value, meta_p.max_value)
        self.assertEqual(final, base)

    # -- 25: hot reload preservation -------------------------------------------

    def test_25_hot_reload_preserves_surviving_state(self):
        p = self._write_tmp("void mainImage(out vec4 o, vec2 u) { float fov = 2.5; o = vec4(fov); }")
        self.canvas.load_shader_file(p)
        name = next(iter(self.canvas.metadata.parameters.keys()))
        self.canvas.set_param_value(name, 3.3)
        self.canvas.set_param_audio_binding(name, "MIDS", 0.25)

        self.canvas.reload_current_shader()

        self.assertAlmostEqual(self.canvas.current_params[name], 3.3)
        self.assertEqual(self.canvas.get_param_audio_binding(name), ("MIDS", 0.25))

    # -- 26: shader-switch isolation ---------------------------------------------

    def test_26_shader_switch_clears_previous_bindings(self):
        p1 = self._write_tmp("void mainImage(out vec4 o, vec2 u) { float fov = 2.5; o = vec4(fov); }", "a.frag")
        p2 = self._write_tmp("void mainImage(out vec4 o, vec2 u) { float glow = 0.5; o = vec4(glow); }", "b.frag")
        self.canvas.load_shader_file(p1)
        self.canvas.musicalize()
        self.assertTrue(self.canvas.audio_bindings)

        self.canvas.load_shader_file(p2)
        self.assertEqual(self.canvas.audio_bindings, {})

    # -- 27: real corpus, no shader-specific rules -----------------------------

    def test_27_real_user_corpus_parameterized_without_modification(self):
        corpus_dir = REPO_ROOT / "user_shaders" / "shadertoy"
        frag_files = sorted(corpus_dir.rglob("*.frag"))
        self.assertGreaterEqual(len(frag_files), 5)

        shaders_with_params = 0
        for f in frag_files:
            before = f.read_bytes()
            raw = f.read_text(encoding="utf-8")
            _full, meta = classify_and_wrap_source(raw, f.stem)
            after = f.read_bytes()
            self.assertEqual(before, after, f"{f} was modified")
            if any(p.auto_param_kind for p in meta.parameters.values()):
                shaders_with_params += 1

        # Evidence-driven target from GPU-AUDIO-006A: majority (>=4/5) coverage.
        self.assertGreaterEqual(shaders_with_params, 4, "expected at least 4/5 real user shaders to gain generated parameters")

    # -- 28: macro-wrapped time multiplier ---------------------------------------

    def test_28_macro_wrapped_time_multiplier_supported(self):
        src = "#define T (iTime*6.)\nvoid mainImage(out vec4 o, vec2 u) { o = vec4(T); }"
        transformed, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 1)
        p = next(iter(generated.values()))
        self.assertEqual(p.auto_param_kind, "time_scale")
        self.assertEqual(p.default_value, 6.0)
        # Regression: must not leave a dangling "." after the substitution.
        self.assertNotIn(f"{p.name}.", transformed)
        self.assertIn(f"(iTime*{p.name})", transformed)

    # -- 29: sentinel/extreme-magnitude exclusion --------------------------------

    def test_29_extreme_magnitude_sentinel_excluded(self):
        src = "void mainImage(out vec4 o, vec2 u) { float d = -9e9; o = vec4(d); }"
        _t, generated = find_runtime_literal_candidates(src, set())
        self.assertEqual(len(generated), 0)

    # -- helpers ------------------------------------------------------------------

    def _write_tmp(self, content: str, name: str = "t.frag") -> Path:
        import tempfile
        if not hasattr(self, "_tmpdir"):
            self._tmpdir_ctx = tempfile.TemporaryDirectory()
            self._tmpdir = Path(self._tmpdir_ctx.name)
            self.addCleanup(self._tmpdir_ctx.cleanup)
        p = self._tmpdir / name
        p.write_text(content, encoding="utf-8")
        return p


if __name__ == "__main__":
    unittest.main()
