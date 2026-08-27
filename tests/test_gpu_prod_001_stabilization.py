"""
ToroidAMP - Unit and Integration Tests for GPU-PROD-001 Stabilization & RETINA-Only Policy
Validates:
1. Multi-cycle RETINA MELT re-entry (5 consecutive enter/exit cycles maintain valid GL resources)
2. Explicit HUD visibility state machine (HUD_PINNED on left click, HUD_HIDDEN on right click)
3. Direct TUNE slider value mutation and session persistence
4. TUNE overlay event protection (slider drags don't dismiss HUD or lose events)
5. Clean CPU and GPU visualizer cycling in both RETINA MELT and NORMAL modes
6. RETINA-only policy: GPU visualizer in NORMAL mode shows deliberate branded placeholder, not a black frame
7. One-click RETINA MELT entry from NORMAL placeholder
8. Normal CPU visualizer preview rendering remains intact
"""

import unittest
from pathlib import Path
import sys
import tempfile

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QSurfaceFormat, QMouseEvent

from toroidamp.analysis.audio_frame import AudioFrame
from toroidamp.session import SessionManager, SessionState
from toroidamp.visualizers.toroid_identity import ToroidIdentityVisualizer
from toroidamp.ui.fullscreen import RetinaMeltWindow
from toroidamp.ui.modules.visualizer_module import VisualizerModule
from toroidamp.ui.window_manager import WindowManager


