"""
ToroidAMP - Production Cut 2 Test Suite
Validates Session Persistence (Serialization, Deserialization, Atomic Writing, Corrupted Recovery),
Screen Geometry Clamping, Playlist & Module Restoration, System Tray, and Clean Shutdown Lifecycle.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
import numpy as np

from toroidamp.analysis.audio_frame import AnalysisHandoff, AudioFrame
from toroidamp.audio.player import PlayerEngine, PlaybackState
from toroidamp.audio.playlist import PlaylistItem, PlaylistManager
from toroidamp.session import SessionManager, SessionState, WindowPosition, ModulePosition


def test_session_serialization_and_atomic_write():
    """Validates full session state serialization, atomic save, and deserialization."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_file = os.path.join(tmp_dir, "session.json")
        sm = SessionManager(custom_path=session_file)

        # Configure custom state
        sm.state.scale = "mini"
        sm.state.volume = 0.65
        sm.state.shuffle = True
        sm.state.repeat = True
        sm.state.selected_visualizer_idx = 1
        sm.state.chassis_pos = WindowPosition(x=100, y=150, w=380, h=36)
        sm.state.vis_module = ModulePosition(x=100, y=190, is_docked=True, dock_edge="bottom", is_visible=True)
        sm.state.pl_module = ModulePosition(x=485, y=150, is_docked=False, dock_edge="right", is_visible=True)
        sm.state.playlist_files = [
            {"filepath": "/music/song1.mp3", "title": "Song 1", "duration": 180.0},
            {"filepath": "/music/track.xm", "title": "Track XM", "duration": 45.0}
        ]
        sm.state.current_track_index = 1
        sm.state.last_position_seconds = 23.5

        # Atomic Save
        sm.save()
        assert os.path.exists(session_file)

        # Load into fresh manager
        sm2 = SessionManager(custom_path=session_file)
        st2 = sm2.load()

        assert st2.scale == "mini"
        assert abs(st2.volume - 0.65) < 1e-4
        assert st2.shuffle is True
        assert st2.repeat is True
        assert st2.selected_visualizer_idx == 1
        assert st2.chassis_pos.x == 100
        assert st2.chassis_pos.y == 150
        assert st2.vis_module.is_docked is True
        assert st2.pl_module.is_docked is False
        assert len(st2.playlist_files) == 2
        assert st2.current_track_index == 1
        assert abs(st2.last_position_seconds - 23.5) < 1e-4


def test_corrupted_and_missing_session_recovery():
    """Validates graceful fallback to defaults when session file is corrupted or missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Missing file
        missing_file = os.path.join(tmp_dir, "non_existent.json")
        sm_missing = SessionManager(custom_path=missing_file)
        st_missing = sm_missing.load()
        assert st_missing.scale == "normal"
        assert st_missing.volume == 0.8
        assert len(st_missing.playlist_files) == 0

        # 2. Corrupted JSON
        corrupt_file = os.path.join(tmp_dir, "corrupt.json")
        with open(corrupt_file, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON DATA --- [[")

        sm_corrupt = SessionManager(custom_path=corrupt_file)
        st_corrupt = sm_corrupt.load()
        assert st_corrupt.scale == "normal"
        assert st_corrupt.volume == 0.8


def test_screen_geometry_clamping():
    """Validates that off-screen or disconnect-orphaned coordinates are clamped safely into view."""
    class MockScreenRect:
        def left(self): return 0
        def top(self): return 0
        def right(self): return 1920
        def bottom(self): return 1080

    mock_screen = MockScreenRect()

    # Normal visible coordinate
    cx, cy = SessionManager.clamp_to_screen(300, 200, 420, 135, mock_screen)
    assert cx == 300
    assert cy == 200

    # Negative off-screen coordinate (Monitor 2 disconnected to the left)
    cx_neg, cy_neg = SessionManager.clamp_to_screen(-1000, -500, 420, 135, mock_screen)
    assert cx_neg >= -420 + 40
    assert cy_neg >= 0

    # Beyond right border (Resolution scaled down)
    cx_far, cy_far = SessionManager.clamp_to_screen(3000, 2000, 420, 135, mock_screen)
    assert cx_far <= 1920 - 40
    assert cy_far <= 1080 - 40


def test_desktop_lifecycle_tray_and_shutdown():
    """Validates full desktop lifecycle: hide to tray, continuous audio, restore, and shutdown."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    from PySide6.QtWidgets import QApplication
    from toroidamp.ui.window_manager import WindowManager

    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp_dir:
        session_file = os.path.join(tmp_dir, "test_session.json")
        sm = SessionManager(custom_path=session_file)

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()
        
        # Load sample audio
        mp3_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "audio", "Burn The World Waltz.mp3"))
        if os.path.exists(mp3_path):
            playlist.add_file(mp3_path, "Burn The World Waltz", 200.0)

        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)

        # 1. Start playback and open modules
        wm._play_index(0)
        wm._toggle_vis()
        wm._toggle_pl()
        assert player.state == PlaybackState.PLAYING
        assert wm.vis_mod.isVisible()
        assert wm.pl_mod.isVisible()

        # 2. Hide to Tray (Simulate clicking '✕' or Close)
        wm.handle_close_action()
        assert wm.is_hidden_to_tray is True
        assert not wm.chassis.isVisible()
        assert not wm.vis_mod.isVisible()
        assert not wm.pl_mod.isVisible()
        assert player.state == PlaybackState.PLAYING  # AUDIO REMAINS PLAYING!

        # 3. Restore from Tray
        wm.restore_from_tray()
        assert wm.is_hidden_to_tray is False
        assert wm.chassis.isVisible()
        assert wm.vis_mod.isVisible()
        assert wm.pl_mod.isVisible()
        assert player.state == PlaybackState.PLAYING

        # 4. Clean Shutdown Sequence
        wm.shutdown()
        assert player.state == PlaybackState.STOPPED

        # 5. Verify Session File was saved on shutdown
        assert os.path.exists(session_file)
        sm_restart = SessionManager(custom_path=session_file)
        st_restart = sm_restart.load()
        assert len(st_restart.playlist_files) == 1
        assert st_restart.vis_module.is_visible is True
        assert st_restart.pl_module.is_visible is True

    app.quit()


if __name__ == "__main__":
    print("Running test_session_serialization_and_atomic_write...")
    test_session_serialization_and_atomic_write()
    print("PASS: test_session_serialization_and_atomic_write")

    print("Running test_corrupted_and_missing_session_recovery...")
    test_corrupted_and_missing_session_recovery()
    print("PASS: test_corrupted_and_missing_session_recovery")

    print("Running test_screen_geometry_clamping...")
    test_screen_geometry_clamping()
    print("PASS: test_screen_geometry_clamping")

    print("Running test_desktop_lifecycle_tray_and_shutdown...")
    test_desktop_lifecycle_tray_and_shutdown()
    print("PASS: test_desktop_lifecycle_tray_and_shutdown")

    print("\n--> ALL PRODUCTION CUT 2 PERSISTENCE & LIFECYCLE TESTS PASSED 100%! <--")
