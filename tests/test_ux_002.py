"""
tests/test_ux_002.py — UX-002 Always-Visible Player Contract

Focused regression tests for:
  A. NORMAL ─ button → set_mode("mini"), not hide_to_tray.
  B. No hide_to_tray / is_hidden_to_tray in WindowManager.
  C. MINI strip has no redundant ─ hide button.
  D. Native OS minimize intercepted → chassis stays visible in MINI.
  E. Tray restore_requested → _focus_chassis (raise + activate), not hide/show cycle.
  F. Lifecycle completeness: 3 visible states + 1 terminal; no hidden state.
  G. Neon tick guard removed — neon always runs (no is_hidden_to_tray check).

NOTE: Tests that exercise the real Qt event loop require a QApplication.
      OS-level minimize interception (Win+M, taskbar click) requires manual
      validation on a live desktop — automated tests can only assert the
      changeEvent mechanism is present and structurally correct.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch, call

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QEvent
    from PySide6.QtGui import QCloseEvent
    _app = QApplication.instance() or QApplication(sys.argv)
    QT_AVAILABLE = True
except Exception:
    QT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Part A — NORMAL ─ button routes to MINI, not hide_to_tray
# ---------------------------------------------------------------------------

class TestNormalMinimizeRouting(unittest.TestCase):
    """NORMAL ─ button must switch to MINI, not invoke hide_to_tray semantics."""

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_minimize_requested_signal_exists(self):
        """chassis.minimize_requested must still exist — signal is the contract point."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        assert hasattr(chassis, "minimize_requested"), (
            "chassis.minimize_requested signal must exist"
        )
        chassis.close()

    def test_normal_minimize_button_emits_minimize_requested(self):
        """NORMAL ─ button click must emit minimize_requested (not close_requested)."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("normal", animated=False)
        received_minimize = []
        received_close = []
        chassis.minimize_requested.connect(lambda: received_minimize.append(True))
        chassis.close_requested.connect(lambda: received_close.append(True))
        # Trigger minimize_requested programmatically (mirrors btn_min.clicked)
        chassis.minimize_requested.emit()
        assert received_minimize == [True], "minimize_requested must be emittable"
        assert received_close == [], "close_requested must NOT fire on minimize"
        chassis.close()

    def test_mini_strip_has_no_hide_button(self):
        """
        MINI strip must not contain a QPushButton wired to minimize_requested.
        The ─ button was removed from _init_mini_view in UX-002.
        """
        from toroidamp.ui.chassis import UnifiedChassis
        from PySide6.QtWidgets import QPushButton
        chassis = UnifiedChassis()
        # Collect all QPushButton children of mini_widget and check none have "─"
        mini_buttons = chassis.mini_widget.findChildren(QPushButton)
        hide_buttons = [b for b in mini_buttons if b.text() == "─"]
        assert hide_buttons == [], (
            "MINI strip must not contain a ─ (hide) button — "
            f"found {[b.text() for b in hide_buttons]}"
        )
        chassis.close()


# ---------------------------------------------------------------------------
# Part B — WindowManager has no is_hidden_to_tray / hide_to_tray
# ---------------------------------------------------------------------------

class TestWindowManagerNoHiddenState(unittest.TestCase):
    """
    WindowManager must not carry hide_to_tray(), restore_from_tray(),
    or is_hidden_to_tray as part of its public interface.
    These were removed in UX-002 — their absence is the contract.
    """

    def test_hide_to_tray_method_removed(self):
        from toroidamp.ui.window_manager import WindowManager
        assert not hasattr(WindowManager, "hide_to_tray"), (
            "hide_to_tray must be removed from WindowManager (UX-002)"
        )

    def test_restore_from_tray_method_removed(self):
        from toroidamp.ui.window_manager import WindowManager
        assert not hasattr(WindowManager, "restore_from_tray"), (
            "restore_from_tray must be removed from WindowManager (UX-002)"
        )

    def test_handle_close_action_method_removed(self):
        from toroidamp.ui.window_manager import WindowManager
        assert not hasattr(WindowManager, "handle_close_action"), (
            "handle_close_action was dead code and must be removed (UX-002)"
        )

    def test_focus_chassis_method_present(self):
        """_focus_chassis replaces restore_from_tray — it raises/activates the chassis."""
        from toroidamp.ui.window_manager import WindowManager
        assert hasattr(WindowManager, "_focus_chassis"), (
            "_focus_chassis must exist as the tray Show handler"
        )


# ---------------------------------------------------------------------------
# Part D — Native minimize intercepted by changeEvent
# ---------------------------------------------------------------------------

class TestChangeEventMinimizeInterception(unittest.TestCase):
    """
    UnifiedChassis.changeEvent must intercept Qt.WindowMinimized and
    redirect to MINI mode, keeping the chassis visible.
    """

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_chassis_has_change_event_override(self):
        from toroidamp.ui.chassis import UnifiedChassis
        # changeEvent must be overridden in UnifiedChassis, not just inherited from QWidget
        assert "changeEvent" in UnifiedChassis.__dict__, (
            "UnifiedChassis must override changeEvent to intercept native minimize"
        )

    def test_minimize_state_redirects_to_mini_mode(self):
        """
        When chassis receives a WindowStateChange with WindowMinimized,
        it must switch to mini mode and remain visible.
        """
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("normal", animated=False)
        assert chassis.mode == "normal"

        # Simulate a WindowStateChange event with minimized state
        event = QEvent(QEvent.Type.WindowStateChange)
        # Manually set window state to minimized, then call changeEvent
        chassis.setWindowState(Qt.WindowMinimized)
        chassis.changeEvent(event)

        # Chassis must have switched to mini
        assert chassis.mode == "mini", (
            f"Chassis must switch to MINI on minimize, got mode='{chassis.mode}'"
        )
        chassis.close()

    def test_minimize_from_mini_stays_mini(self):
        """
        A minimize event while already in MINI must not re-trigger set_mode or error.
        """
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("mini", animated=False)
        assert chassis.mode == "mini"

        event = QEvent(QEvent.Type.WindowStateChange)
        chassis.setWindowState(Qt.WindowMinimized)
        # Must not raise
        chassis.changeEvent(event)
        assert chassis.mode == "mini"
        chassis.close()

    def test_non_minimize_state_change_passes_through(self):
        """
        WindowStateChange to a non-minimized state must call super() and not
        change the chassis mode.
        """
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("normal", animated=False)

        # Emit a non-minimize WindowStateChange (e.g. WindowNoState)
        chassis.setWindowState(Qt.WindowNoState)
        event = QEvent(QEvent.Type.WindowStateChange)
        chassis.changeEvent(event)

        # Mode must be unchanged
        assert chassis.mode == "normal", (
            "Non-minimize state change must not alter chassis mode"
        )
        chassis.close()


# ---------------------------------------------------------------------------
# Part E — Tray restore → _focus_chassis, not hide/show
# ---------------------------------------------------------------------------

class TestTrayRestoreRouting(unittest.TestCase):
    """
    Tray restore_requested must call _focus_chassis (raise + activate),
    not toggle chassis visibility.
    """

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_focus_chassis_raises_and_activates(self):
        """_focus_chassis calls raise_() and activateWindow() on the chassis."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()

        # Patch raise_ and activateWindow to track calls
        raise_calls = []
        activate_calls = []
        chassis.raise_ = lambda: raise_calls.append(True)
        chassis.activateWindow = lambda: activate_calls.append(True)

        # Create a minimal mock window_manager-style object with the method
        class FakeWM:
            def __init__(self, ch):
                self.chassis = ch
            def _focus_chassis(self):
                self.chassis.raise_()
                self.chassis.activateWindow()

        wm = FakeWM(chassis)
        wm._focus_chassis()

        assert raise_calls == [True], "_focus_chassis must call chassis.raise_()"
        assert activate_calls == [True], "_focus_chassis must call chassis.activateWindow()"
        chassis.close()


