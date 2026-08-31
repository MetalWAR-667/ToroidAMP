"""
ToroidAMP - LINUX-TTS-001 Test Suite
Validation of Linux Startup Voice Deferral Policy, Windows Voice Preservation,
and Non-Blocking Startup Lifecycle.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock

from toroidamp.audio.voice import VoiceService, TTS_AVAILABLE


class TestLinuxTtsDeferralPolicy(unittest.TestCase):
    """Tests the Linux startup TTS deferral policy and Windows preservation."""

    def test_01_linux_platform_skips_startup_voice_cleanly(self):
        vs = VoiceService()
        with patch("toroidamp.audio.voice.sys.platform", "linux"):
            with patch("toroidamp.audio.voice.logger") as mock_logger:
                vs.speak_startup_phrase_async()

        self.assertIsNone(vs._thread)
        self.assertFalse(vs.is_speaking)
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        self.assertTrue(
            any("Startup voice disabled on Linux" in c for c in info_calls),
            f"Expected Linux deferral log, got: {info_calls}",
        )

    def test_02_windows_platform_triggers_voice_thread(self):
        vs = VoiceService()
        with patch("toroidamp.audio.voice.sys.platform", "win32"):
            with patch.object(vs, "_synthesize_and_play") as mock_synth:
                vs.speak_startup_phrase_async("Windows test")
                self.assertIsNotNone(vs._thread)
                if vs._thread is not None:
                    vs._thread.join(timeout=2.0)
                mock_synth.assert_called_once_with("Windows test")

    def test_03_no_false_success_logged_on_linux(self):
        vs = VoiceService()
        with patch("toroidamp.audio.voice.sys.platform", "linux"):
            with patch("toroidamp.audio.voice.logger") as mock_logger:
                vs.speak_startup_phrase_async()

        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        self.assertFalse(
            any("playback completed" in c for c in info_calls),
            "Must not emit a false playback completed log on Linux",
        )

    def test_04_core_synthesize_and_play_method_remains_available(self):
        vs = VoiceService()
        mock_engine = MagicMock()
        mock_engine.getProperty.return_value = []
        with patch("toroidamp.audio.voice.pyttsx3.init", return_value=mock_engine):
            with patch("toroidamp.audio.voice.os.path.getsize", return_value=0):
                vs._synthesize_and_play("direct call")
        mock_engine.runAndWait.assert_called_once()
        self.assertFalse(vs.is_speaking)

    def test_05_startup_remains_instant_and_nonblocking(self):
        import time
        vs = VoiceService()
        t0 = time.perf_counter()
        vs.speak_startup_phrase_async()
        t1 = time.perf_counter()
        self.assertLess(t1 - t0, 0.05, "Startup voice call on Linux must return almost instantaneously (<50ms)")


if __name__ == "__main__":
    unittest.main()
