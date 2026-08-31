"""
tests/test_release_blockers_001.py — RELEASE-BLOCKERS-001
Ubuntu TTS, User GLSL & Wayland Unified Chassis

Focused regression tests for Blocker 3 (GLSL Lab user shaders rendering
black on Ubuntu/Mesa/Intel HD 5500):
  1-2. Every sample user shader in this repo's user_shaders/shadertoy/
       directory compiles, links, AND renders non-black pixels through
       the real production pipeline (load_shader_file() /
       classify_and_wrap_source() / paintGL()) on a real (not offscreen)
       OpenGL context -- a regression guard confirming this repo's own
       sample content stays healthy through this pipeline.
  3-4. The Lab's new black-render diagnostic (_diagnose_black_render)
       correctly flags a shader that compiles/links but paints all-black,
       and does NOT false-positive on a shader that renders real content
       -- distinguishing a genuinely silent runtime failure from normal
       operation without guessing at a fix for an unreproducible
       driver-level difference.

These tests require a real, non-offscreen OpenGL context (same posture as
tests/test_gpu_official_002.py and test_gpu_audio_005.py) -- they are not
run under QT_QPA_PLATFORM=offscreen.
"""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat

REPO_ROOT = Path(__file__).resolve().parent.parent

fmt = QSurfaceFormat()
fmt.setVersion(3, 3)
fmt.setProfile(QSurfaceFormat.CoreProfile)
QSurfaceFormat.setDefaultFormat(fmt)

_app = QApplication.instance() or QApplication(sys.argv)

from toroidamp.visualizers.gpu_canvas import GLVisualizerCanvas


def _load_lab_app():
    lab_app_path = REPO_ROOT / "experiments" / "gpu_visualizers" / "lab_app.py"
    spec = importlib.util.spec_from_file_location("lab_app_release_blockers_001", lab_app_path)
    lab_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab_app)
    return lab_app


def _max_pixel_channel(img, w, h):
    xs = (int(w * 0.1), int(w * 0.3), int(w * 0.5), int(w * 0.7), int(w * 0.9))
    ys = (int(h * 0.1), int(h * 0.3), int(h * 0.5), int(h * 0.7), int(h * 0.9))
    samples = [img.pixelColor(x, y) for x in xs for y in ys]
    return max(max(c.red(), c.green(), c.blue()) for c in samples)


class TestUserShaderPipelineHealth(unittest.TestCase):
    """Regression guard: this repo's own sample user shaders must keep
    compiling, linking, and rendering visible (non-black) content through
    the real production GL pipeline. Root-cause investigation for Blocker
    3 found no pipeline defect reproducible here -- every one of these
    files already renders correctly on a real desktop OpenGL driver."""

    @classmethod
    def setUpClass(cls):
        cls.canvas = GLVisualizerCanvas()
        cls.canvas.resize(320, 240)
        cls.canvas.show()
        _app.processEvents()
        if not cls.canvas.isValid():
            raise unittest.SkipTest("requires a live OpenGL context")

    @classmethod
    def tearDownClass(cls):
        cls.canvas.close()

    def test_01_sample_user_shadertoy_shaders_compile_and_render(self):
        shader_dir = REPO_ROOT / "user_shaders" / "shadertoy"
        shaders = sorted(shader_dir.glob("*/*.frag"))
        self.assertGreater(len(shaders), 0, "expected at least one sample user shader")

        for sp in shaders:
            with self.subTest(shader=sp.name):
                ok = self.canvas.load_shader_file(sp)
                self.canvas.update()
                self.canvas.repaint()
                img = self.canvas.grabFramebuffer()
                max_channel = _max_pixel_channel(img, img.width(), img.height())
                self.assertTrue(ok, f"{sp.name} failed to compile/link: {self.canvas.last_error_log}")
                self.assertGreater(max_channel, 3, f"{sp.name} rendered effectively all-black")

    def test_02_official_shader_still_compiles_and_renders(self):
        official = REPO_ROOT / "src" / "toroidamp" / "assets" / "official_shaders" / "toroid_identity.frag"
        ok = self.canvas.load_shader_file(official)
        self.canvas.update()
        self.canvas.repaint()
        img = self.canvas.grabFramebuffer()
        max_channel = _max_pixel_channel(img, img.width(), img.height())
        self.assertTrue(ok)
        self.assertGreater(max_channel, 3)


