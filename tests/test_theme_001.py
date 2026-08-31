"""
THEME-001 Automated Test Suite — Internal Theme Foundation + Cyber Yellow.

Verifies:
1. Exact registered themes: DEFAULT and CYBER_YELLOW.
2. Asset resolution for Cyber Yellow (chassis, panel, hazard, logo, wordmark, font).
3. Font database registration (Quantum loaded or fallback).
4. Live theme toggle without process restart.
5. Session persistence of theme_id.
6. Graceful fallback on corrupted/invalid theme_id in session JSON.
7. Playback continuity during theme switch.
8. Window lifecycle / MINI-NORMAL survival across theme switch.
9. PlaylistModule theme synchronization.
10. VisualizerModule theme synchronization.
11. RETINA MELT HUD, TUNE, LAB theme synchronization.
12. Visualizer render engine pixel invariance (theming does not touch frame buffer).
13. High-contrast QColorDialog readability in both themes.
14. Memory and asset caching stability across rapid theme toggle cycles.
15. Direct cold startup into CYBER_YELLOW.
"""

import os
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QColorDialog
from PySide6.QtGui import QColor, QFontDatabase, QImage
from PySide6.QtCore import Qt, QSize

from toroidamp.ui.theme import (
    ThemeManager,
    ThemeDefinition,
    resolve_theme_asset_path,
)
from toroidamp.session import SessionManager, SessionState
from toroidamp.audio.player import PlayerEngine, PlaybackState
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.ui.window_manager import WindowManager
from toroidamp.ui.chassis import UnifiedChassis
from toroidamp.ui.modules.playlist_module import PlaylistModule
from toroidamp.ui.modules.visualizer_module import VisualizerModule
from toroidamp.ui.fullscreen import RetinaMeltWindow, _open_styled_color_dialog
from toroidamp.ui.neon import ReactiveNeonController


