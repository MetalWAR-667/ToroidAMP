"""
tests/test_brand_001.py — BRAND-001 Application Icon Identity

Focused regression tests for:
  1. branding master exists/resolves.
  2. runtime icon resolution does not depend on the current working directory.
  3. QApplication receives a non-null QIcon when the asset exists.
  4. tray uses the official branding icon.
  5. missing icon fails gracefully (warning, never fatal).
  6. owned module/taskbar architecture remains unchanged.
  7. the generated .ico contains the expected multiresolution sizes.
  8. source artwork is not modified by generation/integration.

AUTHORITATIVE DISTINCTION under test:
  CREATIVE SOURCE (assets/images/ToroidAMP.png) != RUNTIME BRANDING ASSET
  (assets/branding/toroidamp_icon.png).
"""

import hashlib
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    _app = QApplication.instance() or QApplication(sys.argv)
    QT_AVAILABLE = True
except Exception:
    QT_AVAILABLE = False

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BRANDING_MASTER = os.path.join(REPO_ROOT, "assets", "branding", "toroidamp_icon.png")
CREATIVE_SOURCE = os.path.join(REPO_ROOT, "assets", "images", "ToroidAMP.png")
BRANDING_ICO = os.path.join(REPO_ROOT, "assets", "branding", "toroidamp.ico")
PACKAGE_BRANDING_MASTER = os.path.join(REPO_ROOT, "src", "toroidamp", "assets", "branding", "toroidamp_icon.png")


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ---------------------------------------------------------------------------
# Part 1 — Branding master exists/resolves
# ---------------------------------------------------------------------------

class TestBrandingAssetsExist(unittest.TestCase):
    def test_branding_master_exists(self):
        self.assertTrue(os.path.isfile(BRANDING_MASTER), f"Missing: {BRANDING_MASTER}")

    def test_creative_source_exists(self):
        self.assertTrue(os.path.isfile(CREATIVE_SOURCE), f"Missing: {CREATIVE_SOURCE}")

    def test_package_internal_copy_matches_authoritative_master(self):
        """The packaged runtime copy must be byte-identical to the human-facing master."""
        self.assertTrue(os.path.isfile(PACKAGE_BRANDING_MASTER))
        self.assertEqual(_sha256(BRANDING_MASTER), _sha256(PACKAGE_BRANDING_MASTER))


# ---------------------------------------------------------------------------
# Part 2 — CWD-independent resolution
# ---------------------------------------------------------------------------

