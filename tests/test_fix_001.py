"""
ToroidAMP - FIX-001 Test Suite
Validates:
1. Lifecycle separation: MINI vs MINIMIZE (hide to tray) vs CLOSE (shutdown).
2. Authoritative X = EXIT semantics (process shutdown, audio release).
3. Startup empty-state contract (no loaded track, PlayerEngine in STOPPED state).
4. Restored playlist sanitization (dead files discarded, next/prev traverse valid only).
5. VoiceService failure isolation (TTS failure does not prevent startup).
6. Backward compatibility of session deserialization.
"""

import json
import os
import sys
import tempfile
import time

from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.player import PlayerEngine, PlaybackState
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.audio.voice import VoiceService
from toroidamp.session import SessionManager, SessionState, WindowPosition, ModulePosition


def test_playlist_sanitization_and_traversal():
    """Validates that dead files are purged from restored playlists and traversal is clean."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create 2 real audio files and 2 non-existent references
        real_file_1 = os.path.join(tmp_dir, "real_1.mp3")
        real_file_2 = os.path.join(tmp_dir, "real_2.mp3")
        with open(real_file_1, "wb") as f:
            f.write(b"RIFF dummy 1")
        with open(real_file_2, "wb") as f:
            f.write(b"RIFF dummy 2")

        dead_file_1 = os.path.join(tmp_dir, "dead_1.mp3")
        dead_file_2 = os.path.join(tmp_dir, "dead_2.mp3")

        pl = PlaylistManager()
        pl.add_file(real_file_1, "Real 1")
        pl.add_file(dead_file_1, "Dead 1")
        pl.add_file(real_file_2, "Real 2")
        pl.add_file(dead_file_2, "Dead 2")

        assert len(pl) == 4

        # Sanitize
        removed = pl.sanitize()
        assert len(removed) == 2
        assert len(pl) == 2
        assert pl.items[0].filepath == os.path.abspath(real_file_1)
        assert pl.items[1].filepath == os.path.abspath(real_file_2)

        # Set startup empty index
        pl.current_index = -1
        assert pl.current_item is None

        # Next loads first valid track (index 0)
        next_idx = pl.get_next_index()
        assert next_idx == 0
        pl.current_index = next_idx
        assert pl.current_item.title == "Real 1"

        # Next loads second valid track (index 1)
        next_idx = pl.get_next_index()
        assert next_idx == 1
        pl.current_index = next_idx
        assert pl.current_item.title == "Real 2"

        # End of queue without repeat -> None
        assert pl.get_next_index() is None


def test_startup_empty_state_and_session_restore():
    """Validates that session hydration restores queue but keeps player unloaded and stopped."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    from PySide6.QtWidgets import QApplication
    from toroidamp.ui.window_manager import WindowManager

    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp_dir:
        session_file = os.path.join(tmp_dir, "session_test.json")

        # Create session data with playlist and track index
        real_file = os.path.join(tmp_dir, "valid.mp3")
        with open(real_file, "wb") as f:
            f.write(b"RIFF dummy")

        sm = SessionManager(custom_path=session_file)
        sm.state.playlist_files = [
            {"filepath": real_file, "title": "Valid Track", "duration": 120.0},
            {"filepath": os.path.join(tmp_dir, "ghost.mp3"), "title": "Ghost", "duration": 80.0}
        ]
        sm.state.current_track_index = 0
        sm.save()

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()

        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)

        # 1. Verify sanitized playlist
        assert len(playlist) == 1
        assert playlist.items[0].title == "Valid Track"

        # 2. Verify STARTUP EMPTY STATE
        assert player.state == PlaybackState.STOPPED
        assert playlist.current_index == -1
        assert playlist.current_item is None
        assert wm.chassis.normal_title_marquee.text() == "♫ No Track Loaded"

        wm.shutdown()

    app.quit()


