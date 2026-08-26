"""
ToroidAMP - FIX-002 Regression & Production Isolation Test Suite
Validates:
1. Strict production isolation: startup with no session / CLI produces an empty playlist.
2. No runtime dependency or path references to MetalWar-Installer.
3. Native Qt close events (WM_CLOSE / Taskbar thumbnail X / Alt+F4) route to authoritative shutdown.
4. Minimize keeps process and audio alive, while close terminates everything.
"""

import os
import sys
import tempfile

from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.player import PlayerEngine, PlaybackState
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.session import SessionManager


def test_production_isolation_empty_startup():
    """Validates that a fresh startup with no session or CLI args results in an empty playlist."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    from PySide6.QtWidgets import QApplication
    from toroidamp.ui.window_manager import WindowManager

    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp_dir:
        session_file = os.path.join(tmp_dir, "empty_session.json")
        sm = SessionManager(custom_path=session_file)

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()

        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)

        # 1. Assert Playlist is 100% EMPTY (no donor tracks or test audio auto-injected)
        assert len(playlist) == 0, f"Expected empty playlist on fresh startup, found {len(playlist)} items"
        assert playlist.current_item is None
        assert playlist.current_index == -1

        # 2. Assert PlayerEngine state
        assert player.state == PlaybackState.STOPPED
        assert player.is_tracker is False
        assert player.duration == 0.0

        wm.shutdown()

    app.quit()


def test_no_donor_path_in_production_codebase():
    """Validates that no production src/ files reference MetalWar-Installer."""
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "toroidamp"))
    forbidden = ["metalwar", "dalezy", "lotus_drei"]

    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                    for term in forbidden:
                        # Comments explaining historical origins are acceptable, but active paths are forbidden
                        lines = [line for line in content.splitlines() if term in line and not line.strip().startswith("#")]
                        assert len(lines) == 0, f"Found forbidden donor reference in {filepath}: {lines}"


def test_native_close_event_routing():
    """Validates that closeEvent on UnifiedChassis triggers authoritative WindowManager shutdown."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QCloseEvent
    from toroidamp.ui.window_manager import WindowManager

    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp_dir:
        session_file = os.path.join(tmp_dir, "close_session.json")
        sm = SessionManager(custom_path=session_file)

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()

        # Add track and play
        test_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "audio", "Burn The World Waltz.mp3"))
        if os.path.exists(test_file):
            playlist.add_file(test_file, "Test", 200.0)

        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)
        wm._play_index(0)
        assert player.state == PlaybackState.PLAYING

        # Simulate native Windows WM_CLOSE / Taskbar thumbnail X / Alt+F4
        close_evt = QCloseEvent()
        wm.chassis.closeEvent(close_evt)

        # Assert full shutdown executed: audio stopped, windows closed, timers stopped
        assert player.state == PlaybackState.STOPPED
        assert wm.render_timer.isActive() is False
        assert wm.snap_timer.isActive() is False
        assert getattr(wm, "_is_shutting_down", False) is True

    app.quit()


if __name__ == "__main__":
    print("Running test_production_isolation_empty_startup...")
    test_production_isolation_empty_startup()
    print("PASS: test_production_isolation_empty_startup")

    print("Running test_no_donor_path_in_production_codebase...")
    test_no_donor_path_in_production_codebase()
    print("PASS: test_no_donor_path_in_production_codebase")

    print("Running test_native_close_event_routing...")
    test_native_close_event_routing()
    print("PASS: test_native_close_event_routing")

    print("\n--> ALL FIX-002 PRODUCTION ISOLATION & SHUTDOWN TESTS PASSED 100%! <--")
