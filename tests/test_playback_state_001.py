"""
tests/test_playback_state_001.py — Playback State & Interaction Stabilization

Focused regression tests for:
  1. Natural EOF -> exactly one auto-advance.
  2. User STOP -> zero auto-advance (Windows STOP-auto-advance root cause).
  3. Repeated STOP -> zero auto-advance.
  4. Seek during playback -> zero spurious auto-advance.
  5. Seek near EOF -> zero spurious auto-advance (decoder-race root cause).
  6. Explicit NEXT -> exactly one next-track transition.
  7. Explicit PREVIOUS behaves correctly.
  8. Pause/resume does not trigger completion.
  9. A fade-out completing (user stop) does not masquerade as EOF.
  10. Speaker button toggles the MINI volume popup visible/hidden, including
      the close-on-second-click case that a naive isVisible() check can't
      see (Qt.Popup auto-dismisses itself before the button's own click
      signal fires).

No real audio hardware or files are used -- PlayerEngine's decoder/stream
state is driven directly, and playlist entries use nonexistent paths (only
the state-machine's *decision* to advance/not-advance is under test; a
failed load()/play() against a fake path is caught and logged by
WindowManager.load_and_play(), never raised).
"""

import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from PySide6.QtWidgets import QApplication

from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.player import PlayerEngine, PlaybackState, FadeState
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.session import SessionManager
from toroidamp.ui.window_manager import WindowManager
from toroidamp.ui.chassis import UnifiedChassis

_app = QApplication.instance() or QApplication(sys.argv)


def _make_window_manager(n_tracks=3):
    tmp_dir = tempfile.mkdtemp()
    session_manager = SessionManager(custom_path=os.path.join(tmp_dir, "session.json"))
    handoff = AnalysisHandoff(2048)
    player = PlayerEngine(handoff=handoff)
    playlist = PlaylistManager()
    for i in range(n_tracks):
        playlist.add_file(f"C:/fake/track_{i:02d}.mp3")
    playlist.current_index = 0
    wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=session_manager)
    return wm


class TestNaturalEofAutoAdvance(unittest.TestCase):
    def setUp(self):
        self.wm = _make_window_manager()

    def tearDown(self):
        self.wm.shutdown()

    def test_01_natural_eof_advances_exactly_once(self):
        pe = self.wm.player_engine
        pe._state = PlaybackState.STOPPED
        pe._position_seconds = 42.0
        pe._eof_pending = True

        self.assertEqual(self.wm.playlist.current_index, 0)
        self.wm._tick()
        self.assertEqual(self.wm.playlist.current_index, 1)

        # The flag is consumed -- a second tick must not advance again.
        self.wm._tick()
        self.assertEqual(self.wm.playlist.current_index, 1)


class TestUserStopDoesNotAdvance(unittest.TestCase):
    def setUp(self):
        self.wm = _make_window_manager()

    def tearDown(self):
        self.wm.shutdown()

    def test_02_user_stop_immediate_zero_advance(self):
        pe = self.wm.player_engine
        pe._state = PlaybackState.PLAYING
        pe._position_seconds = 42.0
        pe._active_decoder = object()  # anything non-None; only state matters here
        pe.stop_immediate()

        self.assertEqual(pe.state, PlaybackState.STOPPED)
        self.wm._tick()
        self.assertEqual(self.wm.playlist.current_index, 0, "STOP must never be interpreted as natural EOF")

    def test_03_repeated_stop_zero_advance(self):
        pe = self.wm.player_engine
        pe._active_decoder = object()
        for _ in range(5):
            pe._state = PlaybackState.PLAYING
            pe._position_seconds = 10.0
            pe.stop_immediate()
            self.wm._tick()
        self.assertEqual(self.wm.playlist.current_index, 0)

    def test_09_fade_out_completion_does_not_masquerade_as_eof(self):
        # Reproduces the actual Windows STOP-auto-advance root cause:
        # stop() with fade enabled doesn't call _do_stop() synchronously --
        # it sets FADING_OUT and lets the audio callback ramp the envelope
        # down, transitioning to STOPPED asynchronously once the fade
        # completes. That transition must not set the EOF flag.
        pe = self.wm.player_engine
        pe._active_decoder = object()
        pe._state = PlaybackState.PLAYING
        pe._position_seconds = 55.0
        pe._fade_enabled = True
        pe._stream = object()  # truthy sentinel so stop() takes the fade-out branch
        pe._fade_envelope = 1.0

        pe.stop()
        self.assertEqual(pe.fade_state, FadeState.FADING_OUT, "sanity: fade-out must actually be triggered")

        # Simulate the audio callback's own fade-out-complete transition
        # (mirrors _audio_callback's tail: envelope reached 0 -> IDLE -> STOPPED).
        pe._fade_state = FadeState.IDLE
        pe._fade_envelope = 0.0
        pe._state = PlaybackState.STOPPED

        self.assertFalse(pe.consume_natural_eof(), "a completed fade-out (user stop) must never set the EOF flag")
        self.wm._tick()
        self.assertEqual(self.wm.playlist.current_index, 0)


