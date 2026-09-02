"""
tests/test_dsp_001.py — Automated Test Suite for DSP-001

Covers:
  DSP-001A — Transport Micro-Fades (Pause, Stop, Seek micro-fades, text/analysis safety)
  DSP-001B — Gapless & Crossfade Playback (Equal-power gain law, mixed analysis, edge cases)
  DSP-001C — Loudness / Level Normalization (ReplayGain, fallback leveling, safety limiter)
"""

import math
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.player import PlayerEngine, PlaybackState, FadeState

from toroidamp.audio.playlist import PlaylistManager
from toroidamp.audio.replaygain import (
    parse_replaygain_tags,
    calculate_fallback_leveling,
    estimate_track_gain,
    apply_safety_limiter
)
from toroidamp.session import SessionManager, SessionState


class DummyDecoder:
    """Deterministic dummy decoder for frame-accurate DSP testing."""

    def __init__(self, duration: float = 10.0, sample_rate: int = 44100, amplitude: float = 0.5):
        self._sr = sample_rate
        self._duration = duration
        self._amplitude = amplitude
        self._pos_frames = 0
        self._total_frames = int(duration * sample_rate)
        self._closed = False
        self._seek_count = 0

    def load(self, filepath: str) -> None:
        self._pos_frames = 0
        self._closed = False

    def read_frames(self, num_frames: int) -> np.ndarray:
        if self._closed or self._pos_frames >= self._total_frames:
            return np.zeros((0, 2), dtype=np.float32)

        available = min(num_frames, self._total_frames - self._pos_frames)
        # Constant amplitude or slight sine wave
        frames = np.full((available, 2), self._amplitude, dtype=np.float32)
        self._pos_frames += available
        return frames

    def seek(self, position_seconds: float) -> None:
        self._seek_count += 1
        self._pos_frames = max(0, min(self._total_frames, int(position_seconds * self._sr)))

    def get_duration(self) -> float:
        return self._duration

    def get_title(self) -> str:
        return "Dummy Track"

    def get_sample_rate(self) -> int:
        return self._sr

    def close(self) -> None:
        self._closed = True


