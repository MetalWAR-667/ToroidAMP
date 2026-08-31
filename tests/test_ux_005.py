"""
tests/test_ux_005.py — v0.666 NORMAL UX & Interaction Polish

Focused regression tests for:
  1-3. Volume-independent audio analysis/reactivity (Task 4): the
       AnalysisHandoff must reflect musical content, not the user's
       listening volume; true silence (fade-out complete) must still
       register as silence.
  4-6. Playlist multi-selection & bulk removal (Task 5): Ctrl/Shift
       selection semantics, bulk delete, and playback identity surviving
       an unrelated bulk operation.
  7. Version consistency (Task 7): a single authoritative version source.
"""

import sys
import unittest
import numpy as np

from PySide6.QtWidgets import QApplication, QAbstractItemView

from toroidamp.audio.player import PlayerEngine, PlaybackState
from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.playlist import PlaylistManager, PlaylistItem
from toroidamp.ui.modules.playlist_module import PlaylistModule


class ToneDecoder:
    """Deterministic 440 Hz tone decoder — non-trivial, reproducible signal."""

    def __init__(self, sample_rate=44100, duration=10.0):
        self._sample_rate = sample_rate
        self._duration = duration
        self._pos = 0.0
        self._n = 0

    def get_sample_rate(self) -> int:
        return self._sample_rate

    def get_duration(self) -> float:
        return self._duration

    def get_title(self) -> str:
        return "Tone"

    def seek(self, sec: float) -> None:
        self._pos = sec
        self._n = int(sec * self._sample_rate)

    def read_frames(self, frames: int) -> np.ndarray:
        t = (self._n + np.arange(frames)) / float(self._sample_rate)
        self._n += frames
        tone = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
        return np.stack([tone, tone], axis=1)

    def close(self) -> None:
        pass


class TestVolumeIndependentReactivity(unittest.TestCase):
    """Task 4: AnalysisHandoff must not be scaled by PlayerEngine.volume."""

    def _rms_after_callbacks(self, volume: float, fade_enabled: bool, n_chunks: int = 40) -> float:
        handoff = AnalysisHandoff()
        player = PlayerEngine(handoff=handoff)
        player._active_decoder = ToneDecoder()
        player._sample_rate = 44100
        player.fade_enabled = fade_enabled
        player.volume = volume
        player._state = PlaybackState.PLAYING
        player._fade_state = player._fade_state.__class__.PLAYING if not fade_enabled else player._fade_state
        if fade_enabled:
            # Skip past the 200ms fade-in ramp so steady-state amplitude is compared.
            from toroidamp.audio.player import FadeState
            player._fade_state = FadeState.PLAYING
            player._fade_envelope = 1.0

        outdata = np.zeros((512, 2), dtype=np.float32)
        for _ in range(n_chunks):
            player._audio_callback(outdata, 512, None, None)

        frame = handoff.get_audio_frame(sr=44100)
        return frame.rms

    def test_01_loud_and_quiet_volume_produce_same_reactivity_fade_disabled(self):
        rms_loud = self._rms_after_callbacks(volume=1.0, fade_enabled=False)
        rms_quiet = self._rms_after_callbacks(volume=0.05, fade_enabled=False)
        self.assertGreater(rms_loud, 0.05, "sanity: loud volume should register real energy")
        self.assertAlmostEqual(
            rms_loud, rms_quiet, delta=0.02,
            msg=f"Analysis RMS must not track player volume: loud={rms_loud} quiet={rms_quiet}"
        )

    def test_02_loud_and_quiet_volume_produce_same_reactivity_fade_enabled(self):
        rms_loud = self._rms_after_callbacks(volume=1.0, fade_enabled=True)
        rms_quiet = self._rms_after_callbacks(volume=0.05, fade_enabled=True)
        self.assertAlmostEqual(
            rms_loud, rms_quiet, delta=0.02,
            msg=f"Analysis RMS must not track player volume: loud={rms_loud} quiet={rms_quiet}"
        )

    def test_03_true_silence_from_fade_out_registers_as_silence(self):
        from toroidamp.audio.player import FadeState
        handoff = AnalysisHandoff()
        player = PlayerEngine(handoff=handoff)
        player._active_decoder = ToneDecoder()
        player._sample_rate = 44100
        player.fade_enabled = True
        player.volume = 1.0
        player._state = PlaybackState.PLAYING
        player._fade_state = FadeState.FADING_OUT
        player._fade_envelope = 1.0

        # 200ms fade duration at 44100 Hz = 8820 frames for the envelope to
        # reach 0; request enough extra frames in this single callback that
        # the tail (after the ramp completes) alone exceeds the analysis
        # ring buffer size (2048 frames), so get_audio_frame() sees only
        # post-fade, fully-silent samples.
        n_frames = 8820 + handoff.buffer_frames + 512
        outdata = np.zeros((n_frames, 2), dtype=np.float32)
        player._audio_callback(outdata, n_frames, None, None)

        frame = handoff.get_audio_frame(sr=44100)
        self.assertLess(frame.rms, 0.05, f"Faded-out silence must register as silence, got rms={frame.rms}")


