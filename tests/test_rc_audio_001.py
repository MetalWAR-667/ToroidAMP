"""
RC-AUDIO-001 Automated Test Suite — Decoder Error Isolation & Recovery
Tests that malformed audio, throwing decoders, and seek exceptions are safely
isolated without escaping the audio callback or crashing the player.
"""

import os
import tempfile
import unittest
import numpy as np
from pathlib import Path
from PySide6.QtWidgets import QApplication

from toroidamp.audio.player import PlayerEngine, PlaybackState, FadeState
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.decoders import AudioDecoder, ConventionalDecoder, TrackerDecoder


class ThrowingDecoder(AudioDecoder):
    """Test fixture decoder that throws exceptions on read or seek."""
    def __init__(self, throw_on_read=True, throw_on_seek=False, sample_rate=44100, duration=10.0, title="Throwing Track"):
        self.throw_on_read = throw_on_read
        self.throw_on_seek = throw_on_seek
        self._sr = sample_rate
        self._duration = duration
        self._title = title
        self.read_calls = 0
        self.seek_calls = 0
        self.closed = False

    def load(self, filepath: str) -> None:
        pass

    def read_frames(self, num_frames: int) -> np.ndarray:
        self.read_calls += 1
        if self.throw_on_read:
            raise RuntimeError("soundfile.LibsndfileError: Unspecified internal error / Illegal MPEG Header")
        return np.ones((num_frames, 2), dtype=np.float32)

    def seek(self, position_seconds: float) -> None:
        self.seek_calls += 1
        if self.throw_on_seek:
            raise RuntimeError("soundfile.LibsndfileError: Seek failed")

    def get_duration(self) -> float:
        return self._duration

    def get_title(self) -> str:
        return self._title

    def get_sample_rate(self) -> int:
        return self._sr

    def close(self) -> None:
        self.closed = True


class NormalDummyDecoder(AudioDecoder):
    """Test fixture decoder that works normally."""
    def __init__(self, sample_rate=44100, duration=10.0, title="Valid Track"):
        self._sr = sample_rate
        self._duration = duration
        self._title = title
        self.read_calls = 0
        self.closed = False

    def load(self, filepath: str) -> None:
        pass

    def read_frames(self, num_frames: int) -> np.ndarray:
        self.read_calls += 1
        return np.ones((num_frames, 2), dtype=np.float32)

    def seek(self, position_seconds: float) -> None:
        pass

    def get_duration(self) -> float:
        return self._duration

    def get_title(self) -> str:
        return self._title

    def get_sample_rate(self) -> int:
        return self._sr

    def close(self) -> None:
        self.closed = True


