"""
RC-POLISH-001 Automated Test Suite — Playback Fade, Always-Alive Marquee,
Readability Tokens, and M3U Load/Save.
"""

import os
import tempfile
import unittest
import numpy as np
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from toroidamp.audio.player import PlayerEngine, PlaybackState, FadeState
from toroidamp.audio.playlist import PlaylistManager, PlaylistItem
from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.ui.marquee import MarqueeLabel
from toroidamp.ui.theme import ThemeManager, ThemePalette
from toroidamp.ui.chassis import UnifiedChassis
from toroidamp.ui.modules.playlist_module import PlaylistModule
from toroidamp.ui.modules.visualizer_module import VisualizerModule
from toroidamp.ui.fullscreen import RetinaMeltWindow


class DummyDecoder:
    def __init__(self, sample_rate=44100, duration=10.0, title="Test Track"):
        self._sample_rate = sample_rate
        self._duration = duration
        self._title = title
        self._pos = 0.0

    def get_sample_rate(self) -> int:
        return self._sample_rate

    def get_duration(self) -> float:
        return self._duration

    def get_title(self) -> str:
        return self._title

    def seek(self, sec: float) -> None:
        self._pos = sec

    def read_frames(self, frames: int) -> np.ndarray:
        # Return constant 1.0 stereo frames
        return np.ones((frames, 2), dtype=np.float32)

    def close(self) -> None:
        pass