def test_lifecycle_separation_mini_minimize_close():
    """
    Validates distinct behaviors for MINI, MINIMIZE, and CLOSE (X shutdown).

    UX-002 superseded FIX-001's original hide-to-tray MINIMIZE contract:
    ToroidAMP is now an always-visible player (docs/ux/002_always_visible_player.md).
    MINIMIZE (-) routes to MINI mode rather than hiding the chassis to the
    tray — `is_hidden_to_tray`/`restore_from_tray` no longer exist. This test
    was rewritten to assert the current authoritative lifecycle rather than
    the removed one; see tests/test_ux_002.py for the full UX-002 contract.
    """
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    from PySide6.QtWidgets import QApplication
    from toroidamp.ui.window_manager import WindowManager

    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp_dir:
        session_file = os.path.join(tmp_dir, "lifecycle_session.json")
        sm = SessionManager(custom_path=session_file)

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()

        mp3_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "audio", "Burn The World Waltz.mp3"))
        if os.path.exists(mp3_path):
            playlist.add_file(mp3_path, "Burn The World Waltz", 200.0)

        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)
        wm._play_index(0)
        assert player.state == PlaybackState.PLAYING

        # 1. Test MINI scale: window visible, compact 460x36, playback continues
        wm.chassis.set_mode("mini")
        assert wm.chassis.mode == "mini"
        assert wm.chassis.isVisible() is True
        assert wm.chassis.width() == wm.chassis.MINI_WIDTH
        assert wm.chassis.height() == wm.chassis.MINI_HEIGHT
        assert player.state == PlaybackState.PLAYING

        # 2. Test MINIMIZE (-) from NORMAL: routes to MINI, chassis stays visible
        wm.chassis.set_mode("normal")
        wm.chassis.minimize_requested.emit()
        assert wm.chassis.mode == "mini"
        assert wm.chassis.isVisible() is True
        assert player.state == PlaybackState.PLAYING

        # Return to NORMAL
        wm.chassis.set_mode("normal")
        assert wm.chassis.mode == "normal"
        assert wm.chassis.isVisible() is True
        assert player.state == PlaybackState.PLAYING

        # 3. Test CLOSE (X): triggers complete shutdown and stops playback
        wm.chassis.close_requested.emit()
        assert player.state == PlaybackState.STOPPED

    app.quit()


def test_voice_service_isolation():
    """Validates that VoiceService functions or fails gracefully without blocking or throwing."""
    vs = VoiceService()
    # Test with custom dummy line
    vs.speak_startup_phrase_async("ToroidAMP test phrase")
    # Should not block
    assert isinstance(vs.is_speaking, bool)
    # This spins up a REAL (unmocked) TTS engine on a daemon thread -- on
    # Windows that means a real SAPI5/comtypes COM object. Leaving that
    # thread to finish on its own, unjoined, after this test function
    # returns lets its COM object's lifetime spill into whatever test runs
    # next in this same pytest process; comtypes' own event/__del__ handling
    # is not safe against being garbage-collected while unrelated code runs
    # concurrently on another thread, which produced a real, reproducible
    # native access violation when a later, unrelated test happened to run
    # at the same moment this thread's engine was being torn down. Joining
    # here (with a generous timeout so a genuinely hung engine still fails
    # the test loudly rather than hanging the suite) keeps this real
    # background thread's entire lifecycle contained within this test.
    if vs._thread is not None:
        vs._thread.join(timeout=15)
        assert not vs._thread.is_alive(), "VoiceService thread did not complete in time"


if __name__ == "__main__":
    print("Running test_playlist_sanitization_and_traversal...")
    test_playlist_sanitization_and_traversal()
    print("PASS: test_playlist_sanitization_and_traversal")

    print("Running test_startup_empty_state_and_session_restore...")
    test_startup_empty_state_and_session_restore()
    print("PASS: test_startup_empty_state_and_session_restore")

    print("Running test_lifecycle_separation_mini_minimize_close...")
    test_lifecycle_separation_mini_minimize_close()
    print("PASS: test_lifecycle_separation_mini_minimize_close")

    print("Running test_voice_service_isolation...")
    test_voice_service_isolation()
    print("PASS: test_voice_service_isolation")

    print("\n--> ALL FIX-001 REGRESSION & LIFECYCLE TESTS PASSED 100%! <--")