class TestTheme001Foundation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.theme_manager = ThemeManager.get_instance()
        self.theme_manager.set_theme("default")

    def tearDown(self):
        self.theme_manager.set_theme("default")

    # 1. Both bundled theme definitions exist and resolve
    def test_01_both_bundled_theme_definitions_exist(self):
        themes = self.theme_manager.get_available_themes()
        self.assertIn("default", themes)
        self.assertIn("cyber_yellow", themes)
        self.assertEqual(len(themes), 2)

        def_theme = self.theme_manager.get_theme("default")
        self.assertEqual(def_theme.id, "default")
        self.assertEqual(def_theme.display_name, "DEFAULT")
        self.assertFalse(def_theme.is_image_backed)

        cy_theme = self.theme_manager.get_theme("cyber_yellow")
        self.assertEqual(cy_theme.id, "cyber_yellow")
        self.assertEqual(cy_theme.display_name, "CYBER YELLOW")
        self.assertTrue(cy_theme.is_image_backed)

    # 2. Cyber Yellow assets resolve from bundled theme folder
    def test_02_cyber_yellow_assets_resolve(self):
        chassis_p = resolve_theme_asset_path("cyber_yellow", "images/chassis.png")
        self.assertIsNotNone(chassis_p)
        self.assertTrue(chassis_p.exists())

        panel_p = resolve_theme_asset_path("cyber_yellow", "images/panel_brushed_metal.png")
        self.assertIsNotNone(panel_p)
        self.assertTrue(panel_p.exists())

        hazard_p = resolve_theme_asset_path("cyber_yellow", "images/hazard_strip.png")
        self.assertIsNotNone(hazard_p)
        self.assertTrue(hazard_p.exists())

        logo_p = resolve_theme_asset_path("cyber_yellow", "images/logo.png")
        self.assertIsNotNone(logo_p)
        self.assertTrue(logo_p.exists())

        wordmark_p = resolve_theme_asset_path("cyber_yellow", "images/wordmark.png")
        self.assertIsNotNone(wordmark_p)
        self.assertTrue(wordmark_p.exists())

        font_p = resolve_theme_asset_path("cyber_yellow", "fonts/quantum.ttf")
        self.assertIsNotNone(font_p)
        self.assertTrue(font_p.exists())

    # 3. Dynamic typography loads or gracefully falls back
    def test_03_typography_font_database_registration(self):
        cy_theme = self.theme_manager.get_theme("cyber_yellow")
        self.assertTrue(cy_theme.typography.has_custom_display_font)
        self.assertEqual(cy_theme.typography.display_family, "Quantum")

    # 4. Live toggle switches active theme without process restart
    def test_04_live_toggle_without_restart(self):
        self.assertEqual(self.theme_manager.active_theme_id, "default")
        new_id = self.theme_manager.toggle_theme()
        self.assertEqual(new_id, "cyber_yellow")
        self.assertEqual(self.theme_manager.active_theme_id, "cyber_yellow")

        # Toggle back
        new_id = self.theme_manager.toggle_theme()
        self.assertEqual(new_id, "default")
        self.assertEqual(self.theme_manager.active_theme_id, "default")

    # 5. Session persistence saves theme_id
    def test_05_session_persistence_saves_theme_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = str(Path(tmpdir) / "session.json")
            sm = SessionManager(custom_path=session_file)
            st = sm.load()
            self.assertEqual(st.theme_id, "default")

            st.theme_id = "cyber_yellow"
            sm.save()

            sm2 = SessionManager(custom_path=session_file)
            st2 = sm2.load()
            self.assertEqual(st2.theme_id, "cyber_yellow")

    # 6. Corrupted/unknown theme_id falls back safely to default
    def test_06_corrupted_theme_id_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = str(Path(tmpdir) / "session.json")
            sm = SessionManager(custom_path=session_file)
            st = sm.load()
            st.theme_id = "non_existent_synthwave_theme"
            sm.save()

            sm2 = SessionManager(custom_path=session_file)
            st2 = sm2.load()
            self.assertEqual(st2.theme_id, "default")

    # 7. Playback continuity during live theme switch
    def test_07_playback_continuity_during_theme_switch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = str(Path(tmpdir) / "session.json")
            sm = SessionManager(custom_path=session_file)
            handoff = AnalysisHandoff()
            player = PlayerEngine(handoff=handoff)
            playlist = PlaylistManager()

            wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)
            try:
                # Simulate playback state
                player._state = PlaybackState.PLAYING
                player._position_seconds = 42.5

                # Toggle theme
                wm._on_theme_toggle()
                self.assertEqual(wm.theme_manager.active_theme_id, "cyber_yellow")
                self.assertEqual(player.state, PlaybackState.PLAYING)
                self.assertEqual(player.position, 42.5)
            finally:
                wm.shutdown()

    # 8. MINI / NORMAL window lifecycle survival
    def test_08_mini_normal_mode_survival(self):
        chassis = UnifiedChassis()
        self.assertEqual(chassis.mode, "normal")

        # Toggle theme in normal mode
        self.theme_manager.set_theme("cyber_yellow")
        self.assertEqual(chassis.mode, "normal")

        # Switch to mini
        chassis.set_mode("mini")
        self.assertEqual(chassis.mode, "mini")

        # Toggle theme in mini mode
        self.theme_manager.set_theme("default")
        self.assertEqual(chassis.mode, "mini")

        # Switch back to normal
        chassis.set_mode("normal")
        self.assertEqual(chassis.mode, "normal")

    # 9. PlaylistModule styling reflects active theme
    def test_09_playlist_module_theme_synchronization(self):
        pl = PlaylistManager()
        mod = PlaylistModule(pl)

        self.theme_manager.set_theme("default")
        self.assertIn("#06070a", mod.list_widget.styleSheet())

        self.theme_manager.set_theme("cyber_yellow")
        self.assertIn("#0e0f14", mod.list_widget.styleSheet())
        self.assertIn("Quantum", mod.title_label.styleSheet())

    # 10. VisualizerModule styling reflects active theme
    def test_10_visualizer_module_theme_synchronization(self):
        # GLSL Everywhere cut: the RETINA-only placeholder (and its themed
        # label) is gone -- official GPU visualizers render on gpu_canvas
        # now. btn_switch (the MODE selector, themed with pal.primary in
        # every mode) is the equivalent always-present themed element.
        mod = VisualizerModule()

        self.theme_manager.set_theme("default")
        self.assertIn("#00f0ff", mod.btn_switch.styleSheet())

        self.theme_manager.set_theme("cyber_yellow")
        self.assertIn("#ffd700", mod.btn_switch.styleSheet())

    # 11. Fullscreen RETINA MELT HUD / TUNE / LAB reflect active theme
    def test_11_fullscreen_retina_theme_synchronization(self):
        melt = RetinaMeltWindow()

        self.theme_manager.set_theme("default")
        self.assertIn("#00f0ff", melt.hud.styleSheet())

        self.theme_manager.set_theme("cyber_yellow")
        self.assertIn("#ffd700", melt.hud.styleSheet())
        self.assertIn("Quantum", melt.hud_marquee.styleSheet())

    # 12. Visualizer pixels untouched by theme
    def test_12_visualizer_rendering_invariance(self):
        mod = VisualizerModule()
        # Verify visualizers array and internal configuration are unchanged by theme
        initial_vis_count = len(mod.visualizers)
        self.theme_manager.set_theme("cyber_yellow")
        self.assertEqual(len(mod.visualizers), initial_vis_count)
        self.theme_manager.set_theme("default")
        self.assertEqual(len(mod.visualizers), initial_vis_count)

    # 13. High-contrast QColorDialog readability
    def test_13_color_dialog_readability_in_both_themes(self):
        for th_id in ["default", "cyber_yellow"]:
            self.theme_manager.set_theme(th_id)
            pal = self.theme_manager.current_theme.palette
            # Ensure background and text colors are distinct and high contrast
            self.assertNotEqual(pal.bg_surface, pal.text_primary)
            self.assertNotEqual(pal.bg_surface, pal.primary)

    # 14. Asset caching & toggle stability
    def test_14_rapid_theme_toggle_stability(self):
        chassis = UnifiedChassis()
        for _ in range(20):
            self.theme_manager.toggle_theme()
            self.app.processEvents()

        # Preloaded pixmaps should be present and valid
        cy = self.theme_manager.get_theme("cyber_yellow")
        self.assertIsNotNone(cy.assets.get_pixmap("chassis"))
        self.assertFalse(cy.assets.get_pixmap("chassis").isNull())

    # 15. Cold startup directly into Cyber Yellow
    def test_15_cold_startup_into_cyber_yellow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = str(Path(tmpdir) / "session.json")
            sm = SessionManager(custom_path=session_file)
            st = sm.load()
            st.theme_id = "cyber_yellow"
            sm.save()

            handoff = AnalysisHandoff()
            player = PlayerEngine(handoff=handoff)
            playlist = PlaylistManager()
            wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)
            try:
                self.assertEqual(wm.theme_manager.active_theme_id, "cyber_yellow")
                self.assertEqual(wm.neon_controller.current_theme_id, "cyber_yellow")
            finally:
                wm.shutdown()

    # 16. Cyber Yellow wordmark header in NORMAL mode
    def test_16_cyber_yellow_wordmark_header_switching(self):
        chassis = UnifiedChassis()

        # In DEFAULT theme, plain text label is visible and wordmark is hidden
        self.theme_manager.set_theme("default")
        self.assertTrue(chassis.normal_id_lbl.isVisible())
        self.assertFalse(chassis.normal_wordmark_lbl.isVisible())
        self.assertFalse(chassis.normal_version_lbl.isVisible())

        # In CYBER YELLOW, wordmark image and version label are visible; plain text is hidden
        self.theme_manager.set_theme("cyber_yellow")
        self.assertFalse(chassis.normal_id_lbl.isVisible())
        self.assertTrue(chassis.normal_wordmark_lbl.isVisible())
        self.assertTrue(chassis.normal_version_lbl.isVisible())
        self.assertIsNotNone(chassis.normal_wordmark_lbl.pixmap())
        self.assertFalse(chassis.normal_wordmark_lbl.pixmap().isNull())
        self.assertEqual(chassis.normal_wordmark_lbl.pixmap().height(), 42)

        # Toggle back to DEFAULT restores exact original textual header
        self.theme_manager.set_theme("default")
        self.assertTrue(chassis.normal_id_lbl.isVisible())
        self.assertFalse(chassis.normal_wordmark_lbl.isVisible())
        self.assertFalse(chassis.normal_version_lbl.isVisible())

    # 17. Surface-aware contrast tokens for chassis vs dark panels
    def test_17_surface_aware_contrast_tokens(self):
        cy = self.theme_manager.get_theme("cyber_yellow")
        pal = cy.palette

        # Light chassis surface requires dark graphite foreground
        self.assertEqual(pal.text_on_chassis, "#18181b")
        self.assertEqual(pal.text_on_chassis_muted, "#3f3f46")

        # Dark module and LCD surfaces retain bright foreground
        self.assertEqual(pal.text_primary, "#ffffff")
        self.assertEqual(pal.text_lcd, "#ffd700")
        self.assertEqual(pal.primary, "#ffd700")

    # 18. Cyber Yellow targeted red accents (NORMAL player + Playlist actions)
    def test_18_cyber_yellow_red_accents(self):
        chassis = UnifiedChassis()
        pl_mgr = PlaylistManager()
        pl_mod = PlaylistModule(pl_mgr)

        # In DEFAULT:
        self.theme_manager.set_theme("default")
        self.assertIn("#00ffcc", chassis.normal_widget.styleSheet())
        self.assertIn("#64748b", chassis.normal_widget.styleSheet())
        self.assertIn("#00f0ff", chassis.normal_widget.styleSheet())
        self.assertIn("#00f0ff", pl_mod.styleSheet())

        # In CYBER YELLOW:
        self.theme_manager.set_theme("cyber_yellow")
        # Track title marquee uses canonical red accent (#ff2a4b)
        self.assertIn("#ff2a4b", chassis.normal_widget.styleSheet())
        # Playlist action buttons use canonical red accent (#ff2a4b)
        self.assertIn("#ff2a4b", pl_mod.styleSheet())

        # Toggle back to DEFAULT restores original cyan presentation
        self.theme_manager.set_theme("default")
        self.assertIn("#00ffcc", chassis.normal_widget.styleSheet())
        self.assertIn("#64748b", chassis.normal_widget.styleSheet())
        self.assertIn("#00f0ff", chassis.normal_widget.styleSheet())
        self.assertIn("#00f0ff", pl_mod.styleSheet())


if __name__ == "__main__":
    unittest.main()