class TestLabBlackRenderDiagnostic(unittest.TestCase):
    """The Lab's post-load diagnostic must flag a compiled-but-black frame
    loudly (log + on-screen), and must not false-positive on a shader that
    renders real content -- see lab_app.py's _diagnose_black_render()."""

    def setUp(self):
        self.lab_app = _load_lab_app()
        self.win = self.lab_app.GPUAuthoringLabWindow()
        self.win.show()
        _app.processEvents()
        if not self.win.canvas.isValid():
            # An earlier test file in this same pytest process may have
            # set QT_QPA_PLATFORM=offscreen via os.environ.setdefault(),
            # which -- being process-wide, not per-test-file -- persists
            # for the rest of the run and leaves no live OpenGL context
            # here (same posture as test_gpu_audio_004.py).
            self.win.close()
            self.skipTest("requires a live OpenGL context (unavailable in this offscreen environment)")

    def tearDown(self):
        self.win.close()

    def _write_shader(self, name: str, body: str) -> Path:
        path = REPO_ROOT / "user_shaders" / name
        path.write_text(body, encoding="utf-8")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_03_all_black_shader_triggers_diagnostic(self):
        black_shader = self._write_shader(
            "test_release_blockers_001_black.frag",
            "void mainImage(out vec4 fragColor, in vec2 fragCoord) {\n"
            "    fragColor = vec4(0.0, 0.0, 0.0, 1.0);\n"
            "}\n",
        )
        with patch.object(self.lab_app.logger, "warning") as mock_warn:
            self.win.switch_shader_path(black_shader)

        self.assertTrue(
            any("effectively all-black" in str(c) for c in mock_warn.call_args_list),
            f"expected a black-render diagnostic warning, got: {mock_warn.call_args_list}",
        )
        self.assertIn("effectively all-black", self.win.error_view.toPlainText())

    def test_04_colorful_shader_does_not_false_positive(self):
        colorful_shader = self._write_shader(
            "test_release_blockers_001_colorful.frag",
            "void mainImage(out vec4 fragColor, in vec2 fragCoord) {\n"
            "    fragColor = vec4(1.0, 0.5, 0.25, 1.0);\n"
            "}\n",
        )
        with patch.object(self.lab_app.logger, "warning") as mock_warn:
            self.win.switch_shader_path(colorful_shader)

        self.assertFalse(
            any("effectively all-black" in str(c) for c in mock_warn.call_args_list),
            "must not flag a shader that actually renders visible content",
        )

    def test_05_compile_failure_still_uses_existing_error_path_not_diagnostic(self):
        # A genuine compile/link failure must keep going through
        # _update_ui_state()'s existing error surfacing, not the new
        # black-render diagnostic (which only runs when ok=True).
        broken_shader = self._write_shader(
            "test_release_blockers_001_broken.frag",
            "void mainImage(out vec4 fragColor, in vec2 fragCoord) {\n"
            "    fragColor = totallyUndefinedIdentifier;\n"
            "}\n",
        )
        with patch.object(self.lab_app.logger, "warning") as mock_warn:
            self.win.switch_shader_path(broken_shader)

        self.assertFalse(
            any("effectively all-black" in str(c) for c in mock_warn.call_args_list),
            "compile/link failures must not also trigger the black-render diagnostic",
        )
        self.assertNotEqual(self.win.canvas.last_error_log, "")


if __name__ == "__main__":
    unittest.main()
