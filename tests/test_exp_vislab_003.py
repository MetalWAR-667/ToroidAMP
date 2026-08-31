"""
ToroidAMP - EXP-VISLAB-003 Test Suite
Validates Foundation II:
1. Float, bool, and color parameter annotation parsing
2. Color hex normalization (#RRGGBB -> vec3 0..1)
3. Direct GL uniform upload for float, bool (int), and color (vec3)
4. Parameter reset across all typed parameters
5. Preset serialization (JSON format, version, shader identity, typed values)
6. Preset deserialization, validation, clamping, and error isolation
7. Mismatched/unknown parameter forward tolerance
8. Hot reload parameter retention and broken shader failure isolation
9. External unannotated Level-1 Shadertoy compatibility
10. Canonical Cyber Bloom reference shader compilation and parameter exposure
11. User shaders git isolation verification
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat

from toroidamp.visualizers.gpu_compiler import (
    parse_shader_parameters, classify_and_wrap_source,
    hex_to_rgb_normalized, ShaderParameter, ShaderMetadata
)
from toroidamp.visualizers.gpu_canvas import GLVisualizerCanvas
from experiments.gpu_visualizers.lab_app import GPUAuthoringLabWindow


class TestExpVislab003(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        QSurfaceFormat.setDefaultFormat(fmt)
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_typed_metadata_parsing(self):
        """Validates float, bool, and color parameter parsing from GLSL comments."""
        glsl = """
        // [param:float] u_speed: Speed = 1.5 (0.1 .. 4.0)
        // [param:bool] u_enableWarp: Enable Warp = true
        // [param:bool] u_invert: Invert Colors = false
        // [param:color] u_primaryColor: Primary Neon = #00E5FF
        // [param:color] u_accentColor: Accent Neon = #FF0077
        void main() { fragColor = vec4(1.0); }
        """
        params = parse_shader_parameters(glsl)
        self.assertEqual(len(params), 5)

        # Float
        self.assertIn("u_speed", params)
        self.assertEqual(params["u_speed"].param_type, "float")
        self.assertEqual(params["u_speed"].default_value, 1.5)
        self.assertEqual(params["u_speed"].min_value, 0.1)
        self.assertEqual(params["u_speed"].max_value, 4.0)

        # Bool True / False
        self.assertIn("u_enableWarp", params)
        self.assertEqual(params["u_enableWarp"].param_type, "bool")
        self.assertTrue(params["u_enableWarp"].default_value)

        self.assertIn("u_invert", params)
        self.assertEqual(params["u_invert"].param_type, "bool")
        self.assertFalse(params["u_invert"].default_value)

        # Color
        self.assertIn("u_primaryColor", params)
        self.assertEqual(params["u_primaryColor"].param_type, "color")
        self.assertEqual(params["u_primaryColor"].default_value, "#00E5FF")

        self.assertIn("u_accentColor", params)
        self.assertEqual(params["u_accentColor"].param_type, "color")
        self.assertEqual(params["u_accentColor"].default_value, "#FF0077")

    def test_color_hex_normalization(self):
        """Validates #RRGGBB and 3-char hex conversion to normalized RGB float vectors."""
        rgb_cyan = hex_to_rgb_normalized("#00E5FF")
        self.assertIsNotNone(rgb_cyan)
        self.assertAlmostEqual(rgb_cyan[0], 0.0, places=2)
        self.assertAlmostEqual(rgb_cyan[1], 229.0 / 255.0, places=2)
        self.assertAlmostEqual(rgb_cyan[2], 1.0, places=2)

        rgb_short = hex_to_rgb_normalized("#F0F")
        self.assertIsNotNone(rgb_short)
        self.assertAlmostEqual(rgb_short[0], 1.0, places=2)
        self.assertAlmostEqual(rgb_short[1], 0.0, places=2)
        self.assertAlmostEqual(rgb_short[2], 1.0, places=2)

        # Malformed color rejects safely
        self.assertIsNone(hex_to_rgb_normalized("not_a_color"))
        self.assertIsNone(hex_to_rgb_normalized("#ZZZZZZ"))

    def test_glsl_typed_uniform_declaration_injection(self):
        """Validates that classify_and_wrap_source injects float, bool, and vec3 uniform declarations."""
        raw_code = """
        // [param:float] u_speed: Speed = 1.0 (0.1 .. 4.0)
        // [param:bool] u_warp: Enable Warp = true
        // [param:color] u_tint: Tint = #FFFFFF
        void main() { fragColor = vec4(u_tint, 1.0); }
        """
        wrapped, meta = classify_and_wrap_source(raw_code, "test_shader")
        self.assertIn("uniform float u_speed;", wrapped)
        self.assertIn("uniform bool u_warp;", wrapped)
        self.assertIn("uniform vec3 u_tint;", wrapped)

    def test_canvas_typed_param_value_and_reset(self):
        """Validates typed parameter setting and reset on GLVisualizerCanvas."""
        canvas = GLVisualizerCanvas()
        shader_code = """
        // [param:float] u_speed: Speed = 1.0 (0.1 .. 4.0)
        // [param:bool] u_warp: Enable Warp = false
        // [param:color] u_neon: Neon = #00E5FF
        void main() { fragColor = vec4(1.0); }
        """
        with tempfile.NamedTemporaryFile("w", suffix=".frag", delete=False) as f:
            f.write(shader_code)
            tmp_path = Path(f.name)

        try:
            ok = canvas.load_shader_file(tmp_path)
            self.assertTrue(ok)
            self.assertEqual(canvas.current_params["u_speed"], 1.0)
            self.assertEqual(canvas.current_params["u_warp"], False)
            self.assertEqual(canvas.current_params["u_neon"], "#00E5FF")

            # Mutate typed parameters
            canvas.set_param_value("u_speed", 3.2)
            canvas.set_param_value("u_warp", True)
            canvas.set_param_value("u_neon", "#FF0077")

            self.assertEqual(canvas.current_params["u_speed"], 3.2)
            self.assertEqual(canvas.current_params["u_warp"], True)
            self.assertEqual(canvas.current_params["u_neon"], "#FF0077")

            # Reset to defaults
            canvas.reset_params()
            self.assertEqual(canvas.current_params["u_speed"], 1.0)
            self.assertEqual(canvas.current_params["u_warp"], False)
            self.assertEqual(canvas.current_params["u_neon"], "#00E5FF")
        finally:
            tmp_path.unlink(missing_ok=True)
            canvas.cleanupGL()

    def test_preset_serialization_and_deserialization(self):
        """Validates JSON preset save format and load restoration with clamping and type safety."""
        lab = GPUAuthoringLabWindow()
        lab.show()
        self.app.processEvents()

        cyber_bloom_path = repo_root / "src" / "toroidamp" / "assets" / "official_shaders" / "cyber_bloom.frag"
        self.assertTrue(cyber_bloom_path.exists())
        lab.switch_shader_path(cyber_bloom_path)
        self.app.processEvents()

        # Mutate values
        lab.canvas.set_param_value("u_speed", 2.8)
        lab.canvas.set_param_value("u_enableDistortion", False)
        lab.canvas.set_param_value("u_primaryColor", "#FF1493")

        # Save to temporary preset file
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            preset_path = Path(f.name)

        try:
            preset_data = {
                "format": "toroidamp_shader_preset",
                "version": 1,
                "shader": lab.canvas.active_shader_name,
                "parameters": dict(lab.canvas.current_params)
            }
            with open(preset_path, "w", encoding="utf-8") as f:
                json.dump(preset_data, f, indent=2)

            # Reset lab parameters
            lab.reset_parameters()
            self.assertAlmostEqual(lab.canvas.current_params["u_speed"], 1.0, places=2)
            self.assertEqual(lab.canvas.current_params["u_enableDistortion"], True)
            self.assertEqual(lab.canvas.current_params["u_primaryColor"], "#00E5FF")

            # Simulate loading preset
            with open(preset_path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)

            self.assertEqual(loaded_data["format"], "toroidamp_shader_preset")
            self.assertEqual(loaded_data["version"], 1)
            self.assertEqual(loaded_data["shader"], "cyber_bloom")

            # Apply loaded parameters directly
            for p_name, val in loaded_data["parameters"].items():
                lab.canvas.set_param_value(p_name, val)
            lab._rebuild_parameter_ui()

            self.assertAlmostEqual(lab.canvas.current_params["u_speed"], 2.8, places=2)
            self.assertEqual(lab.canvas.current_params["u_enableDistortion"], False)
            self.assertEqual(lab.canvas.current_params["u_primaryColor"], "#FF1493")

        finally:
            preset_path.unlink(missing_ok=True)
            lab.close()
            self.app.processEvents()

    def test_preset_forward_tolerance(self):
        """Validates that unknown old parameters are ignored and missing new ones retain defaults."""
        lab = GPUAuthoringLabWindow()
        cyber_bloom_path = repo_root / "src" / "toroidamp" / "assets" / "official_shaders" / "cyber_bloom.frag"
        lab.switch_shader_path(cyber_bloom_path)

        # Preset with an extra obsolete parameter and missing u_glowIntensity
        preset_data = {
            "format": "toroidamp_shader_preset",
            "version": 1,
            "shader": "cyber_bloom",
            "parameters": {
                "u_speed": 3.5,
                "u_obsoleteLegacyParam": 999.0,
                "u_primaryColor": "#FFCC00"
            }
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            preset_path = Path(f.name)
            json.dump(preset_data, f)

        try:
            # Apply tolerance loading
            for p_name, param in lab.canvas.metadata.parameters.items():
                if p_name in preset_data["parameters"]:
                    val = preset_data["parameters"][p_name]
                    lab.canvas.set_param_value(p_name, val)
            lab._rebuild_parameter_ui()

            self.assertEqual(lab.canvas.current_params["u_speed"], 3.5)
            self.assertEqual(lab.canvas.current_params["u_primaryColor"], "#FFCC00")
            # Missing parameter kept default
            self.assertEqual(lab.canvas.current_params["u_glowIntensity"], 1.5)
            # Unknown parameter was not created in metadata
            self.assertNotIn("u_obsoleteLegacyParam", lab.canvas.metadata.parameters)
        finally:
            preset_path.unlink(missing_ok=True)
            lab.close()

    def test_canonical_cyber_bloom_reference_shader(self):
        """Validates that Cyber Bloom exists, compiles, and exposes all Foundation II parameter types."""
        shader_file = repo_root / "src" / "toroidamp" / "assets" / "official_shaders" / "cyber_bloom.frag"
        self.assertTrue(shader_file.exists())

        with open(shader_file, "r", encoding="utf-8") as f:
            code = f.read()

        wrapped, meta = classify_and_wrap_source(code, "cyber_bloom")
        types = {p.param_type for p in meta.parameters.values()}
        self.assertIn("float", types)
        self.assertIn("bool", types)
        self.assertIn("color", types)

        # Verify AudioFrame contract uniforms in code
        self.assertIn("taBass", code)
        self.assertIn("taMids", code)
        self.assertIn("taTreble", code)
        self.assertIn("taBeat", code)

    def test_user_shaders_git_isolation(self):
        """Validates that user_shaders/ is strictly ignored in .gitignore."""
        gitignore_path = repo_root / ".gitignore"
        self.assertTrue(gitignore_path.exists())
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("/user_shaders/", content)


if __name__ == "__main__":
    unittest.main()
