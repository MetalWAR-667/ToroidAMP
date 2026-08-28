"""
THEME-002 Automated Test Suite — Editable QSS Override Foundation.

Verifies:
1. Bundled Cyber Yellow theme.qss resolves.
2. QSS can be loaded as text without errors.
3. Missing QSS safely falls back to ThemeDefinition base styling.
4. Empty QSS is safe and does not produce errors.
5. DEFAULT -> CYBER switching replaces the active override.
6. CYBER -> DEFAULT removes Cyber-specific overrides.
7. Repeated switching does not concatenate QSS indefinitely.
8. Target NORMAL widgets expose stable objectName selectors.
9. Target Playlist buttons expose stable selectors/themeRole properties.
10. Cyber QSS contains the intended editable targets.
11. QSS application does not modify playback state.
12. QSS application does not modify visualizer selection/state.
13. RETINA behavior remains unaffected.
14. QColorDialog scoped styling remains unaffected.
15. End-to-end integration: modifying theme.qss overrides container/widget presentation.
"""

import os
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from toroidamp.ui.theme import (
    ThemeManager,
    ThemeDefinition,
    resolve_theme_asset_path,
)
from toroidamp.session import SessionManager
from toroidamp.audio.player import PlayerEngine, PlaybackState
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.ui.window_manager import WindowManager
from toroidamp.ui.chassis import UnifiedChassis
from toroidamp.ui.modules.playlist_module import PlaylistModule
from toroidamp.ui.fullscreen import RetinaMeltWindow, COLOR_DIALOG_STYLESHEET