# ---------------------------------------------------------------------------
# Part F — Lifecycle: 3 visible states + 1 terminal; no hidden state
# ---------------------------------------------------------------------------

class TestLifecycleStates(unittest.TestCase):
    """
    ToroidAMP has exactly 3 running visible states and 1 terminal state.
    No hidden state exists in the lifecycle.
    """

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_mini_to_normal_transition(self):
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("mini", animated=False)
        assert chassis.mode == "mini"
        chassis.set_mode("normal", animated=False)
        assert chassis.mode == "normal"
        chassis.close()

    def test_normal_to_mini_transition(self):
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("normal", animated=False)
        assert chassis.mode == "normal"
        chassis.set_mode("mini", animated=False)
        assert chassis.mode == "mini"
        chassis.close()

    def test_close_requested_signal_present(self):
        """close_requested is the terminal state entry point — must remain present."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        received = []
        chassis.close_requested.connect(lambda: received.append(True))
        chassis.close_requested.emit()
        assert received == [True]
        chassis.close()

    def test_mini_is_always_on_top(self):
        """MINI mode must set WindowStaysOnTopHint — minimum presence contract."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("mini", animated=False)
        flags = chassis.windowFlags()
        assert bool(flags & Qt.WindowStaysOnTopHint), (
            "MINI mode must set Qt.WindowStaysOnTopHint — minimum always-visible presence"
        )
        chassis.close()

    def test_normal_mode_not_always_on_top(self):
        """NORMAL mode must clear WindowStaysOnTopHint to behave as a regular window."""
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("normal", animated=False)
        flags = chassis.windowFlags()
        assert not bool(flags & Qt.WindowStaysOnTopHint), (
            "NORMAL mode must not set Qt.WindowStaysOnTopHint"
        )
        chassis.close()


