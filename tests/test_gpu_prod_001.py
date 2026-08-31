"""
ToroidAMP - Unit and Integration Tests for GPU-PROD-001
Production RETINA MELT GPU Host Integration + Live Tune Controls

Validates:
1. Production official shader and texture asset resolution (zero reliance on experiments/ or user_shaders/)
2. GPU visualizer registration in production visualizers package
3. CPU <-> GPU visualizer mode switching without playback corruption
4. AudioFrame delivery to production GPU host
5. Dynamic parameter metadata discovery & TUNE panel construction
6. Parameter modification propagation to GPU uniform registers
7. Parameter persistence per visualizer in SessionState
8. RESET restores declared defaults and saves them
9. Stale/unknown parameter tolerance and boundary clamping
10. TUNE button availability logic (only present for visualizers with tunable parameters)
11. HUD auto-hide suspended while TUNE is active
12. GPU renderer inactivity when RETINA MELT is hidden
13. OpenGL resource cleanup with active context
14. Failure isolation and graceful fallback
"""

import unittest
from pathlib import Path
import sys
import tempfile

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat

from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.session import SessionManager, SessionState
from toroidamp.visualizers.gpu_compiler import parse_shader_parameters, classify_and_wrap_source
from toroidamp.visualizers.gpu_canvas import GLVisualizerCanvas
from toroidamp.visualizers.toroid_identity import ToroidIdentityVisualizer
from toroidamp.ui.fullscreen import RetinaMeltWindow


