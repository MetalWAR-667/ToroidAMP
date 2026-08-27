"""
ToroidAMP - Unit Tests for GPU-OFFICIAL-001
First Official GPU Visualizer: Toroid Identity

Validates:
1. Packaged Artwork & Shader Asset Existence:
   - src/toroidamp/assets/images/ToroidAMP.png exists
   - src/toroidamp/assets/official_shaders/toroid_identity.frag exists
   - src/toroidamp/assets/official_shaders/minimal_reference.frag exists
2. Shader Compilation & Metadata Parsing:
   - Toroid Identity extracts all authoring parameters (u_warp, u_chroma, u_glow, u_rotation, u_bgIntensity)
   - Minimal Reference extracts authoring parameters (u_rotSpeed, u_ringCount, u_colorCycle)
   - Both detect taTexture0 usage where applicable
3. AudioFrame Contracts & Uniform Injections:
   - Native uniform wrappers include taBass, taMids, taTreble, taBeat, taStrongBeat, taSpectrum, taTexture0
4. OpenGL Context Execution (Conditional on Hardware OpenGL Support):
   - QOpenGLTexture builds and generates mipmaps from packaged ToroidAMP.png
   - Fragment shaders compile cleanly with no link errors in QOpenGLShaderProgram
"""

import unittest
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "src"))

from experiments.gpu_visualizers.shader_compiler import (
    classify_and_wrap_source, parse_shader_parameters,
    VERTEX_SHADER_SOURCE, TOROIDAMP_HEADER_NATIVE
)
from toroidamp.analysis.audio_frame import AudioFrame