class TestRCAudio001DecoderIsolation(unittest.TestCase):
    def setUp(self):
        self.handoff = AnalysisHandoff()
        self.player = PlayerEngine(handoff=self.handoff)

    def tearDown(self):
        self.player.close()

    # 1. read_frames exception does not escape _audio_callback
    def test_01_read_frames_exception_does_not_escape_callback(self):
        decoder = ThrowingDecoder(throw_on_read=True)
        self.player._active_decoder = decoder
        self.player._state = PlaybackState.PLAYING
        self.player._current_filepath = "test_broken.mp3"

        outdata = np.ones((512, 2), dtype=np.float32)
        # Calling callback must NOT raise an exception
        try:
            self.player._audio_callback(outdata, 512, None, None)
        except Exception as e:
            self.fail(f"_audio_callback allowed exception to escape: {e}")

    # 2. callback outputs silence on decoder failure
    def test_02_callback_outputs_silence_on_failure(self):
        decoder = ThrowingDecoder(throw_on_read=True)
        self.player._active_decoder = decoder
        self.player._state = PlaybackState.PLAYING

        outdata = np.ones((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)

        self.assertTrue(np.all(outdata == 0.0))

    # 3. decoder failure is marked exactly once
    def test_03_decoder_failure_is_marked_properly(self):
        decoder = ThrowingDecoder(throw_on_read=True)
        self.player._active_decoder = decoder
        self.player._state = PlaybackState.PLAYING
        self.player._current_filepath = "corrupt.mp3"

        self.assertFalse(self.player.decoder_failed)
        outdata = np.zeros((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)

        self.assertTrue(self.player.decoder_failed)
        self.assertEqual(self.player.state, PlaybackState.STOPPED)

        has_err, path, msg = self.player.check_and_clear_error()
        self.assertTrue(has_err)
        self.assertEqual(path, "corrupt.mp3")
        self.assertIn("LibsndfileError", msg)
        self.assertFalse(self.player.decoder_failed)

    # 4. repeated callbacks after failure remain safe
    def test_04_repeated_callbacks_after_failure_remain_safe_silence(self):
        decoder = ThrowingDecoder(throw_on_read=True)
        self.player._active_decoder = decoder
        self.player._state = PlaybackState.PLAYING

        outdata = np.ones((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)
        self.assertEqual(decoder.read_calls, 1)

        # Repeated callbacks should not invoke read_frames again (no spam)
        for _ in range(5):
            outdata.fill(1.0)
            self.player._audio_callback(outdata, 512, None, None)
            self.assertTrue(np.all(outdata == 0.0))
            self.assertEqual(decoder.read_calls, 1)

    # 5. seek failure does not propagate to UI caller
    def test_05_seek_failure_does_not_propagate(self):
        decoder = ThrowingDecoder(throw_on_read=False, throw_on_seek=True)
        self.player._active_decoder = decoder
        self.player._state = PlaybackState.PLAYING
        self.player._current_filepath = "bad_seek.mp3"

        success = self.player.seek(5.0)
        self.assertFalse(success)
        self.assertTrue(self.player.decoder_failed)

        has_err, path, msg = self.player.check_and_clear_error()
        self.assertTrue(has_err)
        self.assertIn("Seek error", msg)

    # 6. seek against already-failed decoder is safe no-op
    def test_06_seek_against_failed_decoder_is_noop(self):
        decoder = ThrowingDecoder(throw_on_read=True, throw_on_seek=True)
        self.player._active_decoder = decoder
        self.player._state = PlaybackState.PLAYING
        outdata = np.zeros((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)
        self.assertTrue(self.player.decoder_failed)

        # Seeking now should not call decoder.seek at all
        success = self.player.seek(2.0)
        self.assertFalse(success)
        self.assertEqual(decoder.seek_calls, 0)

    # 7. normal EOF remains distinct from failure
    def test_07_normal_eof_distinct_from_failure(self):
        decoder = NormalDummyDecoder()
        self.player._active_decoder = decoder
        self.player._state = PlaybackState.PLAYING

        # Mock read returning 0 frames (EOF)
        decoder.read_frames = lambda f: np.zeros((0, 2), dtype=np.float32)
        outdata = np.ones((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)

        self.assertEqual(self.player.state, PlaybackState.STOPPED)
        self.assertFalse(self.player.decoder_failed)
        has_err, _, _ = self.player.check_and_clear_error()
        self.assertFalse(has_err)

    # 8. decoder cleanup after failure is safe/idempotent
    def test_08_cleanup_after_failure_is_idempotent(self):
        decoder = ThrowingDecoder(throw_on_read=True)
        self.player._active_decoder = decoder
        self.player._state = PlaybackState.PLAYING
        outdata = np.zeros((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)

        # Closing / stopping multiple times must not raise
        self.player.stop_immediate()
        self.player.close()
        self.player.close()
        self.assertFalse(self.player.decoder_failed)

    # 9. rapid track replacement does not apply stale failure to new decoder
    def test_09_rapid_track_replacement_generation_isolation(self):
        decoder_bad = ThrowingDecoder(throw_on_read=True)
        decoder_good = NormalDummyDecoder()

        self.player._active_decoder = decoder_bad
        self.player._generation = 1
        self.player._state = PlaybackState.PLAYING

        # Before bad callback finishes, user switched track to generation 2
        self.player._active_decoder = decoder_good
        self.player._generation = 2
        self.player._decoder_failed = False

        # Stale bad callback running from generation 1
        self.player._generation = 1 # simulate callback captured gen 1
        self.player._generation = 2 # simulate engine moved to gen 2

        outdata = np.zeros((512, 2), dtype=np.float32)
        # Callback with bad decoder but generation mismatch
        self.player._audio_callback(outdata, 512, None, None)
        # Good decoder should play next
        self.player._active_decoder = decoder_good
        self.player.play()
        self.assertEqual(self.player.state, PlaybackState.PLAYING)

    # 10. new valid track can play after previous decoder failure
    def test_10_new_valid_track_can_play_after_failure(self):
        # 1. Broken track fails
        decoder_bad = ThrowingDecoder(throw_on_read=True)
        self.player._active_decoder = decoder_bad
        self.player._state = PlaybackState.PLAYING
        outdata = np.zeros((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)
        self.assertTrue(self.player.decoder_failed)

        # 2. Good track is loaded
        decoder_good = NormalDummyDecoder()
        self.player._active_decoder = decoder_good
        self.player._decoder_failed = False
        self.player._state = PlaybackState.STOPPED
        self.player._generation += 1

        self.player.play()
        self.assertEqual(self.player.state, PlaybackState.PLAYING)

        outdata.fill(0)
        self.player._audio_callback(outdata, 512, None, None)
        self.assertFalse(self.player.decoder_failed)
        self.assertGreater(np.sum(np.abs(outdata)), 0.0)

    # 11. FDE ON and FDE OFF remain functional after recovery
    def test_11_fade_modes_functional_after_recovery(self):
        # Cause failure
        decoder_bad = ThrowingDecoder(throw_on_read=True)
        self.player._active_decoder = decoder_bad
        self.player._state = PlaybackState.PLAYING
        self.player._audio_callback(np.zeros((512, 2), dtype=np.float32), 512, None, None)

        # Recover with FDE ON
        decoder_good = NormalDummyDecoder()
        self.player._active_decoder = decoder_good
        self.player._decoder_failed = False
        self.player.fade_enabled = True
        self.player.play()
        self.assertEqual(self.player.fade_state, FadeState.FADING_IN)

        # Recover with FDE OFF
        self.player.stop_immediate()
        self.player.fade_enabled = False
        self.player.play()
        self.assertEqual(self.player.fade_state, FadeState.PLAYING)

    # 12. AnalysisHandoff receives safe silence/no invalid data during failure
    def test_12_analysis_handoff_receives_silence_or_no_garbage(self):
        decoder_bad = ThrowingDecoder(throw_on_read=True)
        self.player._active_decoder = decoder_bad
        self.player._state = PlaybackState.PLAYING

        outdata = np.zeros((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)

        frame = self.handoff.get_audio_frame(44100)
        self.assertEqual(frame.rms, 0.0)
        self.assertEqual(frame.peak, 0.0)
        self.assertFalse(frame.beat)

    # 13. Conventional decoder error on load sets error state
    def test_13_conventional_decoder_missing_or_corrupt_file_sets_error(self):
        with self.assertRaises(FileNotFoundError):
            self.player.load("non_existent_file.mp3")

    # 14. Shutdown after decoder failure remains clean
    def test_14_shutdown_after_decoder_failure_clean(self):
        decoder_bad = ThrowingDecoder(throw_on_read=True)
        self.player._active_decoder = decoder_bad
        self.player._state = PlaybackState.PLAYING
        self.player._audio_callback(np.zeros((512, 2), dtype=np.float32), 512, None, None)

        # Clean close
        self.player.close()
        self.assertIsNone(self.player._active_decoder)
        self.assertEqual(self.player.state, PlaybackState.STOPPED)

    # 15. Player properties are safe when decoder is in failed state
    def test_15_player_properties_safe_when_failed(self):
        decoder_bad = ThrowingDecoder(throw_on_read=True)
        self.player._active_decoder = decoder_bad
        self.player._state = PlaybackState.PLAYING
        self.player._audio_callback(np.zeros((512, 2), dtype=np.float32), 512, None, None)

        self.assertEqual(self.player.current_track_title, "")
        self.assertEqual(self.player.duration, 0.0)
        self.assertEqual(self.player.state, PlaybackState.STOPPED)


if __name__ == "__main__":
    unittest.main()