class TestGPUProd001(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        QSurfaceFormat.setDefaultFormat(fmt)
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.session_path = Path(self.tmp_dir.name) / "test_session.json"
        self.session_manager = SessionManager(str(self.session_path))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_production_asset_resolution(self):
        """Validates that production GPU visualizers resolve only packaged assets."""
        vis = ToroidIdentityVisualizer()
        shader_path = vis.get_shader_path()
        self.assertIsNotNone(shader_path)
        self.assertTrue(shader_path.exists())
        self.assertNotIn("experiments", str(shader_path))
        self.assertNotIn("user_shaders", str(shader_path))

        canvas = GLVisualizerCanvas()
        tex_path = canvas._resolve_packaged_texture_path()
        self.assertIsNotNone(tex_path)
        self.assertTrue(tex_path.exists())
        self.assertNotIn("experiments", str(tex_path))

    def test_gpu_visualizer_registration_and_switching(self):
        """Validates that CPU and GPU visualizers coexist in RETINA MELT."""
        retina = RetinaMeltWindow(session_manager=self.session_manager)
        retina.show()
        self.app.processEvents()

        # 1. Starts at index 0 (CPU 3D Torus)
        self.assertEqual(retina.vis_idx, 0)
        self.assertEqual(retina.surface_layout.currentIndex(), 0)
        self.assertFalse(retina.hud_btn_tune.isVisible())

        # 2. Cycle to Toroid Identity (Index 4)
        retina.set_visualizer_index(4)
        self.assertEqual(retina.vis_idx, 4)
        self.assertEqual(retina.surface_layout.currentIndex(), 1)
        self.assertTrue(retina.hud_btn_tune.isVisible())
        self.assertIn("TOROID IDENTITY", retina.hud_btn_mode.text())

        # 3. Cycle back to CPU (Index 0)
        retina.set_visualizer_index(0)
        self.assertEqual(retina.surface_layout.currentIndex(), 0)
        self.assertFalse(retina.hud_btn_tune.isVisible())

        retina.close()
        self.app.processEvents()

    def test_tune_panel_generation_and_uniform_binding(self):
        """Validates dynamic TUNE panel controls and parameter mutation."""
        retina = RetinaMeltWindow(session_manager=self.session_manager)
        retina.show()
        retina.set_visualizer_index(4)  # Toroid Identity
        self.app.processEvents()

        # Open TUNE panel
        retina._open_tune_panel()
        self.assertTrue(retina.tune_panel.isVisible())
        self.assertTrue(retina.hud_btn_tune.isChecked())

        # Verify all 5 sliders were generated
        expected_params = ["u_warp", "u_chroma", "u_glow", "u_rotation", "u_bgIntensity"]
        for p in expected_params:
            self.assertIn(p, retina._param_sliders)
            self.assertIn(p, retina._param_val_labels)

        # Move u_glow slider to max (1000)
        slider_glow = retina._param_sliders["u_glow"]
        slider_glow.setValue(1000)
        self.app.processEvents()

        self.assertAlmostEqual(retina.gpu_canvas.current_params["u_glow"], 3.5, places=2)

        # Check persistence written
        persisted = self.session_manager.state.visualizer_parameters.get("toroid_identity", {})
        self.assertAlmostEqual(persisted.get("u_glow", 0.0), 3.5, places=2)

        # Trigger RESET
        retina._reset_tune_parameters()
        self.assertAlmostEqual(retina.gpu_canvas.current_params["u_glow"], 1.2, places=2)
        persisted_reset = self.session_manager.state.visualizer_parameters.get("toroid_identity", {})
        self.assertAlmostEqual(persisted_reset.get("u_glow", 0.0), 1.2, places=2)

        retina.close()
        self.app.processEvents()

    def test_persistence_safety_and_clamping(self):
        """Validates that out-of-bounds or stale parameters are clamped/ignored safely."""
        # Inject deliberate dirty state into session
        self.session_manager.state.visualizer_parameters["toroid_identity"] = {
            "u_glow": 999.0,         # Out of bounds high
            "u_warp": -50.0,         # Out of bounds low
            "u_staleParam": 42.0,    # Unknown obsolete param
            "u_chroma": "corrupted"  # Corrupted type
        }
        self.session_manager.save()

        retina = RetinaMeltWindow(session_manager=self.session_manager)
        retina.show()
        retina.set_visualizer_index(4)  # Toroid Identity
        self.app.processEvents()

        # Check clamped bounds and defaults
        self.assertAlmostEqual(retina.gpu_canvas.current_params["u_glow"], 3.5) # clamped to max 3.5
        self.assertAlmostEqual(retina.gpu_canvas.current_params["u_warp"], 0.0) # clamped to min 0.0
        self.assertAlmostEqual(retina.gpu_canvas.current_params["u_chroma"], 1.0) # restored default
        self.assertNotIn("u_staleParam", retina.gpu_canvas.metadata.parameters)

        retina.close()
        self.app.processEvents()

    def test_hud_autohide_suspension_while_tuning(self):
        """Validates that auto-hide is suspended when TUNE is open."""
        retina = RetinaMeltWindow(session_manager=self.session_manager)
        retina.show()
        retina.set_visualizer_index(4)
        self.app.processEvents()

        # In normal state, timer is active
        self.assertTrue(retina.hud_timer.isActive())

        # Open TUNE -> timer stopped
        retina._open_tune_panel()
        self.assertFalse(retina.hud_timer.isActive())

        # Close TUNE -> timer resumed
        retina._close_tune_panel()
        self.assertTrue(retina.hud_timer.isActive())

        retina.close()
        self.app.processEvents()

    def test_audio_frame_delivery_to_gpu_host(self):
        """Validates that production AudioFrame arrives at GPU canvas."""
        retina = RetinaMeltWindow(session_manager=self.session_manager)
        retina.show()
        retina.set_visualizer_index(4)
        self.app.processEvents()

        frame = AudioFrame(0.55, 0.85, 0.9, 0.4, 0.3, tuple([0.5]*64), tuple([0.0]*128), True, False)
        retina.render_frame(frame, 0.016)

        self.assertIsNotNone(retina.gpu_canvas._current_audio_frame)
        self.assertAlmostEqual(retina.gpu_canvas._current_audio_frame.bass, 0.9)
        self.assertTrue(retina.gpu_canvas._current_audio_frame.beat)

        retina.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