class TestRCPolish001(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.handoff = AnalysisHandoff()
        self.theme_manager = ThemeManager.get_instance()
        self.theme_manager.set_theme("default")

    def tearDown(self):
        if self.theme_manager.active_theme_id != "default":
            self.theme_manager.set_theme("default")

    # =========================================================================
    # PART A — PLAYBACK FADE-IN / FADE-OUT
    # =========================================================================

    def test_01_fade_in_starts_at_zero_and_reaches_full_gain(self):
        player = PlayerEngine(handoff=self.handoff)
        dummy = DummyDecoder()
        player._active_decoder = dummy
        player._sample_rate = 44100
        player._state = PlaybackState.PLAYING
        player._fade_state = FadeState.FADING_IN
        player._fade_envelope = 0.0
        player.volume = 1.0

        # Read 100 ms (4410 frames) chunk - halfway through 200 ms fade
        outdata = np.zeros((4410, 2), dtype=np.float32)
        player._audio_callback(outdata, 4410, None, None)

        # Initial frames should be near 0
        self.assertAlmostEqual(outdata[0, 0], 0.0, delta=0.01)
        # 4410th frame should be approx 0.5
        self.assertAlmostEqual(outdata[-1, 0], 0.5, delta=0.02)
        self.assertEqual(player.fade_state, FadeState.FADING_IN)

        # Read second 100 ms (4410 frames) chunk - finishes 200 ms fade
        outdata2 = np.zeros((4410, 2), dtype=np.float32)
        player._audio_callback(outdata2, 4410, None, None)
        self.assertAlmostEqual(outdata2[-1, 0], 1.0, delta=0.01)
        self.assertEqual(player.fade_state, FadeState.PLAYING)

    def test_02_fade_out_reaches_silence_cleanly(self):
        player = PlayerEngine(handoff=self.handoff)
        dummy = DummyDecoder()
        player._active_decoder = dummy
        player._sample_rate = 44100
        player._state = PlaybackState.PLAYING
        player._fade_state = FadeState.FADING_OUT
        player._fade_envelope = 1.0
        player.volume = 1.0

        # 200 ms = 8820 frames
        outdata = np.zeros((8820, 2), dtype=np.float32)
        player._audio_callback(outdata, 8820, None, None)

        self.assertAlmostEqual(outdata[0, 0], 1.0, delta=0.01)
        self.assertAlmostEqual(outdata[-1, 0], 0.0, delta=0.01)
        self.assertEqual(player.fade_state, FadeState.IDLE)
        self.assertEqual(player.state, PlaybackState.STOPPED)

    def test_03_user_volume_remains_independent_of_fade(self):
        player = PlayerEngine(handoff=self.handoff)
        dummy = DummyDecoder()
        player._active_decoder = dummy
        player._sample_rate = 44100
        player._state = PlaybackState.PLAYING
        player._fade_state = FadeState.PLAYING
        player._fade_envelope = 1.0
        player.volume = 0.4

        outdata = np.zeros((512, 2), dtype=np.float32)
        player._audio_callback(outdata, 512, None, None)
        # Should match exact user volume
        self.assertAlmostEqual(outdata[0, 0], 0.4, places=4)

    def test_04_rapid_play_stop_does_not_get_stuck(self):
        player = PlayerEngine(handoff=self.handoff)
        dummy = DummyDecoder()
        player._active_decoder = dummy
        player.play()
        self.assertEqual(player.state, PlaybackState.PLAYING)
        self.assertEqual(player.fade_state, FadeState.FADING_IN)

        player.stop_immediate()
        self.assertEqual(player.state, PlaybackState.STOPPED)
        self.assertEqual(player.fade_state, FadeState.IDLE)

    def test_05_track_load_stops_immediate_without_bleed(self):
        player = PlayerEngine(handoff=self.handoff)
        player._state = PlaybackState.PLAYING
        player._fade_state = FadeState.PLAYING
        player._fade_envelope = 1.0
        # Calling stop_immediate resets everything
        player.stop_immediate()
        self.assertEqual(player.state, PlaybackState.STOPPED)
        self.assertEqual(player._fade_envelope, 0.0)

    # =========================================================================
    # PART B — ALWAYS-ALIVE TITLE MARQUEE
    # =========================================================================

    def test_06_overflowing_title_animates(self):
        marquee = MarqueeLabel()
        marquee.resize(100, 20)
        marquee.set_marquee_text("A Very Long Track Title That Definitely Exceeds Visible Width")
        self.assertGreater(marquee._overflow_px, 0)
        self.assertGreater(marquee._max_offset, 0)

    def test_07_short_fitting_title_animates(self):
        marquee = MarqueeLabel()
        marquee.resize(400, 20)
        marquee.set_marquee_text("Track 1")
        self.assertEqual(marquee._overflow_px, 0)
        # Short text must now have positive travel target
        self.assertGreater(marquee._max_offset, 0)
        self.assertLessEqual(marquee._max_offset, MarqueeLabel.NON_OVERFLOW_TRAVEL_PX)

    def test_08_empty_text_stays_static(self):
        marquee = MarqueeLabel()
        marquee.resize(400, 20)
        marquee.set_marquee_text("")
        self.assertEqual(marquee._max_offset, 0)
        self.assertEqual(marquee._state, MarqueeLabel._STATIC)

    def test_09_mini_normal_retina_use_same_marquee_contract(self):
        chassis = UnifiedChassis()
        melt = RetinaMeltWindow()
        # All three instantiate MarqueeLabel
        self.assertIsInstance(chassis.normal_title_marquee, MarqueeLabel)
        self.assertIsInstance(chassis.mini_title_marquee, MarqueeLabel)
        self.assertIsInstance(melt.hud_marquee, MarqueeLabel)

    # =========================================================================
    # PART C — PANEL TEXT READABILITY PASS
    # =========================================================================

    def test_10_readability_tokens_resolve_to_high_contrast_shades(self):
        def_pal = self.theme_manager.get_theme("default").palette
        cy_pal = self.theme_manager.get_theme("cyber_yellow").palette

        # Both DEFAULT and CYBER YELLOW secondary text must be clear bright light shades
        self.assertIn(def_pal.text_secondary.lower(), ["#e2e8f0", "#ffffff"])
        self.assertIn(def_pal.list_item_text.lower(), ["#e2e8f0", "#ffffff"])
        self.assertIn(cy_pal.text_secondary.lower(), ["#f3f4f6", "#ffffff"])
        self.assertIn(cy_pal.list_item_text.lower(), ["#f3f4f6", "#ffffff"])

    def test_11_playlist_module_uses_theme_readable_list_color(self):
        pl_mgr = PlaylistManager()
        pl_mod = PlaylistModule(pl_mgr)
        self.theme_manager.set_theme("default")
        self.assertIn("#e2e8f0", pl_mod.list_widget.styleSheet())

        self.theme_manager.set_theme("cyber_yellow")
        self.assertIn("#f3f4f6", pl_mod.list_widget.styleSheet())

    # =========================================================================
    # PART D — M3U LOAD / SAVE
    # =========================================================================

    def test_12_m3u_save_and_load_roundtrip_with_unicode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "track_alpha.mp3"
            f2 = Path(tmpdir) / "track_日本語.mp3"
            f1.write_bytes(b"dummy")
            f2.write_bytes(b"dummy")

            m3u_file = Path(tmpdir) / "test_playlist.m3u8"

            mgr1 = PlaylistManager()
            mgr1.add_file(str(f1), title="Alpha Track", duration=120.0)
            mgr1.add_file(str(f2), title="Unicode ♫ Track", duration=180.0)

            mgr1.save_m3u(str(m3u_file))
            self.assertTrue(m3u_file.exists())

            mgr2 = PlaylistManager()
            mgr2.load_m3u(str(m3u_file))

            self.assertEqual(len(mgr2), 2)
            self.assertEqual(mgr2.items[0].title, "Alpha Track")
            self.assertEqual(mgr2.items[1].title, "Unicode ♫ Track")
            self.assertEqual(mgr2.items[0].filepath, str(f1.resolve()))
            self.assertEqual(mgr2.items[1].filepath, str(f2.resolve()))

    def test_13_m3u_empty_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            m3u_file = Path(tmpdir) / "empty.m3u8"
            mgr = PlaylistManager()
            mgr.save_m3u(str(m3u_file))
            self.assertTrue(m3u_file.exists())
            content = m3u_file.read_text(encoding="utf-8")
            self.assertEqual(content.strip(), "#EXTM3U")

    def test_14_m3u_load_nonexistent_raises_or_handles(self):
        mgr = PlaylistManager()
        with self.assertRaises(FileNotFoundError):
            mgr.load_m3u("non_existent_file.m3u")

    # =========================================================================
    # PART E — FADE A/B CONTROL & PERSISTENCE
    # =========================================================================

    def test_15_fade_enabled_defaults_to_true(self):
        player = PlayerEngine(handoff=self.handoff)
        self.assertTrue(player.fade_enabled)

    def test_16_disabled_fade_bypasses_envelope_completely(self):
        player = PlayerEngine(handoff=self.handoff)
        dummy = DummyDecoder()
        player._active_decoder = dummy
        player._sample_rate = 44100
        player.fade_enabled = False
        player.volume = 0.75
        player.play()

        try:
            self.assertEqual(player.state, PlaybackState.PLAYING)
            self.assertEqual(player.fade_state, FadeState.PLAYING)

            outdata = np.zeros((512, 2), dtype=np.float32)
            player._audio_callback(outdata, 512, None, None)
            # First sample should immediately be at full user volume (0.75) without ramping
            self.assertAlmostEqual(outdata[0, 0], 0.75, places=4)
            self.assertAlmostEqual(outdata[-1, 0], 0.75, places=4)
        finally:
            # player.play() opens a real sounddevice OutputStream with a
            # background PortAudio callback thread (unlike every other test
            # in this file, which drives player._audio_callback() directly
            # without a real stream). Left open, that native thread keeps
            # calling back into the interpreter indefinitely, racing later
            # tests' Qt/GL work on the main thread -- this was tracked down
            # as the cause of an intermittent native crash (access
            # violation on Windows, segfault on Linux) deep in unrelated
            # code several tests later in a full-suite run.
            player.stop_immediate()

    def test_17_disabled_stop_terminates_immediately(self):
        player = PlayerEngine(handoff=self.handoff)
        dummy = DummyDecoder()
        player._active_decoder = dummy
        player.fade_enabled = False
        player.play()
        self.assertEqual(player.state, PlaybackState.PLAYING)

        player.stop()
        self.assertEqual(player.state, PlaybackState.STOPPED)
        self.assertEqual(player.fade_state, FadeState.IDLE)

    def test_18_session_persistence_roundtrip_fade_enabled(self):
        from toroidamp.session import SessionManager, SessionState
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Path(tmpdir) / "session.json"
            sm = SessionManager(custom_path=str(sp))
            sm.state.fade_enabled = False
            sm.save()

            sm2 = SessionManager(custom_path=str(sp))
            loaded = sm2.load()
            self.assertFalse(loaded.fade_enabled)

    def test_19_missing_session_value_falls_back_to_true(self):
        from toroidamp.session import SessionManager
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Path(tmpdir) / "legacy_session.json"
            sp.write_text('{"version": 1, "scale": "normal", "volume": 0.8}', encoding="utf-8")
            sm = SessionManager(custom_path=str(sp))
            loaded = sm.load()
            self.assertTrue(loaded.fade_enabled)

    def test_20_chassis_fde_button_exists_and_toggles(self):
        chassis = UnifiedChassis()
        self.assertTrue(hasattr(chassis, "chip_fade"))
        self.assertTrue(chassis.chip_fade.isCheckable())
        self.assertTrue(chassis.chip_fade.isChecked())
        self.assertEqual(chassis.chip_fade.text(), "FDE")

    def test_21_chassis_fade_signal_connected(self):
        chassis = UnifiedChassis()
        toggled_states = []
        chassis.toggle_fade_clicked.connect(toggled_states.append)
        chassis.chip_fade.setChecked(False)
        self.assertEqual(toggled_states, [False])
        chassis.chip_fade.setChecked(True)
        self.assertEqual(toggled_states, [False, True])


if __name__ == "__main__":
    unittest.main()
