"""
tests/test_gpu_audio_006a.py — GPU-AUDIO-006A: Real-World Shader Parameter
Discovery Audit (read-only auditor, tools/shader_audit.py)

Validates:
1.  // line comments are ignored.
2.  /* block */ comments (incl. multi-line dead code) are ignored.
3.  Direct `iTime * LITERAL` is detected as a time multiplier.
4.  Direct `LITERAL * iTime` (reversed order) is detected.
5.  Macro-wrapped `#define NAME (iTime*LITERAL)` is detected separately.
6.  `float NAME = LITERAL;` local declarations are detected.
7.  Plain numeric `#define NAME LITERAL` is detected.
8.  Literal vecN(...) constructors are detected and heuristically classified.
9.  Loop bounds are classified STRUCTURAL_UNSAFE, never as candidates.
10. Array dimensions/indices are classified STRUCTURAL_UNSAFE.
11. The auditor never writes to the scanned file (source preservation).
12. Output is deterministic across repeated runs.
13. Runs without a QApplication / OpenGL context.
14. Digits embedded in identifiers (vec3, mat4, ...) are never miscounted
    as numeric literals (regression for a bug found during corpus audit).
15. Category A (explicit/promotable) reuses the REAL production parser and
    can still see a `// [param:...]` annotation despite comment-adjacent
    categories otherwise stripping comments (regression for a bug where
    reusing the comment-stripped text broke annotation detection entirely).
16. Corpus auto-classification (USER/OFFICIAL/TEST_FIXTURE/EXPERIMENTAL).
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import shader_audit as sa  # noqa: E402


def _write_frag(tmpdir: str, name: str, content: str) -> Path:
    p = Path(tmpdir) / name
    p.write_text(content, encoding="utf-8")
    return p


class TestGPUAudio006AShaderDiscoveryAudit(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    # -- 1-2: comment handling ------------------------------------------------

    def test_01_line_comments_ignored(self):
        src = "// float ghost = 9.0;\nfloat real = 1.0;\n"
        clean = sa.strip_comments(src)
        self.assertNotIn("ghost", clean)
        self.assertIn("real", clean)

    def test_02_block_comments_ignored_including_dead_code(self):
        src = (
            "float live = 1.0;\n"
            "/*\n"
            "void mainImage(out vec4 fragColor, in vec2 fragCoord) {\n"
            "    float dead = 9.0;\n"
            "    fragColor = vec4(dead);\n"
            "}\n"
            "*/\n"
            "float other = 2.0;\n"
        )
        clean = sa.strip_comments(src)
        self.assertNotIn("dead", clean)
        self.assertIn("live", clean)
        self.assertIn("other", clean)

    def test_02b_block_comment_does_not_shift_line_numbers(self):
        src = "float a = 1.0;\n/* block\ncomment\nspanning\nlines */\nfloat b = 2.0;\n"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        by_name = {c.name: c.line for c in result.candidates if c.category == "local_float_literal"}
        self.assertEqual(by_name.get("a"), 1)
        self.assertEqual(by_name.get("b"), 6)  # unaffected by the 4-line block comment above it

    def test_02c_realworld_dead_code_does_not_double_count(self):
        """Mirrors the real Skinketest.frag pattern: a full old implementation inside a trailing block comment."""
        src = (
            "void mainImage(out vec4 fragColor, in vec2 fragCoord) {\n"
            "    float minDist = 100.0;\n"
            "    float glowAcc = 0.0;\n"
            "    fragColor = vec4(minDist, glowAcc, 0.0, 1.0);\n"
            "}\n"
            "/*\n"
            "void mainImage(out vec4 fragColor, in vec2 fragCoord) {\n"
            "    float minDist = 100.0;\n"
            "    float glowAcc = 0.0;\n"
            "    fragColor = vec4(minDist, glowAcc, 0.0, 1.0);\n"
            "}\n"
            "*/\n"
        )
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        local_floats = result.by_category().get("local_float_literal", [])
        self.assertEqual(len(local_floats), 2, "dead code inside /* */ must not double the live count")

    # -- 3-5: time multipliers -------------------------------------------------

    def test_03_direct_itime_multiplier(self):
        src = "void mainImage(out vec4 o, vec2 u) { float t = iTime * 0.8; o = vec4(t); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        hits = result.by_category().get("time_multiplier", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].classification, sa.CLASS_HIGH_VALUE)

    def test_04_reversed_literal_times_itime(self):
        src = "void mainImage(out vec4 o, vec2 u) { float t = .2*iTime; o = vec4(t); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        hits = result.by_category().get("time_multiplier", [])
        self.assertEqual(len(hits), 1)

    def test_05_macro_wrapped_time_multiplier(self):
        src = "#define T (iTime*6.)\nvoid mainImage(out vec4 o, vec2 u) { o = vec4(T); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        hits = result.by_category().get("define_time_multiplier", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].name, "T")
        # Must NOT also land in the plain numeric #define bucket.
        self.assertEqual(result.by_category().get("define_numeric", []), [])

    # -- 6-7: local float literal / numeric #define ----------------------------

    def test_06_local_float_literal_detected(self):
        src = "void mainImage(out vec4 o, vec2 u) { float speed = 0.8; o = vec4(speed); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        hits = result.by_category().get("local_float_literal", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].name, "speed")
        self.assertEqual(hits[0].classification, sa.CLASS_HIGH_VALUE)

    def test_07_plain_numeric_define(self):
        src = "#define GLOW 0.015\nvoid mainImage(out vec4 o, vec2 u) { o = vec4(GLOW); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        hits = result.by_category().get("define_numeric", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].classification, sa.CLASS_POSSIBLE)

    # -- 8: vec literal heuristic classification --------------------------------

    def test_08_vec3_literal_probable_color(self):
        src = "void mainImage(out vec4 o, vec2 u) { vec3 c = vec3(1.0, 0.4, 0.1); o = vec4(c, 1.0); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        hits = result.by_category().get("vec_literal", [])
        self.assertTrue(any("color" in c.note for c in hits))

    def test_08b_vec4_literal_non_color_range_is_unknown_not_promotable(self):
        src = "void mainImage(out vec4 o, vec2 u) { mat2 r = mat2(cos(u.x+vec4(0,33,11,0))); o = vec4(0); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        hits = result.by_category().get("vec_literal", [])
        self.assertTrue(hits)
        self.assertTrue(all(c.classification != sa.CLASS_HIGH_VALUE for c in hits))
        self.assertTrue(any("color" not in c.note for c in hits))

    # -- 9-10: structural classification ----------------------------------------

    def test_09_loop_bound_is_structural_never_a_candidate(self):
        src = "void mainImage(out vec4 o, vec2 u) { float t=0.; for (int i = 0; i < 8; i++) { t += 1.0; } o = vec4(t); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        hits = result.by_category().get("structural_int_loop_bound", [])
        self.assertTrue(any(c.value_text == "8" for c in hits))
        for c in hits:
            self.assertEqual(c.classification, sa.CLASS_STRUCTURAL)

    def test_10_array_dimension_is_structural(self):
        src = "void mainImage(out vec4 o, vec2 u) { vec3 v[5]; int edges[16] = int[16](0,1,1,2,2,3,3,0,0,4,1,4,2,4,3,4); o = vec4(0); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        hits = result.by_category().get("structural_int_array", [])
        self.assertTrue(any(c.value_text == "5" for c in hits))
        self.assertTrue(any(c.value_text == "16" for c in hits))

    # -- 11-13: safety / determinism / no Qt dependency -------------------------

    def test_11_auditor_never_writes_to_scanned_file(self):
        src = "float speed = 0.8;\n#define GLOW 0.015\n"
        p = _write_frag(self.tmpdir, "t.frag", src)
        before = p.read_bytes()
        sa.audit_shader(p)
        after = p.read_bytes()
        self.assertEqual(before, after)

    def test_12_deterministic_output(self):
        src = "float speed = 0.8;\nvoid mainImage(out vec4 o, vec2 u) { float t = iTime*0.2; o = vec4(speed, t, 0.0, 1.0); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        r1 = sa.audit_shader(p)
        r2 = sa.audit_shader(p)
        self.assertEqual(sa.format_shader_report(r1), sa.format_shader_report(r2))

    def test_13_no_qapplication_or_opengl_required(self):
        """
        The auditor module itself never imports Qt/OpenGL — checked
        statically against `shader_audit`'s own top-level names, not via
        process-wide sys.modules (which isn't reliable when this file runs
        alongside other test modules in the same pytest process that DO
        import PySide6 for unrelated reasons).
        """
        src = Path(sa.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import PySide6", src)
        self.assertNotIn("from PySide6", src)

    # -- 14: identifier-embedded-digit regression -------------------------------

    def test_14_digits_embedded_in_identifiers_are_not_literals(self):
        src = (
            "float orb(vec3 p) { return length(p); }\n"
            "void mainImage(out vec4 o, vec2 u) {\n"
            "    mat2 r = mat2(cos(u.x));\n"
            "    o = vec4(orb(vec3(u, 0.0)), 0.0, 0.0, 1.0);\n"
            "}\n"
        )
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        # Neither "vec3"'s 3, "vec4"'s 4, nor "mat2"'s 2 should ever surface
        # as a standalone literal anywhere in the candidate list.
        bogus = [c for c in result.candidates if c.value_text in ("3", "4", "2") and c.name is None]
        self.assertEqual(bogus, [], f"identifier-embedded digits leaked as literals: {bogus}")

    # -- 15: category A must see annotations despite comment-adjacent stripping --

    def test_15_annotated_param_detected_through_comment_syntax(self):
        src = (
            "// [param:float] u_zoom: Zoom = 1.0 (0.3 .. 3.0)\n"
            "void main() { float x = u_zoom; fragColor = vec4(x); }\n"
        )
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        self.assertTrue(result.has_current_eligible_parameter())
        hits = result.by_category().get("uniform_float_annotated", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].name, "u_zoom")

    def test_15b_safe_promotable_const_detected(self):
        src = "const float SPEED = 0.6;\nvoid mainImage(out vec4 o, vec2 u) { o = vec4(SPEED); }"
        p = _write_frag(self.tmpdir, "t.frag", src)
        result = sa.audit_shader(p, corpus_tag="TEST_FIXTURE")
        hits = result.by_category().get("const_float_safe_promotable", [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].name, "SPEED")
        self.assertEqual(hits[0].classification, sa.CLASS_CURRENT)

    # -- 16: corpus classification -----------------------------------------------

    def test_16_corpus_classification(self):
        self.assertEqual(sa.classify_corpus_tag(Path("user_shaders/shadertoy/foo/foo.frag")), "USER")
        self.assertEqual(sa.classify_corpus_tag(Path("user_shaders/test_discovered_params.frag")), "TEST_FIXTURE")
        self.assertEqual(sa.classify_corpus_tag(Path("src/toroidamp/assets/official_shaders/cyber_bloom.frag")), "OFFICIAL")
        self.assertEqual(sa.classify_corpus_tag(Path("experiments/gpu_visualizers/shaders/shader_a_plasma.frag")), "EXPERIMENTAL")

    # -- Real corpus smoke test (still read-only, no promotion side effects) ----

    def test_17_real_user_shader_corpus_smoke(self):
        corpus_dir = REPO_ROOT / "user_shaders" / "shadertoy"
        files = sa.iter_shader_files(corpus_dir)
        self.assertGreaterEqual(len(files), 5, "expected at least the 5 known real user shaders")
        for f in files:
            before = f.read_bytes()
            result = sa.audit_shader(f)
            after = f.read_bytes()
            self.assertEqual(before, after, f"{f} was modified by the auditor")
            self.assertEqual(result.corpus_tag, "USER")
            # None of the real corpus currently benefits from discovery/promotion.
            self.assertFalse(result.has_current_eligible_parameter())


if __name__ == "__main__":
    unittest.main()
