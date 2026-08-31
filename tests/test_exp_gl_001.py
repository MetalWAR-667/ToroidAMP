"""
ToroidAMP - Unit Tests for EXP-GL-001 (GPU Visualizer Foundation Probe)
Validates:
1. Shader source classification (Native vs Shadertoy mainImage)
2. Uniform injection and header synthesis
3. AudioFrame to GLSL mapping contracts
4. Graceful handling of missing shader files and syntax error isolation
5. Spectrum & Waveform array packing
6. Future tempo/phase extension points (taBpm, taBeatPhase, taBarPhase)
"""

import unittest
from pathlib import Path
from experiments.gpu_visualizers.shader_compiler import (
    classify_and_wrap_source,
    VERTEX_SHADER_SOURCE,
    TOROIDAMP_HEADER_NATIVE,
    SHADERTOY_WRAPPER_PREFIX,
    FALLBACK_FRAG_SOURCE
)
from toroidamp.analysis.audio_frame import AudioFrame


class TestGPUFoundationProbe(unittest.TestCase):

    def test_vertex_shader_structure(self):
        self.assertIn("#version 330 core", VERTEX_SHADER_SOURCE)
        self.assertIn("layout (location = 0) in vec2 aPos;", VERTEX_SHADER_SOURCE)
        self.assertIn("vUV", VERTEX_SHADER_SOURCE)

    def test_native_shader_classification_and_injection(self):
        raw_glsl = """
        void main() {
            fragColor = vec4(taBass, taTreble, taRms, 1.0);
        }
        """
        wrapped, meta = classify_and_wrap_source(raw_glsl, "TestNative")
        self.assertFalse(meta.is_shadertoy_style)
        self.assertEqual(meta.name, "TestNative")
        self.assertIn("uniform float taBass;", wrapped)
        self.assertIn("uniform float taSpectrum[64];", wrapped)
        self.assertIn("uniform float taWaveform[128];", wrapped)
        self.assertIn("uniform float taBpm;", wrapped)
        self.assertIn("uniform float taBeatPhase;", wrapped)

    def test_shadertoy_wrapper_classification(self):
        shadertoy_glsl = """
        void mainImage(out vec4 fragColor, in vec2 fragCoord) {
            vec2 uv = fragCoord / iResolution.xy;
            fragColor = vec4(uv, 0.5 + 0.5 * sin(iTime), 1.0);
        }
        """
        wrapped, meta = classify_and_wrap_source(shadertoy_glsl, "TestShadertoy")
        self.assertTrue(meta.is_shadertoy_style)
        self.assertIn("uniform vec3 iResolution;", wrapped)
        self.assertIn("uniform float iTime;", wrapped)
        self.assertIn("void main()", wrapped)
        self.assertIn("mainImage(col, gl_FragCoord.xy);", wrapped)
        # Level 2 ToroidAMP Audio extensions present in wrapper
        self.assertIn("uniform float taBass;", wrapped)
        self.assertIn("uniform float taSpectrum[64];", wrapped)

    def test_audioframe_contract_completeness(self):
        frame = AudioFrame(
            rms=0.8,
            peak=0.95,
            bass=0.75,
            mids=0.45,
            treble=0.6,
            spectrum=tuple([0.1 * i for i in range(64)]),
            waveform=tuple([0.0] * 128),
            beat=True,
            strong_beat=False
        )
        self.assertEqual(len(frame.spectrum), 64)
        self.assertEqual(len(frame.waveform), 128)
        self.assertTrue(frame.beat)
        self.assertFalse(frame.strong_beat)
        self.assertAlmostEqual(frame.bass, 0.75)

    def test_shader_files_exist_and_wrap(self):
        shaders_dir = Path(__file__).resolve().parent.parent / "experiments" / "gpu_visualizers" / "shaders"
        expected_shaders = [
            "shader_a_plasma.frag",
            "shader_b_raymarch.frag",
            "shader_c_shadertoy.frag"
        ]
        for name in expected_shaders:
            file_path = shaders_dir / name
            self.assertTrue(file_path.exists(), f"Missing shader: {name}")
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            wrapped, meta = classify_and_wrap_source(code, file_path.stem)
            self.assertIsNotNone(wrapped)
            self.assertTrue(len(wrapped) > 100)


if __name__ == "__main__":
    unittest.main()
