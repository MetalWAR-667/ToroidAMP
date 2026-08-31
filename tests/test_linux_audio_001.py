"""
tests/test_linux_audio_001.py — Linux Audio Reliability & HP Baseline Validation

Focused regression tests for:
  1-4. select_output_device(): capability-based device policy (prefers a
       device literally named "pipewire" when present; falls back to
       PortAudio's own default everywhere else). Fully mocked -- no real
       audio hardware required, no platform-name branching asserted.
  5-6. PlayerEngine.play() stream configuration: blocksize=0 (PortAudio-
       negotiated), device resolved once and cached, not re-queried on
       every play().
  7-9. Vectorized fade-envelope computation is equivalent to the original
       per-sample loop for FADING_IN, FADING_OUT, and a fade completing
       mid-chunk.
  10-11. VoiceService/pyttsx3 engine lifecycle: the synthesis engine is
       kept alive (not explicitly deleted) for the ownership reasons
       documented in voice.py -- the fix for the Linux eSpeak
       ReferenceError/dangling-ctypes-callback lifecycle bug.
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np

from toroidamp.audio.player import PlayerEngine, PlaybackState, FadeState, select_output_device
from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.voice import VoiceService


class DummyDecoder:
    def __init__(self, sample_rate=44100, duration=10.0):
        self._sample_rate = sample_rate
        self._duration = duration

    def get_sample_rate(self) -> int:
        return self._sample_rate

    def get_duration(self) -> float:
        return self._duration

    def get_title(self) -> str:
        return "Test Track"

    def seek(self, sec: float) -> None:
        pass

    def read_frames(self, frames: int) -> np.ndarray:
        return np.ones((frames, 2), dtype=np.float32) * 0.1

    def close(self) -> None:
        pass


PIPEWIRE_ALSA_DEVICE_LIST = [
    {"name": "HDA Intel PCH: ALC3227 Analog (hw:0,0)", "max_output_channels": 2, "max_input_channels": 0},
    {"name": "sysdefault", "max_output_channels": 2, "max_input_channels": 0},
    {"name": "pipewire", "max_output_channels": 32, "max_input_channels": 32},
    {"name": "pulse", "max_output_channels": 32, "max_input_channels": 32},
    {"name": "default", "max_output_channels": 2, "max_input_channels": 0},
]

NO_PIPEWIRE_DEVICE_LIST = [
    {"name": "Speakers (Realtek Audio)", "max_output_channels": 2, "max_input_channels": 0},
    {"name": "Microsoft Sound Mapper - Output", "max_output_channels": 2, "max_input_channels": 0},
]


class TestSelectOutputDevice(unittest.TestCase):
    """Capability-based device policy -- fully mocked, no real hardware."""

    def test_01_prefers_device_literally_named_pipewire(self):
        idx = select_output_device(query_devices=lambda: PIPEWIRE_ALSA_DEVICE_LIST)
        self.assertEqual(idx, 2)
        self.assertEqual(PIPEWIRE_ALSA_DEVICE_LIST[idx]["name"], "pipewire")

    def test_02_falls_back_to_default_when_no_pipewire_device(self):
        # Windows-shaped device list -- must resolve to None (PortAudio
        # default), never raise, never guess based on platform name.
        idx = select_output_device(query_devices=lambda: NO_PIPEWIRE_DEVICE_LIST)
        self.assertIsNone(idx)

    def test_03_ignores_pipewire_named_device_with_no_output_channels(self):
        devices = [
            {"name": "pipewire", "max_output_channels": 0, "max_input_channels": 2},
            {"name": "default", "max_output_channels": 2, "max_input_channels": 0},
        ]
        idx = select_output_device(query_devices=lambda: devices)
        self.assertIsNone(idx)

    def test_04_device_enumeration_failure_falls_back_safely(self):
        def raising_query():
            raise OSError("PortAudio host API unavailable")
        idx = select_output_device(query_devices=raising_query)
        self.assertIsNone(idx)


class TestPlayerStreamConfiguration(unittest.TestCase):
    """PlayerEngine.play() stream construction policy."""

    def test_05_stream_uses_negotiated_blocksize_not_fixed_512(self):
        handoff = AnalysisHandoff()
        player = PlayerEngine(handoff=handoff)
        player._active_decoder = DummyDecoder()

        captured = {}
        real_output_stream = __import__("sounddevice").OutputStream

        class CapturingStream(real_output_stream):
            def __init__(self, *args, **kwargs):
                captured.update(kwargs)
                super().__init__(*args, **kwargs)

        with patch("toroidamp.audio.player.sd.OutputStream", CapturingStream):
            player.play()
        try:
            self.assertEqual(captured.get("blocksize"), 0)
        finally:
            player.stop_immediate()

    def test_06_output_device_resolved_once_and_cached(self):
        handoff = AnalysisHandoff()
        player = PlayerEngine(handoff=handoff)
        player._active_decoder = DummyDecoder()

        call_count = {"n": 0}

        def counting_select():
            call_count["n"] += 1
            return None

        with patch("toroidamp.audio.player.select_output_device", counting_select):
            player.play()
            player.pause()
            player.play()
        player.stop_immediate()

        self.assertEqual(call_count["n"], 1, "device selection must be resolved once, not re-queried on every play()")


class TestFadeEnvelopeVectorizedEquivalence(unittest.TestCase):
    """Vectorized envelope computation matches the original per-sample loop."""

    def _reference_loop(self, fade_state, fade_envelope, num_read, sample_rate=44100):
        """The original per-sample implementation, kept here only as an
        independent oracle to compare the vectorized version against."""
        fade_step = 1.0 / (0.200 * sample_rate)
        curve = np.empty((num_read, 1), dtype=np.float32)
        state = fade_state
        env = fade_envelope
        for i in range(num_read):
            if state == FadeState.FADING_IN:
                env = min(1.0, env + fade_step)
                if env >= 0.9999:
                    env = 1.0
                    state = FadeState.PLAYING
            elif state == FadeState.FADING_OUT:
                env = max(0.0, env - fade_step)
                if env <= 0.0001:
                    env = 0.0
                    state = FadeState.IDLE
            elif state == FadeState.PLAYING:
                env = 1.0
            else:
                env = 0.0
            curve[i, 0] = env
        return curve, state, env

    def _run_vectorized(self, fade_state, fade_envelope, num_read, sample_rate=44100):
        handoff = AnalysisHandoff()
        player = PlayerEngine(handoff=handoff)
        player._active_decoder = DummyDecoder(sample_rate=sample_rate)
        player._sample_rate = sample_rate
        player._state = PlaybackState.PLAYING
        player._fade_state = fade_state
        player._fade_envelope = fade_envelope
        player.volume = 1.0
        outdata = np.zeros((num_read, 2), dtype=np.float32)
        player._audio_callback(outdata, num_read, None, None)
        return outdata, player.fade_state, player._fade_envelope

    def test_07_fading_in_matches_reference_loop_mid_fade(self):
        ref_curve, ref_state, ref_env = self._reference_loop(FadeState.FADING_IN, 0.0, 4410)
        outdata, state, env = self._run_vectorized(FadeState.FADING_IN, 0.0, 4410)
        np.testing.assert_allclose(outdata[:, 0], (ref_curve[:, 0] * 0.1), atol=1e-4)
        self.assertEqual(state, ref_state)
        self.assertAlmostEqual(env, ref_env, places=4)

    def test_08_fading_out_matches_reference_loop_completing_within_chunk(self):
        ref_curve, ref_state, ref_env = self._reference_loop(FadeState.FADING_OUT, 1.0, 8820)
        outdata, state, env = self._run_vectorized(FadeState.FADING_OUT, 1.0, 8820)
        np.testing.assert_allclose(outdata[:, 0], (ref_curve[:, 0] * 0.1), atol=1e-4)
        self.assertEqual(state, ref_state)
        self.assertEqual(env, ref_env)

    def test_09_fading_in_completes_mid_chunk_state_transition(self):
        # 200ms fade at 44100Hz = 8820 frames; request slightly more than
        # that in one chunk so FADING_IN -> PLAYING happens mid-buffer.
        ref_curve, ref_state, ref_env = self._reference_loop(FadeState.FADING_IN, 0.0, 9000)
        outdata, state, env = self._run_vectorized(FadeState.FADING_IN, 0.0, 9000)
        np.testing.assert_allclose(outdata[:, 0], (ref_curve[:, 0] * 0.1), atol=1e-4)
        self.assertEqual(state, FadeState.PLAYING)
        self.assertEqual(state, ref_state)
        self.assertEqual(env, ref_env)


class TestVoiceServiceEngineLifecycle(unittest.TestCase):
    """
    Linux TTS fix: pyttsx3's eSpeak driver registers its synthesis-progress
    ctypes callback against a weak reference to the engine. The engine must
    stay strongly referenced for its natural lifetime instead of being
    explicitly `del`eted right after runAndWait() -- doing so raced a
    trailing native callback against garbage collection, surfacing as
    `ReferenceError: weakly-referenced object no longer exists` on Linux.
    Fully mocked (no real pyttsx3/espeak dependency, no audio hardware).
    """

    def _make_mock_engine(self):
        engine = MagicMock()
        engine.getProperty.return_value = []  # no voices to search through
        return engine

    def test_10_engine_is_retained_after_synthesis_not_deleted(self):
        vs = VoiceService()
        mock_engine = self._make_mock_engine()

        with patch("toroidamp.audio.voice.pyttsx3.init", return_value=mock_engine):
            with patch("toroidamp.audio.voice.os.path.getsize", return_value=0):
                # getsize=0 skips the playback branch entirely -- this test
                # only cares whether the engine reference survives
                # synthesis, not whether real audio hardware is available
                # to play the (mocked, nonexistent) WAV.
                vs._synthesize_and_play("test phrase")

        self.assertIs(
            vs._current_engine, mock_engine,
            "the synthesis engine must remain referenced after synthesis, not be explicitly deleted",
        )
        mock_engine.runAndWait.assert_called_once()

    def test_11_no_explicit_del_of_the_engine_in_source(self):
        # Structural regression guard: an explicit `del engine` statement
        # immediately after runAndWait() is exactly the bug that was
        # fixed -- assert no such *statement* remains (matched against
        # actual code lines, not the explanatory comment referencing the
        # old bug by name), so a future edit can't silently reintroduce it.
        import re
        from pathlib import Path
        src = Path(__file__).resolve().parent.parent.joinpath(
            "src", "toroidamp", "audio", "voice.py"
        ).read_text(encoding="utf-8")
        code_lines = [line for line in src.splitlines() if not line.strip().startswith("#")]
        self.assertFalse(
            any(re.match(r"\s*del\s+engine\b", line) for line in code_lines),
            "found a live 'del engine' statement -- this reintroduces the Linux TTS lifecycle bug",
        )


if __name__ == "__main__":
    unittest.main()
