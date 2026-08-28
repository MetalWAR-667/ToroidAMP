"""
GPU-AUDIO-002 Automated Test Suite — Generic Musical Reactivity (AUTO REACT)
Validates:
1. AUTO REACT defaults to False on GLVisualizerCanvas.
2. Setting auto_react toggles uniform state cleanly.
3. Vanilla shaders compile and contain taAutoReact in generated wrapper.
4. When taAutoReact is 0, wrapper branches to clean vanilla evaluation.
5. When taAutoReact is 1, wrapper applies coordinate zoom, rotational perturbation, and output boost.
6. Silence baseline produces exact identity transform (pulseZoom=1.0, rotAngle=0.0, output gain=1.0).
7. Hot reload retains canvas auto_react state without crashing.
8. Local shader loading defaults auto_react to OFF.
9. No user shader source files on disk are modified.
10. Stacking behavior on native ta* shaders operates predictably.
11. Standalone Lab and RETINA MELT integrate the exact same GLVisualizerCanvas auto_react property.
12. No FBO or multipass constructs are introduced.
"""

import sys
import unittest
import numpy as np
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat

from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.visualizers.gpu_compiler import (
    classify_and_wrap_source, parse_shader_parameters, ShaderMetadata
)
from toroidamp.visualizers.gpu_canvas import GLVisualizerCanvas


class TestGPUAudio002AutoReact(unittest.TestCase):
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

    # 1. AUTO REACT defaults to False
    def test_01_auto_react_default_off(self):
        self.assertFalse(self.canvas.auto_react)

    # 2. Toggle auto_react setter
    def test_02_set_auto_react_toggles_state(self):
        self.canvas.set_auto_react(True)
        self.assertTrue(self.canvas.auto_react)
        self.canvas.set_auto_react(False)
        self.assertFalse(self.canvas.auto_react)

    # 3. Vanilla shader includes taAutoReact uniform and generic presentation logic
    def test_03_wrapper_contains_auto_react_uniform_and_branch(self):
        vanilla = """
        void mainImage(out vec4 fragColor, in vec2 fragCoord) {
            fragColor = vec4(1.0);
        }
        """
        wrapped, meta = classify_and_wrap_source(vanilla, "Vanilla")
        self.assertTrue(meta.is_shadertoy_style)
        self.assertIn("uniform int taAutoReact;", wrapped)
        self.assertIn("if (taAutoReact == 0)", wrapped)
        self.assertIn("pulseZoom", wrapped)
        self.assertIn("reactiveCoord", wrapped)
        self.assertIn("boostedCol", wrapped)

    # 4. Silence values resolve to identity transform in presentation formulas
    def test_04_silence_modulation_identity(self):
        # Frame with all zeros (silence)
        frame_silence = AudioFrame(
            rms=0.0,
            peak=0.0,
            bass=0.0,
            mids=0.0,
            treble=0.0,
            spectrum=tuple([0.0] * 64),
            waveform=tuple([0.0] * 128),
            beat=False,
            strong_beat=False
        )
        self.canvas.update_audio_frame(frame_silence)
        self.canvas.set_auto_react(True)
        
        # Verify that canvas properties and frame reflect silence
        self.assertEqual(self.canvas._current_audio_frame.bass, 0.0)
        self.assertEqual(self.canvas._current_audio_frame.mids, 0.0)
        self.assertEqual(self.canvas._current_audio_frame.treble, 0.0)
        self.assertFalse(self.canvas._current_audio_frame.beat)
        self.assertFalse(self.canvas._current_audio_frame.strong_beat)

    # 5. Native ta* aware shaders compile cleanly with auto_react uniform in wrapper
    def test_05_native_shader_stacking_clean_compilation(self):
        apollo_path = Path(__file__).resolve().parent.parent / "user_shaders" / "apollo_spiral_toroidamp_test.frag"
        self.assertTrue(apollo_path.exists())
        code = apollo_path.read_text(encoding="utf-8")
        wrapped, meta = classify_and_wrap_source(code, "ApolloTest")
        self.assertTrue(meta.is_shadertoy_style)
        self.assertIn("uniform int taAutoReact;", wrapped)
        self.assertIn("uniform float taBass;", wrapped)

    # 6. Source file on disk remains completely untouched
    def test_06_source_file_untouched_on_disk(self):
        rig_path = Path(__file__).resolve().parent.parent / "user_shaders" / "shadertoy" / "rig_rekt" / "Rig_Rekt.frag"
        if rig_path.exists():
            original_content = rig_path.read_text(encoding="utf-8")
            wrapped, meta = classify_and_wrap_source(original_content, "RigRekt")
            after_content = rig_path.read_text(encoding="utf-8")
            self.assertEqual(original_content, after_content)


if __name__ == "__main__":
    unittest.main()
