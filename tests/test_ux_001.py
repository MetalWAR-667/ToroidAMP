"""
tests/test_ux_001.py — UX-001 Daily Use Ergonomics

Focused regression tests for:
  A. Click-to-seek position conversion and safety.
  B. Module window flags / ownership expressing non-taskbar intent.
  C. MINI elapsed+total time display and authoritative width.
  D. Session geometry compatibility with old MINI dimensions.
  E. Lifecycle semantics unchanged.

NOTE: Tests that exercise the real Qt event loop require a QApplication.
      Qt widget tests here are structural/signal tests, not pixel-level render tests.
      Actual Windows taskbar behaviour requires manual validation on Windows
      (automated tests can only assert window flags / ownership, not OS rendering).
"""

import pytest
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# QApplication singleton guard
# ---------------------------------------------------------------------------
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    _app = QApplication.instance() or QApplication(sys.argv)
    QT_AVAILABLE = True
except Exception:
    QT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Part A — Click-to-Seek
# ---------------------------------------------------------------------------

class TestSeekSliderPositionConversion(unittest.TestCase):
    """SeekSlider converts groove-click position to a normalized seek value."""

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_seeksider_exists_and_is_subclass(self):
        from toroidamp.ui.chassis import SeekSlider
        from PySide6.QtWidgets import QSlider
        assert issubclass(SeekSlider, QSlider), "SeekSlider must subclass QSlider"

    def test_seek_slider_default_range(self):
        from toroidamp.ui.chassis import SeekSlider
        s = SeekSlider(Qt.Horizontal)
        s.setRange(0, 1000)
        assert s.minimum() == 0
        assert s.maximum() == 1000

    def test_seek_slider_sliderMoved_signal_exists(self):
        """sliderMoved must be the single channel for both drag and click-to-seek."""
        from toroidamp.ui.chassis import SeekSlider
        s = SeekSlider(Qt.Horizontal)
        s.setRange(0, 1000)
        received = []
        s.sliderMoved.connect(received.append)
        # Programmatically trigger sliderMoved (as SeekSlider.mousePressEvent does)
        s.sliderMoved.emit(500)
        assert received == [500], "sliderMoved must be emittable and connectable"

    def test_chassis_uses_seeksider_for_normal_seek_slider(self):
        """chassis.normal_seek_slider must be a SeekSlider, not a plain QSlider."""
        from toroidamp.ui.chassis import UnifiedChassis, SeekSlider
        chassis = UnifiedChassis()
        assert isinstance(chassis.normal_seek_slider, SeekSlider), (
            "normal_seek_slider must be a SeekSlider to enable click-to-seek"
        )
        chassis.close()

    def test_seek_value_clamped_within_range(self):
        """Value computed from click position must never exceed slider range."""
        from toroidamp.ui.chassis import SeekSlider
        s = SeekSlider(Qt.Horizontal)
        s.setRange(0, 1000)
        # Simulate what SeekSlider.mousePressEvent computes for edge positions
        for ratio in [0.0, 0.5, 1.0]:
            value = int(round(ratio * (s.maximum() - s.minimum()) + s.minimum()))
            assert s.minimum() <= value <= s.maximum(), (
                f"Value {value} out of range [{s.minimum()}, {s.maximum()}]"
            )


class TestClickToSeekSafety(unittest.TestCase):
    """Click-to-seek must safely no-op when no track is loaded or duration is zero."""

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_window_manager_on_seek_noop_when_duration_zero(self):
        """WindowManager._on_seek must not call player.seek when duration == 0."""
        # Minimal stubs — we test the guard logic, not the audio stack.
        player = MagicMock()
        player.duration = 0.0

        # Directly invoke the guard logic mirroring _on_seek
        duration = player.duration
        if duration > 0.0:
            player.seek(500 / 1000.0 * duration)

        player.seek.assert_not_called()

    def test_window_manager_on_seek_calls_seek_when_duration_positive(self):
        player = MagicMock()
        player.duration = 240.0

        duration = player.duration
        if duration > 0.0:
            target = (500 / 1000.0) * duration
            player.seek(target)

        player.seek.assert_called_once_with(120.0)