class TestCwdIndependentResolution(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_resolution_independent_of_cwd(self):
        from toroidamp.branding import resolve_branding_icon_path
        original_cwd = os.getcwd()
        try:
            os.chdir(os.path.expanduser("~"))
            resolved = resolve_branding_icon_path()
            self.assertIsNotNone(resolved)
            self.assertTrue(resolved.is_file())
        finally:
            os.chdir(original_cwd)

    def test_resolution_does_not_use_relative_traversal_from_cwd(self):
        """Resolution must be anchored to the module/package location, not '.'-relative."""
        from toroidamp.branding import resolve_branding_icon_path
        resolved = resolve_branding_icon_path()
        self.assertTrue(resolved.is_absolute())


# ---------------------------------------------------------------------------
# Part 3 — QApplication / QIcon
# ---------------------------------------------------------------------------

class TestQIconResolution(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_resolve_branding_icon_returns_non_null_qicon(self):
        from toroidamp.branding import resolve_branding_icon
        icon = resolve_branding_icon()
        self.assertIsNotNone(icon)
        self.assertFalse(icon.isNull())

    def test_application_can_receive_the_icon(self):
        from toroidamp.branding import resolve_branding_icon
        icon = resolve_branding_icon()
        _app.setWindowIcon(icon)
        self.assertFalse(_app.windowIcon().isNull())

    def test_chassis_carries_non_null_icon(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        self.assertFalse(c.windowIcon().isNull())
        c.close()


# ---------------------------------------------------------------------------
# Part 4 — Tray uses the official branding icon
# ---------------------------------------------------------------------------

class TestTrayBranding(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_tray_icon_is_non_null(self):
        from toroidamp.ui.tray import ToroidTrayIcon
        tray = ToroidTrayIcon()
        self.assertFalse(tray.icon().isNull())
        tray.hide()

    def test_tray_prefers_official_icon_over_procedural(self):
        """When the branding asset resolves, the tray must not fall back to the procedural design."""
        import toroidamp.ui.tray as tray_module
        from toroidamp.branding import resolve_branding_icon

        official = resolve_branding_icon()
        self.assertIsNotNone(official, "this test requires the branding asset to be present")

        procedural_called = []
        original = tray_module.ToroidTrayIcon._create_procedural_icon
        tray_module.ToroidTrayIcon._create_procedural_icon = staticmethod(
            lambda: (procedural_called.append(True), original())[1]
        )
        try:
            tray = tray_module.ToroidTrayIcon()
            tray.hide()
        finally:
            tray_module.ToroidTrayIcon._create_procedural_icon = staticmethod(original)

        self.assertEqual(procedural_called, [], "procedural fallback must not run when the official icon resolves")


# ---------------------------------------------------------------------------
# Part 5 — Missing icon fails gracefully
# ---------------------------------------------------------------------------

class TestMissingIconFallback(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_resolve_branding_icon_returns_none_when_unresolvable(self):
        import toroidamp.branding as branding
        original = branding.resolve_branding_icon_path
        branding.resolve_branding_icon_path = lambda: None
        try:
            self.assertIsNone(branding.resolve_branding_icon())
        finally:
            branding.resolve_branding_icon_path = original

    def test_tray_falls_back_to_procedural_icon_when_branding_missing(self):
        import toroidamp.ui.tray as tray_module
        original = tray_module.resolve_branding_icon
        tray_module.resolve_branding_icon = lambda: None
        try:
            tray = tray_module.ToroidTrayIcon()
            self.assertFalse(tray.icon().isNull(), "must still get a usable icon via the procedural fallback")
            tray.hide()
        finally:
            tray_module.resolve_branding_icon = original

    def test_chassis_construction_does_not_raise_when_branding_missing(self):
        """A missing/unreadable branding asset must never prevent the chassis (or startup) from constructing."""
        import toroidamp.ui.chassis as chassis_module
        original = chassis_module.resolve_branding_icon
        chassis_module.resolve_branding_icon = lambda: None
        try:
            c = chassis_module.UnifiedChassis()
            c.close()
        finally:
            chassis_module.resolve_branding_icon = original


# ---------------------------------------------------------------------------
# Part 6 — Owned module / taskbar architecture unchanged
# ---------------------------------------------------------------------------

class TestTaskbarOwnershipUnaffected(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_modules_remain_owned_windows_of_chassis(self):
        import tempfile
        from toroidamp.analysis.audio_frame import AnalysisHandoff
        from toroidamp.audio.player import PlayerEngine
        from toroidamp.audio.playlist import PlaylistManager
        from toroidamp.session import SessionManager
        from toroidamp.ui.window_manager import WindowManager

        with tempfile.TemporaryDirectory() as td:
            sm = SessionManager(custom_path=os.path.join(td, "session.json"))
            handoff = AnalysisHandoff(2048)
            player = PlayerEngine(handoff=handoff)
            playlist = PlaylistManager()
            wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)

            self.assertTrue(bool(wm.vis_mod.windowFlags() & Qt.Window))
            self.assertTrue(bool(wm.pl_mod.windowFlags() & Qt.Window))
            self.assertIs(wm.vis_mod.parentWidget(), wm.chassis)
            self.assertIs(wm.pl_mod.parentWidget(), wm.chassis)
            wm.shutdown()


# ---------------------------------------------------------------------------
# BRAND-001 Follow-up — Tray Restore Semantics
#
# Human validation: tray "Restore Player" only raised/focused the chassis —
# it never actually left MINI. Restore Player must now perform MINI->NORMAL
# via the existing authoritative chassis.set_mode() transition (the same
# path the chassis's own ▲ NORMAL button uses), then raise/focus.
# ---------------------------------------------------------------------------

class TestTrayRestoreSemantics(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def _wm(self):
        import tempfile
        from toroidamp.analysis.audio_frame import AnalysisHandoff
        from toroidamp.audio.player import PlayerEngine
        from toroidamp.audio.playlist import PlaylistManager
        from toroidamp.session import SessionManager
        from toroidamp.ui.window_manager import WindowManager

        td = tempfile.mkdtemp()
        sm = SessionManager(custom_path=os.path.join(td, "session.json"))
        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()
        return WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)

    def test_restore_from_mini_switches_to_normal(self):
        wm = self._wm()
        wm.chassis.set_mode("mini")
        self.assertEqual(wm.chassis.mode, "mini")

        wm._focus_chassis()

        self.assertEqual(wm.chassis.mode, "normal")
        wm.shutdown()

    def test_restore_while_already_normal_stays_normal(self):
        wm = self._wm()
        self.assertEqual(wm.chassis.mode, "normal")

        wm._focus_chassis()

        self.assertEqual(wm.chassis.mode, "normal")
        wm.shutdown()

    def test_restore_from_mini_restores_previously_active_modules(self):
        wm = self._wm()
        wm._toggle_vis()
        wm._toggle_pl()
        wm.undock_module(wm.vis_mod)
        wm.vis_mod.resize(680, 400)
        wm.undock_module(wm.pl_mod)
        wm.pl_mod.resize(340, 500)

        wm.chassis.set_mode("mini")
        self.assertFalse(wm.vis_mod.isVisible())
        self.assertFalse(wm.pl_mod.isVisible())

        wm._focus_chassis()

        self.assertTrue(wm.vis_mod.isVisible())
        self.assertTrue(wm.pl_mod.isVisible())
        # USER SIZE IS STATE — restoring through tray must not reset geometry.
        self.assertEqual((wm.vis_mod.width(), wm.vis_mod.height()), (680, 400))
        self.assertEqual((wm.pl_mod.width(), wm.pl_mod.height()), (340, 500))
        wm.shutdown()

    def test_restore_does_not_disturb_playback(self):
        from toroidamp.audio.player import PlaybackState
        wm = self._wm()
        mp3_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "audio", "Burn The World Waltz.mp3"))
        if os.path.exists(mp3_path):
            wm.playlist.add_file(mp3_path, "Burn The World Waltz", 200.0)
        wm._play_index(0)
        was_playing = wm.player_engine.state == PlaybackState.PLAYING

        wm.chassis.set_mode("mini")
        wm._focus_chassis()

        self.assertEqual(wm.player_engine.state == PlaybackState.PLAYING, was_playing)
        wm.shutdown()

    def test_restore_still_raises_and_activates_chassis(self):
        wm = self._wm()
        raise_calls = []
        activate_calls = []
        wm.chassis.raise_ = lambda: raise_calls.append(True)
        wm.chassis.activateWindow = lambda: activate_calls.append(True)

        wm.chassis.set_mode("mini")
        wm._focus_chassis()

        self.assertEqual(raise_calls, [True])
        self.assertEqual(activate_calls, [True])
        wm.shutdown()

    def test_restore_does_not_regress_minimize_or_close(self):
        """MINI button semantics, minimize routing, and shutdown must be untouched by this fix."""
        from toroidamp.audio.player import PlaybackState
        wm = self._wm()
        wm._play_index(0) if len(wm.playlist) else None

        # MINIMIZE (-) still routes NORMAL -> MINI, unaffected by tray Restore changes.
        wm.chassis.minimize_requested.emit()
        self.assertEqual(wm.chassis.mode, "mini")

        # Tray Restore still correctly reverses it.
        wm._focus_chassis()
        self.assertEqual(wm.chassis.mode, "normal")

        # Close lifecycle unaffected.
        wm.chassis.close_requested.emit()
        self.assertEqual(wm.player_engine.state, PlaybackState.STOPPED)


# ---------------------------------------------------------------------------
# Part 7 — Windows ICO multiresolution
# ---------------------------------------------------------------------------

class TestWindowsIco(unittest.TestCase):
    def test_ico_exists(self):
        self.assertTrue(os.path.isfile(BRANDING_ICO), f"Missing: {BRANDING_ICO}")

    def test_ico_contains_expected_sizes(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not available in this environment — cannot inspect .ico contents")

        im = Image.open(BRANDING_ICO)
        sizes = im.info.get("sizes", set())
        expected = {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}
        self.assertTrue(expected.issubset(set(sizes)), f"Missing sizes: {expected - set(sizes)}")

    def test_package_internal_ico_matches_authoritative_ico(self):
        package_ico = os.path.join(REPO_ROOT, "src", "toroidamp", "assets", "branding", "toroidamp.ico")
        if not os.path.isfile(package_ico):
            self.skipTest("packaged .ico copy not present")
        self.assertEqual(_sha256(BRANDING_ICO), _sha256(package_ico))


# ---------------------------------------------------------------------------
# Part 8 — Source artwork untouched
# ---------------------------------------------------------------------------

class TestSourceArtworkUntouched(unittest.TestCase):
    def test_creative_source_matches_test_fixture_original(self):
        """
        The creative source in assets/images/ must be byte-identical to the
        original the human placed under tests/assets/images/ — proving no
        resize/re-encode/modification happened during integration.
        """
        fixture = os.path.join(REPO_ROOT, "tests", "assets", "images", "toroidAMP.png")
        if not os.path.isfile(fixture):
            self.skipTest("original test fixture no longer present to compare against")
        self.assertEqual(_sha256(fixture), _sha256(CREATIVE_SOURCE))

    def test_branding_master_matches_test_fixture_original(self):
        fixture = os.path.join(REPO_ROOT, "tests", "assets", "branding", "toroidamp_icon.png")
        if not os.path.isfile(fixture):
            self.skipTest("original test fixture no longer present to compare against")
        self.assertEqual(_sha256(fixture), _sha256(BRANDING_MASTER))


if __name__ == "__main__":
    unittest.main()