class TestGPUProd001Stabilization(unittest.TestCase):

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

    def test_multi_cycle_retina_reentry(self):
        """Scenario 1: Multi-cycle RETINA MELT enter/exit must preserve GL resources without destruction."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.show()
        melt.set_visualizer_index(4)  # Toroid Identity
        self.app.processEvents()

        # Perform 5 consecutive exit/re-enter cycles
        for cycle in range(5):
            melt.hide()
            self.app.processEvents()
            melt.show()
            self.app.processEvents()

            # Assert GPU canvas remains the selected visualizer mode
            self.assertEqual(melt.surface_layout.currentIndex(), 1)
            self.assertEqual(melt.vis_idx, 4)
            if melt.gpu_canvas.isValid():
                self.assertIsNotNone(melt.gpu_canvas._program, f"Program lost on cycle {cycle}")
                self.assertIsNotNone(melt.gpu_canvas._vao, f"VAO lost on cycle {cycle}")
                self.assertIsNotNone(melt.gpu_canvas._texture0, f"Texture lost on cycle {cycle}")

        melt.close()
        self.app.processEvents()

    def test_explicit_hud_visibility_left_right_click(self):
        """Scenarios 6 & 7: LEFT CLICK pins HUD, RIGHT CLICK hides HUD & closes TUNE."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.show_fullscreen_experience()
        self.app.processEvents()

        # Right click to hide
        press_right = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(100, 100), Qt.RightButton, Qt.RightButton, Qt.NoModifier)
        melt.mousePressEvent(press_right)
        self.assertEqual(melt._hud_state, "HUD_HIDDEN")
        self.assertFalse(melt.hud.isVisible())

        # Left click to pin
        press_left = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(100, 100), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        melt.mousePressEvent(press_left)
        self.assertEqual(melt._hud_state, "HUD_PINNED")
        self.assertTrue(melt.hud.isVisible())
        self.assertFalse(melt.hud_timer.isActive())  # Pinned means no auto-hide countdown

        melt.close()
        self.app.processEvents()

    def test_tune_slider_event_and_parameter_propagation(self):
        """Scenarios 2 & 5: TUNE open keeps HUD pinned and propagates slider values cleanly."""
        melt = RetinaMeltWindow(session_manager=self.session_manager)
        melt.set_visualizer_index(4)  # Toroid Identity
        melt.show_fullscreen_experience()
        self.app.processEvents()

        melt._open_tune_panel()
        self.assertTrue(melt.tune_panel.isVisible())
        self.assertFalse(melt.hud_timer.isActive())  # Auto-hide suspended

        # Drag all 5 sliders and verify parameter updates
        expected_params = {
            "u_warp": 2.5,
            "u_chroma": 3.0,
            "u_glow": 2.8,
            "u_rotation": 2.0,
            "u_bgIntensity": 1.5,
        }

        for p_name, target_val in expected_params.items():
            slider = melt._param_sliders[p_name]
            meta_p = melt.gpu_canvas.metadata.parameters[p_name]
            span = meta_p.max_value - meta_p.min_value
            slider_pos = int(round(((target_val - meta_p.min_value) / span) * 1000.0))
            slider.setValue(slider_pos)
            self.app.processEvents()

            self.assertAlmostEqual(melt.gpu_canvas.current_params[p_name], target_val, places=2)

        # Right click closes TUNE and hides HUD
        press_right = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(100, 100), Qt.RightButton, Qt.RightButton, Qt.NoModifier)
        melt.mousePressEvent(press_right)
        self.assertFalse(melt.tune_panel.isVisible())
        self.assertFalse(melt.hud.isVisible())

        melt.close()
        self.app.processEvents()

    def test_normal_mode_retina_only_placeholder(self):
        """Validates that NORMAL mode displays deliberate branded placeholder for GPU visualizers."""
        vis_mod = VisualizerModule()
        vis_mod.show()
        self.app.processEvents()

        # 1. CPU visualizer mode (0: 3D Toroid) -> Stack page 0 (CPU Pixmap)
        vis_mod.vis_idx = 0
        vis_mod._update_presentation_mode()
        self.assertEqual(vis_mod.surface_stack.currentIndex(), 0)
        self.assertIn("3D TOROID", vis_mod.btn_switch.text())

        dummy_frame = AudioFrame(0.5, 0.8, 0.9, 0.4, 0.3, tuple([0.5]*64), tuple([0.0]*128), True, False)
        vis_mod.render_frame(dummy_frame, 0.016)
        pix = vis_mod.vis_label.pixmap()
        self.assertIsNotNone(pix)
        self.assertFalse(pix.isNull())

        # 2. GPU visualizer mode (4: Toroid Identity) -> Stack page 1 (Branded RETINA Placeholder)
        vis_mod.vis_idx = 4
        vis_mod._update_presentation_mode()
        self.assertEqual(vis_mod.surface_stack.currentIndex(), 1)
        self.assertIn("TOROID IDENTITY", vis_mod.btn_switch.text())
        self.assertIn("TOROID IDENTITY", vis_mod.lbl_placeholder_name.text())
        self.assertTrue(vis_mod.btn_enter_retina.isVisible())

        vis_mod.close()
        self.app.processEvents()

    def test_one_click_retina_melt_entry_and_return(self):
        """Validates that entering RETINA MELT from NORMAL placeholder opens directly with GPU visualizer."""
        from toroidamp.audio.player import PlayerEngine
        from toroidamp.analysis.audio_frame import AnalysisHandoff
        from toroidamp.audio.playlist import PlaylistManager

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()
        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=self.session_manager)
        wm._toggle_vis()
        self.app.processEvents()

        # Select Toroid Identity in NORMAL mode
        wm.vis_mod.vis_idx = 4
        wm.vis_mod._update_presentation_mode()
        self.assertEqual(wm.vis_mod.surface_stack.currentIndex(), 1)

        # Trigger RETINA entry
        wm._enter_retina_melt()
        self.app.processEvents()

        self.assertTrue(wm.retina_melt.isVisible())
        self.assertEqual(wm.retina_melt.vis_idx, 4)
        self.assertEqual(wm.retina_melt.surface_layout.currentIndex(), 1)

        # Exit RETINA back to NORMAL
        wm._exit_retina_melt()
        self.app.processEvents()

        self.assertFalse(wm.retina_melt.isVisible())
        self.assertTrue(wm.chassis.isVisible())
        self.assertEqual(wm.vis_mod.vis_idx, 4)
        self.assertEqual(wm.vis_mod.surface_stack.currentIndex(), 1)

        wm.shutdown()
        self.app.processEvents()

    def test_initial_startup_gpu_placeholder_synchronization(self):
        """Regression test for Initial GPU Placeholder Synchronization (without manual cycling)."""
        from toroidamp.audio.player import PlayerEngine
        from toroidamp.analysis.audio_frame import AnalysisHandoff
        from toroidamp.audio.playlist import PlaylistManager

        # Seed session with Toroid Identity (index 4) selected
        self.session_manager.state.selected_visualizer_idx = 4
        self.session_manager.save()

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()
        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=self.session_manager)
        wm._toggle_vis()
        self.app.processEvents()

        # VisualizerModule must immediately reflect Toroid Identity & stack page 1 without cycling
        self.assertEqual(wm.vis_mod.vis_idx, 4)
        self.assertEqual(wm.vis_mod.surface_stack.currentIndex(), 1)
        self.assertIn("TOROID IDENTITY", wm.vis_mod.btn_switch.text())
        self.assertIn("TOROID IDENTITY", wm.vis_mod.lbl_placeholder_name.text())
        self.assertTrue(wm.vis_mod.btn_enter_retina.isVisible())

        wm.shutdown()
        self.app.processEvents()

    def test_initial_startup_cpu_synchronization(self):
        """Validates that initial startup with a CPU visualizer immediately presents the CPU canvas."""
        from toroidamp.audio.player import PlayerEngine
        from toroidamp.analysis.audio_frame import AnalysisHandoff
        from toroidamp.audio.playlist import PlaylistManager

        # Seed session with Waveform Ribbon (index 1) selected
        self.session_manager.state.selected_visualizer_idx = 1
        self.session_manager.save()

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()
        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=self.session_manager)
        wm._toggle_vis()
        self.app.processEvents()

        # VisualizerModule must immediately show CPU canvas (page 0)
        self.assertEqual(wm.vis_mod.vis_idx, 1)
        self.assertEqual(wm.vis_mod.surface_stack.currentIndex(), 0)
        self.assertIn("WAVEFORM RIBBON", wm.vis_mod.btn_switch.text())

        wm.shutdown()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