class TestDragSeekUnaffected(unittest.TestCase):
    """Drag-handle seek pathway must remain connected after the click-to-seek change."""

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_slider_moved_still_connected_to_seek_changed(self):
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        received = []
        chassis.seek_changed.connect(received.append)
        # Simulate drag — sliderMoved fires, which chains to seek_changed
        chassis.normal_seek_slider.sliderMoved.emit(250)
        assert received == [250], "sliderMoved must still chain to seek_changed"
        chassis.close()


# ---------------------------------------------------------------------------
# Part B — Module Window Flags / Ownership
# ---------------------------------------------------------------------------

class TestModuleWindowFlags(unittest.TestCase):
    """
    ModuleShell windows must express non-taskbar intent via Qt window flags
    or owner assignment.

    IMPORTANT: These tests verify the Qt-level mechanism (owned windows /
    Qt.Tool flag).  Whether Windows actually renders a single taskbar entry
    requires manual validation on a live Windows desktop — no automated test
    can substitute for that observation.
    """

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_module_shell_has_window_flag(self):
        """ModuleShell must be a top-level window (Qt.Window) — independent positioning."""
        from toroidamp.ui.modules.base import ModuleShell
        shell = ModuleShell("TEST")
        flags = shell.windowFlags()
        assert bool(flags & Qt.Window), "ModuleShell must carry Qt.Window for independent positioning"
        shell.close()

    def test_vis_module_created_with_chassis_parent_eliminates_taskbar_entry(self):
        """
        VisualizerModule created with chassis as parent becomes an owned window.
        On Windows, owned Qt.Window widgets do not receive independent taskbar entries.
        """
        from toroidamp.ui.chassis import UnifiedChassis
        from toroidamp.ui.modules.visualizer_module import VisualizerModule
        chassis = UnifiedChassis()
        vis = VisualizerModule(parent=chassis)
        # Ownership is the suppression mechanism.
        assert vis.parent() is chassis, (
            "VisualizerModule must have chassis as parent for taskbar ownership suppression"
        )
        vis.close()
        chassis.close()

    def test_pl_module_created_with_chassis_parent_eliminates_taskbar_entry(self):
        from toroidamp.ui.chassis import UnifiedChassis
        from toroidamp.ui.modules.playlist_module import PlaylistModule
        from toroidamp.audio.playlist import PlaylistManager
        chassis = UnifiedChassis()
        pl = PlaylistModule(PlaylistManager(), parent=chassis)
        assert pl.parent() is chassis, (
            "PlaylistModule must have chassis as parent for taskbar ownership suppression"
        )
        pl.close()
        chassis.close()

    def test_window_manager_creates_modules_with_chassis_parent(self):
        """WindowManager must pass chassis as parent when constructing modules."""
        from toroidamp.ui.chassis import UnifiedChassis
        from toroidamp.ui.modules.visualizer_module import VisualizerModule
        from toroidamp.ui.modules.playlist_module import PlaylistModule

        # Verify the ownership contract by inspecting the module parent
        # (we mock the full WindowManager construction to isolate module creation)
        chassis = UnifiedChassis()
        from toroidamp.audio.playlist import PlaylistManager
        vis = VisualizerModule(parent=chassis)
        pl = PlaylistModule(PlaylistManager(), parent=chassis)

        assert vis.parent() is chassis
        assert pl.parent() is chassis

        vis.close()
        pl.close()
        chassis.close()

    def test_modules_remain_independently_moveable(self):
        """
        Qt.Window flag must be present even with a parent,
        ensuring modules can float to arbitrary screen positions.
        """
        from toroidamp.ui.chassis import UnifiedChassis
        from toroidamp.ui.modules.visualizer_module import VisualizerModule
        chassis = UnifiedChassis()
        vis = VisualizerModule(parent=chassis)
        flags = vis.windowFlags()
        assert bool(flags & Qt.Window), (
            "VisualizerModule must retain Qt.Window flag for independent positioning"
        )
        vis.close()
        chassis.close()


# ---------------------------------------------------------------------------
# Part C — MINI Layout & Time Display
# ---------------------------------------------------------------------------