class TestGPUOfficial001(unittest.TestCase):

    def setUp(self):
        from PySide6.QtGui import QSurfaceFormat
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        QSurfaceFormat.setDefaultFormat(fmt)
        self.official_shader_dir = repo_root / "src" / "toroidamp" / "assets" / "official_shaders"
        self.packaged_img_path = repo_root / "src" / "toroidamp" / "assets" / "images" / "ToroidAMP.png"

    def test_packaged_asset_files_exist(self):
        """Validates that all required official assets are present in the package tree."""
        self.assertTrue(self.packaged_img_path.exists(), f"Missing packaged artwork: {self.packaged_img_path}")
        self.assertTrue((self.official_shader_dir / "toroid_identity.frag").exists(), "Missing toroid_identity.frag")
        self.assertTrue((self.official_shader_dir / "minimal_reference.frag").exists(), "Missing minimal_reference.frag")

    def test_toroid_identity_parameter_parsing(self):
        """Validates that authoring parameters in toroid_identity.frag are discovered correctly."""
        shader_file = self.official_shader_dir / "toroid_identity.frag"
        with open(shader_file, "r", encoding="utf-8") as f:
            code = f.read()

        params = parse_shader_parameters(code)
        expected_params = ["u_warp", "u_chroma", "u_glow", "u_rotation", "u_bgIntensity"]
        for p in expected_params:
            self.assertIn(p, params, f"Missing parameter {p} in toroid_identity.frag")
            self.assertGreaterEqual(params[p].default_value, params[p].min_value)
            self.assertLessEqual(params[p].default_value, params[p].max_value)

        wrapped, meta = classify_and_wrap_source(code, "toroid_identity")
        self.assertFalse(meta.is_shadertoy_style)
        self.assertTrue(meta.uses_texture)
        self.assertIn("uniform sampler2D taTexture0;", wrapped)
        self.assertIn("uniform float taBass;", wrapped)
        self.assertIn("uniform int taStrongBeat;", wrapped)

    def test_minimal_reference_parameter_parsing(self):
        """Validates that authoring parameters in minimal_reference.frag are discovered correctly."""
        shader_file = self.official_shader_dir / "minimal_reference.frag"
        with open(shader_file, "r", encoding="utf-8") as f:
            code = f.read()

        params = parse_shader_parameters(code)
        expected_params = ["u_rotSpeed", "u_ringCount", "u_colorCycle"]
        for p in expected_params:
            self.assertIn(p, params, f"Missing parameter {p} in minimal_reference.frag")

        wrapped, meta = classify_and_wrap_source(code, "minimal_reference")
        self.assertFalse(meta.is_shadertoy_style)
        self.assertFalse(meta.uses_texture)
        self.assertIn("uniform float taBass;", wrapped)

    def test_opengl_compilation_and_texture_binding(self):
        """Validates GLSL compilation and texture upload within a live Qt OpenGL context when available."""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QSurfaceFormat, QImage
        from PySide6.QtOpenGLWidgets import QOpenGLWidget
        from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture

        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        QSurfaceFormat.setDefaultFormat(fmt)

        app = QApplication.instance() or QApplication(sys.argv)

        class HeadlessGLTest(QOpenGLWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.compile_results = {}
                self.tex_created = False
                self.context_valid = False

            def initializeGL(self):
                self.context_valid = self.context().isValid()
                if not self.context_valid:
                    return

                # 1. Test Texture upload
                img = QImage(str(repo_root / "src" / "toroidamp" / "assets" / "images" / "ToroidAMP.png"))
                if not img.isNull():
                    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
                    img = img.flipped() if hasattr(img, 'flipped') else img.mirrored(False, True)
                    tex = QOpenGLTexture(img)
                    tex.setMinMagFilters(QOpenGLTexture.LinearMipMapLinear, QOpenGLTexture.Linear)
                    tex.generateMipMaps()
                    tex.setWrapMode(QOpenGLTexture.ClampToEdge)
                    self.tex_created = tex.isCreated()

                # 2. Test Toroid Identity Compilation
                shaders_to_test = [
                    ("toroid_identity", repo_root / "src" / "toroidamp" / "assets" / "official_shaders" / "toroid_identity.frag"),
                    ("minimal_reference", repo_root / "src" / "toroidamp" / "assets" / "official_shaders" / "minimal_reference.frag")
                ]

                for s_name, s_path in shaders_to_test:
                    with open(s_path, "r", encoding="utf-8") as f:
                        src = f.read()
                    wrapped, _ = classify_and_wrap_source(src, s_name)
                    prog = QOpenGLShaderProgram(self)
                    v_ok = prog.addShaderFromSourceCode(QOpenGLShader.Vertex, VERTEX_SHADER_SOURCE)
                    f_ok = prog.addShaderFromSourceCode(QOpenGLShader.Fragment, wrapped)
                    link_ok = prog.link()
                    self.compile_results[s_name] = (v_ok, f_ok, link_ok, prog.log())

        w = HeadlessGLTest()
        w.show()
        app.processEvents()

        # If platform supports hardware OpenGL in headless mode, assert
        if w.context_valid:
            self.assertTrue(w.tex_created, "QOpenGLTexture failed to allocate and create from packaged artwork")
            for s_name, (v_ok, f_ok, link_ok, log) in w.compile_results.items():
                self.assertTrue(v_ok, f"{s_name} Vertex shader compilation failed: {log}")
                self.assertTrue(f_ok, f"{s_name} Fragment shader compilation failed: {log}")
                self.assertTrue(link_ok, f"{s_name} Shader link failed: {log}")

    def test_parameter_propagation_and_reset(self):
        """Validates that parameters set on canvas propagate to current_params and reset correctly."""
        from PySide6.QtWidgets import QApplication
        from experiments.gpu_visualizers.lab_app import GLVisualizerCanvas
        app = QApplication.instance() or QApplication(sys.argv)
        canvas = GLVisualizerCanvas()
        canvas.show()
        app.processEvents()
        
        # Load official shader
        ok = canvas.load_shader_file(self.official_shader_dir / "toroid_identity.frag")
        self.assertTrue(ok)
        
        # Verify defaults
        self.assertAlmostEqual(canvas.current_params["u_warp"], 1.0)
        self.assertAlmostEqual(canvas.current_params["u_chroma"], 1.0)
        self.assertAlmostEqual(canvas.current_params["u_glow"], 1.2)
        
        # Mutate parameter
        canvas.set_param_value("u_warp", 2.8)
        canvas.set_param_value("u_glow", 3.2)
        self.assertAlmostEqual(canvas.current_params["u_warp"], 2.8)
        self.assertAlmostEqual(canvas.current_params["u_glow"], 3.2)
        
        # Verify survival across reload
        canvas.reload_current_shader()
        self.assertAlmostEqual(canvas.current_params["u_warp"], 2.8)
        self.assertAlmostEqual(canvas.current_params["u_glow"], 3.2)
        
        # Verify reset
        canvas.reset_params()
        self.assertAlmostEqual(canvas.current_params["u_warp"], 1.0)
        self.assertAlmostEqual(canvas.current_params["u_glow"], 1.2)


if __name__ == "__main__":
    unittest.main()