class TestSeekDoesNotSpuriouslyAdvance(unittest.TestCase):
    def setUp(self):
        self.wm = _make_window_manager()

    def tearDown(self):
        self.wm.shutdown()

    def test_04_seek_during_playback_zero_advance(self):
        pe = self.wm.player_engine

        class FiniteDecoder:
            def read_frames(self, n):
                import numpy as np
                return np.zeros((n, 2), dtype="float32")

        pe._active_decoder = FiniteDecoder()
        pe._state = PlaybackState.PLAYING
        pe._sample_rate = 44100
        pe.seek(30.0)

        self.assertFalse(pe.decoder_failed)
        self.wm._tick()
        self.assertEqual(self.wm.playlist.current_index, 0)

    def test_05_seek_near_eof_only_advances_on_genuine_subsequent_eof(self):
        # Seeking itself must never set the EOF flag -- only a real
        # decoder read reaching zero frames does, and only once that read
        # actually happens (via the audio callback, not via seek() itself).
        pe = self.wm.player_engine
        pe._active_decoder = object()
        pe._state = PlaybackState.PLAYING
        pe.seek(179.9)  # e.g. 0.1s from the end of a 180s track
        self.assertFalse(pe.consume_natural_eof())
        self.wm._tick()
        self.assertEqual(self.wm.playlist.current_index, 0)

    def test_seek_while_playing_is_deferred_not_applied_synchronously(self):
        """seek() must not call decoder.seek() directly while PLAYING --
        see PlayerEngine.seek()'s docstring for the concurrency-race
        rationale (GLSL/audio cut history: unlocked read_frames() in the
        callback vs. a synchronous seek() from the UI thread)."""
        pe = self.wm.player_engine
        seek_calls = []

        class TrackedDecoder:
            def seek(self, t):
                seek_calls.append(t)

            def read_frames(self, n):
                import numpy as np
                return np.zeros((n, 2), dtype="float32")

        pe._active_decoder = TrackedDecoder()
        pe._state = PlaybackState.PLAYING
        pe.seek(12.5)

        self.assertEqual(seek_calls, [], "decoder.seek() must be deferred to the audio callback while PLAYING")
        self.assertEqual(pe.position, 12.5, "position should still update optimistically for immediate UI feedback")

        outdata = __import__("numpy").zeros((512, 2), dtype="float32")
        pe._audio_callback(outdata, 512, None, None)
        self.assertEqual(seek_calls, [12.5], "the deferred seek must be applied on the next callback")


class TestExplicitTransportTransitions(unittest.TestCase):
    def setUp(self):
        self.wm = _make_window_manager()

    def tearDown(self):
        self.wm.shutdown()

    def test_06_explicit_next_advances_exactly_once(self):
        self.assertEqual(self.wm.playlist.current_index, 0)
        self.wm._play_next()
        self.assertEqual(self.wm.playlist.current_index, 1)
        self.wm.player_engine.stop_immediate()

    def test_07_explicit_previous_behaves_correctly(self):
        self.wm.playlist.current_index = 1
        self.wm._play_previous()
        self.assertEqual(self.wm.playlist.current_index, 0)
        self.wm.player_engine.stop_immediate()

    def test_08_pause_resume_does_not_trigger_completion(self):
        pe = self.wm.player_engine
        pe._active_decoder = object()
        pe._state = PlaybackState.PLAYING
        pe._position_seconds = 20.0
        pe.pause()
        self.assertEqual(pe.state, PlaybackState.PAUSED)
        self.wm._tick()
        self.assertEqual(self.wm.playlist.current_index, 0)

        pe._state = PlaybackState.PLAYING  # resume
        self.wm._tick()
        self.assertEqual(self.wm.playlist.current_index, 0)


class TestVolumePopupToggle(unittest.TestCase):
    def test_10a_second_click_after_auto_dismiss_does_not_reopen(self):
        c = UnifiedChassis()
        c._toggle_mini_volume_popup()
        self.assertTrue(c.volume_popup.isVisible())

        # Simulate Qt's own popup auto-dismiss-on-outside-click (this is
        # what happens milliseconds before the speaker button's own
        # `clicked` signal fires on a real second click).
        c.volume_popup.hide()
        self.assertFalse(c.volume_popup.isVisible())

        # The button's clicked handler runs immediately after, in the same
        # physical click -- must not reopen it.
        c._toggle_mini_volume_popup()
        self.assertFalse(c.volume_popup.isVisible(), "a second click must leave the popup closed, not reopen it")
        c.close()

    def test_10b_reopen_works_after_the_debounce_window(self):
        import time
        c = UnifiedChassis()
        c._toggle_mini_volume_popup()
        c.volume_popup.hide()
        c._volume_popup_hidden_at -= 1.0  # simulate time passing well past the debounce window
        c._toggle_mini_volume_popup()
        self.assertTrue(c.volume_popup.isVisible(), "a deliberate later click must still be able to reopen it")
        c.close()

    def test_10c_explicit_close_while_visible_still_hides(self):
        c = UnifiedChassis()
        c._toggle_mini_volume_popup()
        self.assertTrue(c.volume_popup.isVisible())
        c._toggle_mini_volume_popup()
        self.assertFalse(c.volume_popup.isVisible())
        c.close()


if __name__ == "__main__":
    unittest.main()