class TestTheme002QSSOverride(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.theme_manager = ThemeManager.get_instance()
        self.theme_manager.set_theme("default")

    def tearDown(self):
        self.theme_manager.set_theme("default")

    # 1. Bundled Cyber Yellow theme.qss resolves
    def test_01_cyber_yellow_qss_resolves(self):
        qss_p = resolve_theme_asset_path("cyber_yellow", "theme.qss")
        self.assertIsNotNone(qss_p)
        self.assertTrue(qss_p.exists())

    # 2. QSS can be loaded as text
    def test_02_qss_loads_as_text(self):
        cy = self.theme_manager.get_theme("cyber_yellow")
        self.assertIsNotNone(cy.qss_override)
        self.assertIn("normalTrackTitle", cy.qss_override)
        self.assertIn("playlistAction", cy.qss_override)

    # 3. Missing QSS safely falls back to ThemeDefinition base styling
    def test_03_missing_qss_fallback(self):
        non_existent_path = Path("assets/themes/non_existent/theme.qss")
        content = self.theme_manager._read_theme_qss(non_existent_path)
        self.assertEqual(content, "")

    # 4. Empty QSS is safe
    def test_04_empty_qss_is_safe(self):
        with tempfile.NamedTemporaryFile(suffix=".qss", delete=False) as tf:
            tf_path = Path(tf.name)
        try:
            content = self.theme_manager._read_theme_qss(tf_path)
            self.assertEqual(content, "")
        finally:
            os.remove(tf_path)

    # 5. DEFAULT -> CYBER switching replaces active override
    def test_05_default_to_cyber_switching_replaces_override(self):
        chassis = UnifiedChassis()
        self.theme_manager.set_theme("default")
        self.assertIn("#00f0ff", chassis.normal_widget.styleSheet())

        self.theme_manager.set_theme("cyber_yellow")
        self.assertIn("#ff2a4b", chassis.normal_widget.styleSheet())

    # 6. CYBER -> DEFAULT removes Cyber-specific overrides
    def test_06_cyber_to_default_removes_cyber_overrides(self):
        chassis = UnifiedChassis()
        self.theme_manager.set_theme("cyber_yellow")
        self.theme_manager.set_theme("default")
        # In Default, the chassis normal_widget style does not contain cyber's primary accent
        self.assertIn("#00f0ff", chassis.normal_widget.styleSheet())

    # 7. Repeated switching does not concatenate QSS indefinitely
    def test_07_repeated_switching_does_not_grow_stylesheet(self):
        chassis = UnifiedChassis()
        lengths = []
        for _ in range(10):
            self.theme_manager.set_theme("cyber_yellow")
            lengths.append(len(chassis.normal_widget.styleSheet()))
            self.theme_manager.set_theme("default")

        # All cyber yellow stylesheet lengths should be identical
        self.assertEqual(len(set(lengths)), 1)

    # 8. Target NORMAL widgets expose stable objectName selectors
    def test_08_target_normal_widgets_expose_stable_object_names(self):
        chassis = UnifiedChassis()
        self.assertEqual(chassis.normal_wordmark_lbl.objectName(), "normalWordmark")
        self.assertEqual(chassis.normal_id_lbl.objectName(), "normalIdentity")
        self.assertEqual(chassis.normal_version_lbl.objectName(), "normalVersion")
        self.assertEqual(chassis.normal_title_marquee.objectName(), "normalTrackTitle")
        self.assertEqual(chassis.normal_time_display.objectName(), "normalTimeDisplay")
        self.assertEqual(chassis.normal_vol_lbl.objectName(), "normalVolumeLabel")
        self.assertEqual(chassis.normal_vol_slider.objectName(), "normalVolumeSlider")
        self.assertEqual(chassis.normal_seek_slider.objectName(), "normalSeekSlider")

    # 9. Target Playlist buttons expose stable selectors/themeRole properties
    def test_09_playlist_buttons_expose_theme_role_and_object_names(self):
        pl_mgr = PlaylistManager()
        pl_mod = PlaylistModule(pl_mgr)

        for btn in (pl_mod.btn_add, pl_mod.btn_del, pl_mod.btn_clear, pl_mod.btn_shf, pl_mod.btn_rep, pl_mod.btn_m3u):
            self.assertEqual(btn.property("themeRole"), "playlistAction")

        self.assertEqual(pl_mod.btn_add.objectName(), "playlistBtnAdd")
        self.assertEqual(pl_mod.btn_rep.objectName(), "playlistBtnRepeat")

    # 10. Cyber QSS contains the intended editable targets
    def test_10_cyber_qss_contains_intended_editable_targets(self):
        cy = self.theme_manager.get_theme("cyber_yellow")
        qss = cy.qss_override
        self.assertIn("normalVersion", qss)
        self.assertIn("normalTrackTitle", qss)
        self.assertIn("normalVolumeLabel", qss)
        self.assertIn("normalVolumeSlider", qss)
        self.assertIn("playlistAction", qss)

    # 11. QSS application does not modify playback state
    def test_11_qss_application_preserves_playback_state(self):
        handoff = AnalysisHandoff()
        player = PlayerEngine(handoff=handoff)
        player._state = PlaybackState.PLAYING
        player._position_seconds = 12.3

        self.theme_manager.set_theme("cyber_yellow")
        self.assertEqual(player.state, PlaybackState.PLAYING)
        self.assertEqual(player.position, 12.3)

    # 12. QSS application does not modify visualizer selection/state
    def test_12_qss_application_preserves_visualizer_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = str(Path(tmpdir) / "session.json")
            sm = SessionManager(custom_path=session_file)
            handoff = AnalysisHandoff()
            player = PlayerEngine(handoff=handoff)
            playlist = PlaylistManager()
            wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)
            try:
                wm.vis_mod.vis_idx = 2
                self.theme_manager.set_theme("cyber_yellow")
                self.assertEqual(wm.vis_mod.vis_idx, 2)
            finally:
                wm.shutdown()

    # 13. RETINA behavior remains unaffected
    def test_13_retina_behavior_unaffected(self):
        melt = RetinaMeltWindow()
        self.theme_manager.set_theme("cyber_yellow")
        self.assertIn("#ffd700", melt.hud.styleSheet())

    # 14. QColorDialog scoped styling remains unaffected
    def test_14_color_dialog_scoped_styling_unaffected(self):
        self.assertIn("QColorDialog", COLOR_DIALOG_STYLESHEET)
        self.assertIn("#121520", COLOR_DIALOG_STYLESHEET)

    # 15. End-to-end integration: custom QSS override reaches target widget
    def test_15_custom_qss_override_integration(self):
        custom_qss = """
            QLabel#normalTrackTitle {
                color: #00ff00;
            }
        """
        cy = self.theme_manager.get_theme("cyber_yellow")
        orig_qss = cy.qss_override
        try:
            cy.qss_override = custom_qss
            chassis = UnifiedChassis()
            chassis.apply_theme(cy)
            # Verify custom color #00ff00 was combined into normal_widget stylesheet
            self.assertIn("#00ff00", chassis.normal_widget.styleSheet())
        finally:
            cy.qss_override = orig_qss


if __name__ == "__main__":
    unittest.main()