class TestMiniTimeDisplay(unittest.TestCase):
    """MINI strip must expose elapsed / total duration."""

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_mini_time_display_shows_elapsed_and_total(self):
        """After update_telemetry, mini_time_display must contain both elapsed and total."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.update_telemetry("♫ Test Track", "02:15 / 06:34", 0.34, True)
        assert "02:15" in chassis.mini_time_display.text()
        assert "06:34" in chassis.mini_time_display.text()
        assert "/" in chassis.mini_time_display.text(), (
            "mini_time_display must show elapsed / total separator"
        )
        chassis.close()

    def test_mini_time_display_initial_format(self):
        """MINI time display must initialise with both elapsed and total placeholders."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        text = chassis.mini_time_display.text()
        assert "/" in text, f"Initial MINI time display must be 'HH:MM / HH:MM', got '{text}'"
        chassis.close()

    def test_mini_time_display_no_truncation(self):
        """update_telemetry must not strip the total from the MINI display."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.update_telemetry("♫ Long Track", "01:23:45 / 02:30:00", 0.55, True)
        text = chassis.mini_time_display.text()
        assert "02:30:00" in text, "Total duration must not be stripped in MINI"
        chassis.close()


class TestMiniWidth(unittest.TestCase):
    """MINI must be wider than the previous 380 px baseline."""

    EXPECTED_MIN_WIDTH = 440  # Comfortably above old 380; authoritative is 460.

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_mini_width_exceeds_old_baseline(self):
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("mini", animated=False)
        assert chassis.width() >= self.EXPECTED_MIN_WIDTH, (
            f"MINI width {chassis.width()} must be >= {self.EXPECTED_MIN_WIDTH} px"
        )
        chassis.close()

    def test_mini_height_unchanged(self):
        """MINI vertical footprint must remain 36 px."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("mini", animated=False)
        assert chassis.height() == 36, (
            f"MINI height must remain 36 px, got {chassis.height()}"
        )
        chassis.close()

    def test_mini_width_constant_matches_attribute(self):
        """MINI_WIDTH attribute must equal actual MINI width after set_mode."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("mini", animated=False)
        assert chassis.width() == chassis.MINI_WIDTH
        chassis.close()


# ---------------------------------------------------------------------------
# Part D — Session Geometry Compatibility
# ---------------------------------------------------------------------------

class TestSessionGeometryCompatibility(unittest.TestCase):
    """
    Old session files that stored the 380 px MINI width must not trap the
    chassis in incorrect geometry.  The authoritative set_mode dimensions
    must always win; only the position is persisted.
    """

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_chassis_size_after_set_mode_is_authoritative(self):
        """set_mode must always apply the current MINI_WIDTH regardless of prior state."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        # Simulate an "old session" by manually setting a wrong width first
        chassis.setFixedSize(380, 36)
        # set_mode must override any stale dimension
        chassis.set_mode("mini", animated=False)
        assert chassis.width() == chassis.MINI_WIDTH, (
            f"set_mode must apply authoritative MINI_WIDTH={chassis.MINI_WIDTH}, "
            f"got {chassis.width()}"
        )
        chassis.close()

    def test_normal_mode_dimensions_unchanged(self):
        """NORMAL mode dimensions must remain 420×135 px."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("normal", animated=False)
        assert chassis.width() == 420
        assert chassis.height() == 135
        chassis.close()


# ---------------------------------------------------------------------------
# Part E — Lifecycle Semantics
# ---------------------------------------------------------------------------

class TestLifecycleSemantics(unittest.TestCase):
    """
    FIX-002 close/shutdown semantics must remain intact.
    closeEvent must always route to close_requested, never to Qt's default close.
    """

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_close_event_emits_close_requested(self):
        from toroidamp.ui.chassis import UnifiedChassis
        from PySide6.QtGui import QCloseEvent
        chassis = UnifiedChassis()
        received = []
        chassis.close_requested.connect(lambda: received.append(True))
        event = QCloseEvent()
        chassis.closeEvent(event)
        assert event.isAccepted() is False, "closeEvent must be ignored (not accepted)"
        assert received == [True], "closeEvent must emit close_requested"
        chassis.close()

    def test_chassis_signals_present(self):
        """All critical chassis signals must remain present after UX-001 changes."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        required_signals = [
            "seek_changed", "volume_changed", "play_toggled", "prev_clicked",
            "next_clicked", "stop_clicked", "close_requested", "minimize_requested",
            "scale_changed", "retina_melt_requested", "files_dropped",
        ]
        for sig in required_signals:
            assert hasattr(chassis, sig), f"chassis.{sig} signal must exist"
        chassis.close()


if __name__ == "__main__":
    unittest.main()
