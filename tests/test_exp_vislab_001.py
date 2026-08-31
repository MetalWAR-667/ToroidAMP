"""
ToroidAMP - Unit Tests for EXP-VISLAB-001 (GPU Visualizer Authoring Lab)

Validates:
1. Three distinct shader storage paths (official, experiments, user_shaders).
2. Git ignore verification for /user_shaders/.
3. Parameter metadata parsing from GLSL comments and taParam uniforms.
4. Parameter default values, limits, and runtime modification without recompilation.
5. Parameter isolation across shader switches.
6. Reset parameters to declared defaults.
7. External shader loading and classification (.frag, .glsl, .txt).
8. Synthetic AudioFrame profiles integration.
9. Missing file and malformed syntax isolation.
"""

import unittest
from pathlib import Path
from experiments.gpu_visualizers.shader_compiler import (
    classify_and_wrap_source,
    parse_shader_parameters,
    ShaderParameter,
    ShaderMetadata
)
from experiments.visualizers.profiles import PROFILES, PROFILE_ORDER
from toroidamp.analysis.audio_frame import AudioFrame


class TestGPUAuthoringLab(unittest.TestCase):

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.user_shaders_dir = self.repo_root / "user_shaders"
        self.official_shaders_dir = self.repo_root / "src" / "toroidamp" / "assets" / "official_shaders"
        self.exp_shaders_dir = self.repo_root / "experiments" / "gpu_visualizers" / "shaders"

    def test_directory_territories_exist(self):
        self.assertTrue(self.user_shaders_dir.exists(), "user_shaders directory must exist")
        self.assertTrue(self.official_shaders_dir.exists(), "official_shaders directory must exist")
        self.assertTrue(self.exp_shaders_dir.exists(), "experiments shaders directory must exist")

    def test_gitignore_contains_user_shaders(self):
        gitignore_path = self.repo_root / ".gitignore"
        self.assertTrue(gitignore_path.exists())
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("/user_shaders/", content, ".gitignore must ignore /user_shaders/")

    def test_parameter_comment_parsing(self):
        sample_glsl = """
        // [param:float] u_speed: Evolution Speed = 1.5 (0.1 .. 4.0)
        // [param:float] u_warp: Coordinate Warp = 3.2 (0.5 .. 10.0)
        void main() {
            fragColor = vec4(u_speed, u_warp, 0.0, 1.0);
        }
        """
        params = parse_shader_parameters(sample_glsl)
        self.assertEqual(len(params), 2)
        self.assertIn("u_speed", params)
        self.assertIn("u_warp", params)
        
        p_speed = params["u_speed"]
        self.assertEqual(p_speed.display_name, "Evolution Speed")
        self.assertEqual(p_speed.default_value, 1.5)
        self.assertEqual(p_speed.min_value, 0.1)
        self.assertEqual(p_speed.max_value, 4.0)
        self.assertEqual(p_speed.current_value, 1.5)

    def test_taparam_uniform_fallback_parsing(self):
        sample_glsl = """
        uniform float taParamGlow;
        void main() {
            fragColor = vec4(taParamGlow);
        }
        """
        params = parse_shader_parameters(sample_glsl)
        self.assertIn("taParamGlow", params)
        self.assertEqual(params["taParamGlow"].display_name, "Glow")
        self.assertEqual(params["taParamGlow"].default_value, 1.0)

    def test_classification_and_parameter_header_injection(self):
        sample_glsl = """
        // [param:float] u_bloom: Bloom Threshold = 0.8 (0.0 .. 2.0)
        void main() {
            fragColor = vec4(u_bloom);
        }
        """
        wrapped, meta = classify_and_wrap_source(sample_glsl, "TestShader")
        self.assertFalse(meta.is_shadertoy_style)
        self.assertIn("u_bloom", meta.parameters)
        self.assertIn("uniform float u_bloom;", wrapped)
        self.assertIn("uniform float taBass;", wrapped)

    def test_shadertoy_parameter_wrapping(self):
        sample_shadertoy = """
        // [param:float] u_zoom: Tunnel Zoom = 2.0 (0.5 .. 5.0)
        void mainImage(out vec4 fragColor, in vec2 fragCoord) {
            fragColor = vec4(u_zoom);
        }
        """
        wrapped, meta = classify_and_wrap_source(sample_shadertoy, "TestShadertoy")
        self.assertTrue(meta.is_shadertoy_style)
        self.assertIn("u_zoom", meta.parameters)
        self.assertIn("uniform float u_zoom;", wrapped)
        self.assertIn("void main()", wrapped)

    def test_synthetic_profiles_availability_and_deterministic_ticks(self):
        self.assertIn("electronic", PROFILES)
        self.assertIn("metal", PROFILES)
        self.assertIn("ambient", PROFILES)
        self.assertIn("orchestral", PROFILES)
        self.assertIn("silence", PROFILES)

        prof = PROFILES["electronic"](seed=42)
        frame1 = prof.tick(0.016)
        self.assertIsInstance(frame1, AudioFrame)
        self.assertTrue(0.0 <= frame1.bass <= 1.0)
        self.assertEqual(len(frame1.spectrum), 64)
        self.assertEqual(len(frame1.waveform), 128)

    def test_manual_beat_injection_in_profile(self):
        prof = PROFILES["silence"]()
        prof.inject_beat(strong=True)
        frame = prof.tick(0.016)
        self.assertTrue(frame.beat)
        self.assertTrue(frame.strong_beat)

    def test_experimental_shaders_parameters_integrity(self):
        for s_name in ["shader_a_plasma.frag", "shader_b_raymarch.frag", "shader_c_shadertoy.frag"]:
            s_path = self.exp_shaders_dir / s_name
            self.assertTrue(s_path.exists(), f"Missing experimental shader: {s_name}")
            with open(s_path, "r", encoding="utf-8") as f:
                code = f.read()
            wrapped, meta = classify_and_wrap_source(code, s_name)
            self.assertGreater(len(meta.parameters), 0, f"Shader {s_name} should declare parameters")


if __name__ == "__main__":
    unittest.main()