class TestPlaylistMultiSelection(unittest.TestCase):
    """Task 5: bulk removal preserves ordering and playback identity."""

    def _manager(self, n=10):
        pm = PlaylistManager()
        for i in range(n):
            pm.add_file(f"C:/music/track_{i:02d}.mp3")
        return pm

    def test_04_bulk_remove_by_index_preserves_remaining_order(self):
        pm = self._manager(10)
        # Remove indices 2, 4, 6 (descending to keep indices valid as we go).
        for idx in sorted([2, 4, 6], reverse=True):
            pm.remove_at(idx)
        remaining = [item.title for item in pm.items]
        expected = [f"track_{i:02d}" for i in [0, 1, 3, 5, 7, 8, 9]]
        self.assertEqual(remaining, expected)

    def test_05_bulk_remove_does_not_disturb_current_track_identity(self):
        pm = self._manager(10)
        pm.current_index = 8  # "track_08"
        current_title_before = pm.current_item.title

        # Bulk-remove tracks before the current one.
        for idx in sorted([0, 1, 2], reverse=True):
            pm.remove_at(idx)

        self.assertEqual(pm.current_item.title, current_title_before)

    def test_06_removing_current_track_in_bulk_selection_is_handled(self):
        pm = self._manager(5)
        pm.current_index = 2  # "track_02"
        for idx in sorted([1, 2, 3], reverse=True):
            pm.remove_at(idx)
        # Current track was itself removed; index must land in-bounds (or
        # signal "nothing playing", represented as -1) rather than pointing
        # at a stale/wrong item.
        self.assertTrue(pm.current_index == -1 or 0 <= pm.current_index < len(pm))


class TestPlaylistWidgetSelection(unittest.TestCase):
    """Task 5: native Qt multi-selection and UI-level bulk removal."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _module(self, n=6):
        manager = PlaylistManager()
        for i in range(n):
            manager.add_file(f"C:/music/track_{i:02d}.mp3")
        mod = PlaylistModule(manager)
        mod.refresh()
        return mod, manager

    def test_09_extended_selection_mode_enabled(self):
        mod, _ = self._module()
        self.assertEqual(mod.list_widget.selectionMode(), QAbstractItemView.ExtendedSelection)

    def test_10_bulk_remove_deletes_all_selected_rows(self):
        mod, manager = self._module(6)
        for row in (1, 3, 4):
            mod.list_widget.item(row).setSelected(True)
        mod._remove_selected()
        remaining = [item.title for item in manager.items]
        self.assertEqual(remaining, ["track_00", "track_02", "track_05"])

    def test_11_refresh_preserves_selection_across_unrelated_update(self):
        mod, manager = self._module(6)
        mod.list_widget.item(2).setSelected(True)
        mod.list_widget.item(4).setSelected(True)

        # Simulate playback advancing (current track changes) -- an
        # unrelated event that still triggers refresh().
        manager.current_index = 0
        mod.refresh()

        selected_rows = {mod.list_widget.row(i) for i in mod.list_widget.selectedItems()}
        self.assertEqual(selected_rows, {2, 4})

    def test_12_refresh_does_not_select_the_now_playing_row(self):
        mod, manager = self._module(6)
        manager.current_index = 3
        mod.refresh()
        # The "now playing" indicator must not also mark the row selected.
        self.assertEqual(mod.list_widget.selectedItems(), [])
        self.assertEqual(mod.list_widget.currentRow(), 3)


class TestVersionConsistency(unittest.TestCase):
    """Task 7: a single authoritative version source."""

    def test_07_version_is_0_667(self):
        from toroidamp import __version__
        self.assertEqual(__version__, "0.667")

    def test_08_pyproject_version_matches_package_version(self):
        import tomllib
        from pathlib import Path
        from toroidamp import __version__
        repo_root = Path(__file__).resolve().parent.parent
        pyproject_version = tomllib.loads(
            (repo_root / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["version"]
        self.assertEqual(pyproject_version, __version__)


if __name__ == "__main__":
    unittest.main()