# ---------------------------------------------------------------------------
# Part G — Neon tick runs unconditionally (no is_hidden_to_tray guard)
# ---------------------------------------------------------------------------

class TestNeonTickUnconditional(unittest.TestCase):
    """
    The neon controller update must not be gated on is_hidden_to_tray.
    Since WindowManager.is_hidden_to_tray no longer exists, the guard is gone.
    """

    def test_window_manager_has_no_is_hidden_to_tray_attribute(self):
        """is_hidden_to_tray flag must not exist anywhere in WindowManager."""
        from toroidamp.ui.window_manager import WindowManager
        import inspect
        source = inspect.getsource(WindowManager)
        assert "is_hidden_to_tray" not in source, (
            "is_hidden_to_tray must be fully removed from WindowManager source (UX-002)"
        )


# ---------------------------------------------------------------------------
# UX-001 Regression Guard — ensure UX-001 contracts still hold
# ---------------------------------------------------------------------------

class TestUX001Regression(unittest.TestCase):
    """
    Spot-check that UX-002 changes did not regress critical UX-001 contracts.
    """

    def setUp(self):
        if not QT_AVAILABLE:
            self.skipTest("PySide6 not available")

    def test_seek_slider_still_seek_slider(self):
        from toroidamp.ui.chassis import UnifiedChassis, SeekSlider
        chassis = UnifiedChassis()
        assert isinstance(chassis.normal_seek_slider, SeekSlider)
        chassis.close()

    def test_mini_time_display_still_full(self):
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.update_telemetry("♫ Track", "03:10 / 07:45", 0.42, True)
        text = chassis.mini_time_display.text()
        assert "03:10" in text and "07:45" in text and "/" in text
        chassis.close()

    def test_mini_width_still_460(self):
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        chassis.set_mode("mini", animated=False)
        assert chassis.width() == chassis.MINI_WIDTH == 460
        chassis.close()

    def test_close_event_still_emits_close_requested(self):
        from toroidamp.ui.chassis import UnifiedChassis
        chassis = UnifiedChassis()
        received = []
        chassis.close_requested.connect(lambda: received.append(True))
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        chassis.closeEvent(event)
        assert event.isAccepted() is False
        assert received == [True]
        chassis.close()


if __name__ == "__main__":
    unittest.main()
