"""
tests/test_ux_004.py — UX-004 Marquee Titles, MINI Volume & Version Cadence

Focused regression tests for:
  1-3. MarqueeLabel: static-when-fits, overflow activation, reset-on-change.
  4-5. NORMAL/MINI titles use MarqueeLabel.
  6-8. MINI volume popup: opens from speaker, no taskbar identity, changes
       authoritative volume.
  9-10. Volume sync both directions (MINI <-> NORMAL).
  11. MINI stays 460x36 regardless of popup interaction.
  12-13. Canonical version resolves to 0.2.0 and drives startup logging.
  14-15. Bump tool patch/minor calculation.
  16. Bump tool performs no Git operation.
"""

import importlib.util
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    from PySide6.QtWidgets import QApplication, QLabel
    from PySide6.QtCore import Qt
    _app = QApplication.instance() or QApplication(sys.argv)
    QT_AVAILABLE = True
except Exception:
    QT_AVAILABLE = False


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_bump_version_module():
    spec = importlib.util.spec_from_file_location("bump_version", os.path.join(REPO_ROOT, "tools", "bump_version.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Parts 1-3 — MarqueeLabel overflow / activation / reset contract
# ---------------------------------------------------------------------------

class TestMarqueeLabel(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def _make(self, width=150):
        from toroidamp.ui.marquee import MarqueeLabel
        m = MarqueeLabel()
        m.setStyleSheet("font-family: monospace; font-size: 10px;")
        m.resize(width, 20)
        m.show()
        return m

    def test_short_title_does_not_marquee(self):
        m = self._make(width=400)
        m.set_marquee_text("Short")
        self.assertEqual(m._overflow_px, 0)
        self.assertEqual(m._state, m._STATIC)
        m.close()

    def test_long_title_activates_marquee(self):
        m = self._make(width=60)
        m.set_marquee_text("A Genuinely Long Track Title That Cannot Possibly Fit")
        self.assertGreater(m._overflow_px, 0)
        self.assertNotEqual(m._state, m._STATIC)
        m.close()

    def test_marquee_resets_on_title_change(self):
        m = self._make(width=60)
        m.set_marquee_text("A Genuinely Long Track Title That Cannot Possibly Fit")
        # Simulate mid-scroll state.
        m._offset = 40.0
        m._state = m._SCROLL_FWD

        m.set_marquee_text("A Completely Different Long Track Title Also Overflowing")

        self.assertEqual(m._offset, 0.0)
        self.assertEqual(m._state, m._PAUSE_START)
        m.close()

    def test_unchanged_text_does_not_reset(self):
        m = self._make(width=60)
        m.set_marquee_text("A Genuinely Long Track Title That Cannot Possibly Fit")
        m._offset = 40.0
        m._state = m._SCROLL_FWD

        m.set_marquee_text("A Genuinely Long Track Title That Cannot Possibly Fit")

        self.assertEqual(m._offset, 40.0, "identical text must not restart the scroll")
        m.close()

    def test_text_accessor_stays_accurate(self):
        """paintEvent draws independently, but .text() must still reflect the canonical title."""
        m = self._make(width=400)
        m.set_marquee_text("♫ No Track Loaded")
        self.assertEqual(m.text(), "♫ No Track Loaded")
        m.close()

    def test_resize_reevaluates_overflow(self):
        m = self._make(width=700)
        title = "Fits At Wide Width"
        m.set_marquee_text(title)
        self.assertEqual(m._overflow_px, 0)

        m.resize(40, 20)
        self.assertGreater(m._overflow_px, 0)
        m.close()


# ---------------------------------------------------------------------------
# NORMAL Marquee Follow-up 2 — Travel Amplitude
#
# Human validation: direction/pause behavior correct, but displacement was
# too small to be useful. max_offset = overflow + end_reveal_margin, not
# just overflow — travel must clearly expose the end, not merely touch it.
# ---------------------------------------------------------------------------

class TestMarqueeTravelAmplitude(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def _make(self, width=150):
        from toroidamp.ui.marquee import MarqueeLabel
        m = MarqueeLabel()
        m.setStyleSheet("font-family: monospace; font-size: 10px;")
        m.resize(width, 20)
        m.show()
        return m

    def _run_to_full_forward_scroll(self, m, max_ticks=5000):
        m._state = m._PAUSE_START
        m._offset = 0.0
        m._tick()  # PAUSE_START -> SCROLL_FWD
        ticks = 0
        while m._state == m._SCROLL_FWD and ticks < max_ticks:
            m._tick()
            ticks += 1
        return ticks

    def test_max_offset_exceeds_raw_overflow_by_end_reveal_margin(self):
        m = self._make(width=200)
        m.set_marquee_text("A Moderately Overflowing Title For This Narrow Label")
        self.assertGreater(m._overflow_px, 0)
        self.assertEqual(m._max_offset, m._overflow_px + m.END_REVEAL_MARGIN_PX)
        m.close()

    def test_short_title_has_zero_max_offset(self):
        m = self._make(width=400)
        m.set_marquee_text("Short")
        self.assertEqual(m._max_offset, 0)
        m.close()

    def test_moderate_overflow_scrolls_past_raw_overflow(self):
        """A title that only barely overflows must still travel a meaningful distance."""
        m = self._make(width=200)
        m.set_marquee_text("A Title That Just Barely Overflows This Label Width")
        self._run_to_full_forward_scroll(m)
        self.assertEqual(m._offset, m._max_offset)
        self.assertGreaterEqual(m._offset, m._overflow_px + m.END_REVEAL_MARGIN_PX)
        m.close()

    def test_heavy_overflow_also_reaches_full_max_offset(self):
        m = self._make(width=80)
        m.set_marquee_text("A Genuinely Very Long And Heavily Overflowing Track Title For Testing Purposes")
        self._run_to_full_forward_scroll(m)
        self.assertEqual(m._offset, m._max_offset)
        m.close()

    def test_normal_and_mini_use_identical_travel_formula_for_same_title(self):
        """Same title, different available widths — both must reach overflow+margin, not merely overflow."""
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_mode("normal")
        c.show()
        _app.processEvents()
        title = "♫ Artist Name Extraordinaire — A Genuinely Long And Heavily Overflowing Track Title"
        c.update_telemetry(title, "00:00 / 03:00", 0.0, False)
        _app.processEvents()
        nm = c.normal_title_marquee
        self.assertEqual(nm._max_offset, nm._overflow_px + nm.END_REVEAL_MARGIN_PX)

        c.set_mode("mini")
        _app.processEvents()
        c.update_telemetry(title, "00:00 / 03:00", 0.0, False)
        _app.processEvents()
        mm = c.mini_title_marquee
        self.assertEqual(mm._max_offset, mm._overflow_px + mm.END_REVEAL_MARGIN_PX)
        c.close()


# ---------------------------------------------------------------------------
# Parts 4-5 — NORMAL/MINI titles use the marquee component
# ---------------------------------------------------------------------------

class TestChassisUsesMarquee(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_normal_title_is_marquee_label(self):
        from toroidamp.ui.chassis import UnifiedChassis
        from toroidamp.ui.marquee import MarqueeLabel
        c = UnifiedChassis()
        self.assertIsInstance(c.normal_title_marquee, MarqueeLabel)
        c.close()

    def test_mini_title_is_marquee_label(self):
        from toroidamp.ui.chassis import UnifiedChassis
        from toroidamp.ui.marquee import MarqueeLabel
        c = UnifiedChassis()
        self.assertIsInstance(c.mini_title_marquee, MarqueeLabel)
        c.close()

    def test_update_telemetry_drives_both_marquees(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.update_telemetry("♫ Some Track", "00:00 / 03:00", 0.0, False)
        self.assertEqual(c.normal_title_marquee.text(), "♫ Some Track")
        self.assertEqual(c.mini_title_marquee.text(), "♫ Some Track")
        c.close()


# ---------------------------------------------------------------------------
# UX-004 Follow-up — NORMAL marquee, in the real chassis LCD layout
#
# Human validation: MINI scrolled correctly, NORMAL did not. These tests
# exercise MarqueeLabel inside the actual chassis widget tree (not an
# isolated instance), through the real update_telemetry() entry point.
# ---------------------------------------------------------------------------

class TestNormalMarqueeInRealLayout(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    LONG_TITLE = "♫ Artist Name Extraordinaire — A Genuinely Long Track Title"
    SHORT_TITLE = "♫ Short"

    def _chassis(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_mode("normal")
        c.show()
        _app.processEvents()
        return c

    def test_normal_long_title_activates_marquee(self):
        c = self._chassis()
        c.update_telemetry(self.LONG_TITLE, "00:00 / 03:00", 0.0, False)
        _app.processEvents()
        nm = c.normal_title_marquee
        self.assertGreater(nm._overflow_px, 0, "a genuinely long title must overflow NORMAL's real LCD width")
        self.assertNotEqual(nm._state, nm._STATIC)
        c.close()

    def test_normal_short_title_remains_static(self):
        c = self._chassis()
        c.update_telemetry(self.SHORT_TITLE, "00:00 / 00:00", 0.0, False)
        _app.processEvents()
        nm = c.normal_title_marquee
        self.assertEqual(nm._overflow_px, 0)
        self.assertEqual(nm._state, nm._STATIC)
        c.close()

    def test_normal_marquee_resets_on_track_change(self):
        c = self._chassis()
        c.update_telemetry(self.LONG_TITLE, "00:00 / 03:00", 0.0, False)
        _app.processEvents()
        nm = c.normal_title_marquee
        nm._offset = 40.0
        nm._state = nm._SCROLL_FWD

        other_long = "♫ A Second Completely Different And Also Overflowing Title"
        c.update_telemetry(other_long, "00:00 / 02:00", 0.0, False)
        _app.processEvents()

        self.assertEqual(nm._offset, 0.0)
        self.assertEqual(nm._state, nm._PAUSE_START)
        c.close()

    def test_marquee_size_policy_does_not_grow_with_text_length(self):
        """
        Regression guard for the actual NORMAL bug: a plain QLabel's
        minimumSizeHint equals its full unwrapped text width, which can
        distort a QHBoxLayout split against sibling widgets (here, the
        time display) as the title gets longer. The marquee's allocated
        width must stay stable regardless of title length.
        """
        c = self._chassis()
        c.update_telemetry(self.SHORT_TITLE, "00:00 / 00:00", 0.0, False)
        _app.processEvents()
        width_short = c.normal_title_marquee.width()

        c.update_telemetry(self.LONG_TITLE, "00:00 / 03:00", 0.0, False)
        _app.processEvents()
        width_long = c.normal_title_marquee.width()

        self.assertEqual(width_short, width_long)
        c.close()

    def test_mini_marquee_unaffected_by_normal_fix(self):
        """MINI must keep working exactly as it did before this follow-up."""
        c = self._chassis()
        c.set_mode("mini")
        c.update_telemetry(self.LONG_TITLE, "00:00 / 03:00", 0.0, False)
        _app.processEvents()
        mm = c.mini_title_marquee
        self.assertGreater(mm._overflow_px, 0)
        self.assertNotEqual(mm._state, mm._STATIC)
        c.close()


# ---------------------------------------------------------------------------
# Parts 6-8, 11 — MINI volume popup
# ---------------------------------------------------------------------------

class TestMiniVolumePopup(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_popup_opens_from_speaker_control(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_mode("mini")
        self.assertFalse(c.volume_popup.isVisible())
        c._toggle_mini_volume_popup()
        self.assertTrue(c.volume_popup.isVisible())
        c.close()

    def test_popup_has_no_taskbar_identity(self):
        """Qt.Popup windows never register their own taskbar entry."""
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        self.assertTrue(bool(c.volume_popup.windowFlags() & Qt.Popup))
        c.close()

    def test_mini_volume_changes_authoritative_volume(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_mode("mini")
        received = []
        c.volume_changed.connect(received.append)

        c._toggle_mini_volume_popup()
        c.mini_pop_slider.setValue(42)

        self.assertIn(42 / 100.0, received)
        c.close()

    def test_mini_stays_460x36_with_popup_open(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_mode("mini")
        c._toggle_mini_volume_popup()
        self.assertEqual((c.width(), c.height()), (460, 36))
        self.assertEqual((c.width(), c.height()), (c.MINI_WIDTH, c.MINI_HEIGHT))
        c.close()


# ---------------------------------------------------------------------------
# UX-004 Follow-up — Vertical MINI volume + minimal-chrome popup
# ---------------------------------------------------------------------------

class TestMiniVolumePopupFollowUp(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_mini_volume_slider_is_vertical(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        self.assertEqual(c.mini_pop_slider.orientation(), Qt.Vertical)
        c.close()

    def test_popup_is_frameless_and_translucent(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        self.assertTrue(c.volume_popup.testAttribute(Qt.WA_TranslucentBackground))
        style = c.volume_popup.styleSheet().lower()
        self.assertIn("transparent", style)
        self.assertNotIn("background-color", style, "no opaque panel fill behind the slider")
        c.close()

    def test_popup_still_has_no_taskbar_identity(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        self.assertTrue(bool(c.volume_popup.windowFlags() & Qt.Popup))
        c.close()

    def test_popup_anchors_above_speaker_when_space_allows(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_mode("mini")
        c.move(300, 600)  # plenty of room above on a typical screen
        c.show()
        _app.processEvents()

        pos = c._compute_volume_popup_pos()
        btn_top = c.mini_vol_btn.mapToGlobal(c.mini_vol_btn.rect().topLeft())

        self.assertLessEqual(pos.y() + c.volume_popup.height(), btn_top.y() + 2, "popup bottom must sit at/above the speaker top")
        btn_center_x = btn_top.x() + c.mini_vol_btn.width() // 2
        popup_center_x = pos.x() + c.volume_popup.width() // 2
        self.assertLessEqual(abs(popup_center_x - btn_center_x), 2, "popup must be horizontally centered over the speaker")
        c.close()

    def test_popup_falls_back_below_when_no_room_above(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_mode("mini")
        c.move(300, 0)  # pinned to the top — no room above
        c.show()
        _app.processEvents()

        pos = c._compute_volume_popup_pos()
        btn_top = c.mini_vol_btn.mapToGlobal(c.mini_vol_btn.rect().topLeft())

        self.assertGreaterEqual(pos.y(), btn_top.y(), "must fall back below the speaker, not go off-screen above it")
        c.close()

    def test_popup_clamped_to_screen_horizontally(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_mode("mini")
        c.show()
        _app.processEvents()
        screen = c.screen()
        if screen is None:
            self.skipTest("no screen available in this environment")
        avail = screen.availableGeometry()

        pos = c._compute_volume_popup_pos()
        self.assertGreaterEqual(pos.x(), avail.left())
        self.assertLessEqual(pos.x() + c.volume_popup.width(), avail.right() + 1)
        c.close()


# ---------------------------------------------------------------------------
# Parts 9-10 — Volume sync both directions
# ---------------------------------------------------------------------------

class TestVolumeSync(unittest.TestCase):
    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_normal_slider_reflects_mini_change(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_mode("mini")
        c._toggle_mini_volume_popup()

        c.mini_pop_slider.setValue(33)

        self.assertEqual(c.normal_vol_slider.value(), 33)
        c.close()

    def test_mini_popup_reflects_normal_change_on_open(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_mode("mini")

        c.set_volume(0.71)  # simulates WindowManager pushing an authoritative update

        c._toggle_mini_volume_popup()
        self.assertEqual(c.mini_pop_slider.value(), 71)
        c.close()

    def test_set_volume_updates_both_views(self):
        from toroidamp.ui.chassis import UnifiedChassis
        c = UnifiedChassis()
        c.set_volume(0.5)
        self.assertEqual(c.normal_vol_slider.value(), 50)
        self.assertEqual(c.mini_pop_slider.value(), 50)
        c.close()


# ---------------------------------------------------------------------------
# Parts 12-13 — Canonical version
# ---------------------------------------------------------------------------

class TestCanonicalVersion(unittest.TestCase):
    def test_version_resolves_to_canonical_pyproject_version(self):
        import tomllib
        import toroidamp
        pyproject_path = os.path.join(REPO_ROOT, "pyproject.toml")
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        self.assertEqual(toroidamp.__version__, data["project"]["version"])

    def test_pyproject_matches_package_version(self):
        import tomllib
        import toroidamp
        pyproject_path = os.path.join(REPO_ROOT, "pyproject.toml")
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        self.assertEqual(data["project"]["version"], toroidamp.__version__)

    def test_main_module_uses_canonical_version_string(self):
        """__main__.py must not hardcode a version string in its startup log."""
        main_path = os.path.join(REPO_ROOT, "src", "toroidamp", "__main__.py")
        with open(main_path, "r", encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn('"0.1.0"', source)
        self.assertIn("__version__", source)


# ---------------------------------------------------------------------------
# Parts 14-16 — Version bump tool
# ---------------------------------------------------------------------------

class TestBumpVersionTool(unittest.TestCase):
    def setUp(self):
        self.mod = _load_bump_version_module()

    def test_patch_bump(self):
        self.assertEqual(self.mod.bump((0, 2, 0), "patch"), (0, 2, 1))
        self.assertEqual(self.mod.bump((0, 2, 9), "patch"), (0, 2, 10))

    def test_minor_bump(self):
        self.assertEqual(self.mod.bump((0, 2, 9), "minor"), (0, 3, 0))
        self.assertEqual(self.mod.bump((0, 9, 4), "minor"), (0, 10, 0))

    def test_major_bump(self):
        self.assertEqual(self.mod.bump((0, 9, 4), "major"), (1, 0, 0))

    def test_read_and_write_version_roundtrip(self):
        sample = 'name = "toroidamp"\nversion = "1.2.3"\ndescription = "x"\n'
        current = self.mod.read_version(sample)
        self.assertEqual(current, (1, 2, 3))
        new_text = self.mod.write_version(sample, (1, 2, 4))
        self.assertIn('version = "1.2.4"', new_text)
        self.assertIn('name = "toroidamp"', new_text, "unrelated lines must survive untouched")

    def test_bump_tool_performs_no_git_operation(self):
        """The tool's source must not shell out to anything — no subprocess/os.system, so it cannot invoke git."""
        tool_path = os.path.join(REPO_ROOT, "tools", "bump_version.py")
        with open(tool_path, "r", encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.system", source)
        self.assertNotIn("os.popen", source)


if __name__ == "__main__":
    unittest.main()