class TestDSP001ATransportMicroFades(unittest.TestCase):
    """DSP-001A: 25ms transport micro-fades for pause, resume, stop, and seek."""

    def setUp(self):
        self.handoff = AnalysisHandoff(2048)
        self.player = PlayerEngine(self.handoff)
        self.decoder = DummyDecoder(duration=5.0, sample_rate=44100, amplitude=0.8)
        self.player._active_decoder = self.decoder
        self.player._sample_rate = 44100
        self.player._state = PlaybackState.PLAYING
        self.player._fade_state = FadeState.PLAYING
        self.player._fade_envelope = 1.0

    def tearDown(self):
        self.player.close()

    def test_01_micro_fade_constants(self):

        self.assertEqual(self.player.MICRO_FADE_DURATION_SECONDS, 0.025)
        self.assertEqual(self.player.FADE_DURATION_SECONDS, 0.200)

    def test_02_pause_triggers_micro_fade_out(self):
        self.player.pause()
        self.assertTrue(self.player._pause_requested)
        self.assertEqual(self.player._fade_state, FadeState.FADING_OUT)

        # Execute audio callback during fade-out
        outdata = np.zeros((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)

        # Envelope should decrease smoothly
        self.assertLess(self.player._fade_envelope, 1.0)
        self.assertGreaterEqual(self.player._fade_envelope, 0.0)

        # Complete fade out (call callback enough times for 25ms = 1102 samples)
        for _ in range(4):
            self.player._audio_callback(outdata, 512, None, None)

        self.assertEqual(self.player.state, PlaybackState.PAUSED)
        self.assertEqual(self.player._fade_state, FadeState.IDLE)
        self.assertEqual(self.player._fade_envelope, 0.0)

    def test_03_resume_triggers_micro_fade_in(self):
        # Set to PAUSED
        self.player._state = PlaybackState.PAUSED
        self.player._fade_state = FadeState.IDLE
        self.player._fade_envelope = 0.0

        self.player.play()
        self.assertEqual(self.player.state, PlaybackState.PLAYING)
        self.assertEqual(self.player._fade_state, FadeState.FADING_IN)

        outdata = np.zeros((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)
        self.assertGreater(self.player._fade_envelope, 0.0)

    def test_04_user_stop_never_triggers_natural_eof(self):
        self.player.stop()
        outdata = np.zeros((512, 2), dtype=np.float32)
        for _ in range(25):
            self.player._audio_callback(outdata, 512, None, None)

        self.assertEqual(self.player.state, PlaybackState.STOPPED)
        self.assertFalse(self.player.consume_natural_eof())

    def test_05_seek_applies_micro_fade_and_coalesces(self):
        # Multiple rapid seek calls while playing
        self.player.seek(1.0)
        self.player.seek(2.5)
        self.player.seek(3.0)

        self.assertEqual(self.player._pending_seek_seconds, 3.0)
        self.assertEqual(self.decoder._seek_count, 0)  # Not applied until callback runs

        outdata = np.zeros((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)

        self.assertEqual(self.decoder._seek_count, 1)
        self.assertIsNone(self.player._pending_seek_seconds)
        self.assertFalse(np.isnan(outdata).any())
        self.assertFalse(np.isinf(outdata).any())

    def test_06_analysis_handoff_receives_fade_envelope_pre_user_volume(self):
        self.player.volume = 0.1  # Low user volume
        self.player._fade_state = FadeState.PLAYING
        self.player._fade_envelope = 1.0

        outdata = np.zeros((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)

        # Output data was scaled by user volume (0.8 * 0.1 = 0.08)
        self.assertAlmostEqual(float(outdata[0, 0]), 0.08, places=2)

        # Analysis handoff received pre-user-volume signal (0.8)
        frame = self.handoff.get_audio_frame(44100)
        self.assertAlmostEqual(frame.peak, 0.8, places=2)


class TestDSP001BGaplessAndCrossfade(unittest.TestCase):
    """DSP-001B: Seamless gapless and equal-power crossfade transitions."""

    def setUp(self):
        self.handoff = AnalysisHandoff(2048)
        self.player = PlayerEngine(self.handoff)
        self.dec_a = DummyDecoder(duration=5.0, sample_rate=44100, amplitude=0.6)
        self.dec_b = DummyDecoder(duration=5.0, sample_rate=44100, amplitude=0.4)
        self.player._active_decoder = self.dec_a
        self.player._sample_rate = 44100
        self.player._state = PlaybackState.PLAYING
        self.player._fade_state = FadeState.PLAYING
        self.player._fade_envelope = 1.0

    def tearDown(self):
        self.player.close()

    def test_01_crossfade_duration_property_clamp(self):

        self.player.crossfade_duration = 1.5
        self.assertEqual(self.player.crossfade_duration, 1.5)

        self.player.crossfade_duration = -1.0
        self.assertEqual(self.player.crossfade_duration, 0.0)

        self.player.crossfade_duration = 10.0
        self.assertEqual(self.player.crossfade_duration, 5.0)

    def test_02_equal_power_gain_law_math(self):
        # Verify cos^2(p * pi/2) + sin^2(p * pi/2) == 1.0
        progress = np.linspace(0.0, 1.0, 100, dtype=np.float32)
        g_out = np.cos(progress * (math.pi / 2.0))
        g_in = np.sin(progress * (math.pi / 2.0))
        power = g_out ** 2 + g_in ** 2
        np.testing.assert_allclose(power, 1.0, atol=1e-6)

    def test_03_active_crossfade_mixing_and_analysis(self):
        # Manually initiate crossfade state
        self.player._outgoing_decoder = self.dec_a
        self.player._active_decoder = self.dec_b
        total_frames = 44100  # 1.0 second crossfade
        self.player._crossfade_total_frames = total_frames
        self.player._crossfade_remaining_frames = total_frames

        outdata = np.zeros((512, 2), dtype=np.float32)
        self.player._audio_callback(outdata, 512, None, None)

        self.assertLess(self.player._crossfade_remaining_frames, total_frames)
        self.assertFalse(np.isnan(outdata).any())
        self.assertFalse(np.isinf(outdata).any())

        # Complete crossfade
        while self.player._crossfade_remaining_frames > 0:
            self.player._audio_callback(outdata, 512, None, None)

        self.assertIsNone(self.player._outgoing_decoder)

    def test_04_stop_during_crossfade_cleans_up_both_decoders(self):
        self.player._outgoing_decoder = self.dec_a
        self.player._active_decoder = self.dec_b
        self.player._crossfade_total_frames = 44100
        self.player._crossfade_remaining_frames = 44100

        self.player.stop_immediate()
        self.assertEqual(self.player.state, PlaybackState.STOPPED)
        self.assertIsNone(self.player._outgoing_decoder)
        self.assertTrue(self.dec_a._closed)


class TestDSP001CLoudnessNormalizationAndLimiter(unittest.TestCase):
    """DSP-001C: ReplayGain parsing, fallback leveling, and soft safety limiter."""

    def test_01_replaygain_tag_parsing(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            # Write a simulated ID3 comment containing ReplayGain
            f.write(b"ID3\x03\x00\x00\x00\x00\x10\x00REPLAYGAIN_TRACK_GAIN = -4.50 dB\x00")
            tmp_path = f.name

        try:
            gain = parse_replaygain_tags(tmp_path)
            self.assertIsNotNone(gain)
            expected = math.pow(10.0, -4.5 / 20.0)
            self.assertAlmostEqual(gain, expected, places=3)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_02_fallback_leveling_gain_clamping(self):
        # High RMS signal (0.50 -> -6 dBFS) vs target -16 dBFS -> gain should be -10 clamped to -6 dB
        loud_pcm = np.full((1000, 2), 0.50, dtype=np.float32)
        gain_loud = calculate_fallback_leveling(loud_pcm, target_db=-16.0)
        self.assertAlmostEqual(gain_loud, math.pow(10.0, -6.0 / 20.0), places=3)

        # Quiet RMS signal (0.01 -> -40 dBFS) -> gain should be +24 clamped to +6 dB
        quiet_pcm = np.full((1000, 2), 0.01, dtype=np.float32)
        gain_quiet = calculate_fallback_leveling(quiet_pcm, target_db=-16.0)
        self.assertAlmostEqual(gain_quiet, math.pow(10.0, +6.0 / 20.0), places=3)

        # Silence handling
        silence_pcm = np.zeros((1000, 2), dtype=np.float32)
        self.assertEqual(calculate_fallback_leveling(silence_pcm), 1.0)
        self.assertEqual(calculate_fallback_leveling(None), 1.0)

    def test_03_soft_safety_limiter_transparency_and_bounds(self):
        # 1. Normal signals <= 0.95 remain 100% untouched
        normal_sig = np.array([[-0.5, 0.2], [0.8, -0.9]], dtype=np.float32)
        limited_normal = apply_safety_limiter(normal_sig)
        np.testing.assert_array_equal(normal_sig, limited_normal)

        # 2. Overs > 1.0 are smoothly limited strictly < 1.0
        hot_sig = np.array([[1.5, -2.0], [3.5, -5.0]], dtype=np.float32)
        limited_hot = apply_safety_limiter(hot_sig)
        self.assertTrue((np.abs(limited_hot) < 1.0).all())
        self.assertTrue((np.abs(limited_hot) >= 0.95).all())

    def test_04_session_persistence_for_dsp_settings(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            session_path = os.path.join(tmp_dir, "session.json")
            sm = SessionManager(custom_path=session_path)

            sm.state.crossfade_duration = 1.5
            sm.state.normalization_enabled = True
            sm.save()

            # Reload and verify
            sm2 = SessionManager(custom_path=session_path)
            loaded = sm2.load()
            self.assertEqual(loaded.crossfade_duration, 1.5)
            self.assertTrue(loaded.normalization_enabled)


if __name__ == "__main__":
    unittest.main()
