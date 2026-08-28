"""
tests/test_rc_069_002b.py — RC-069-002B: Tracker Backend Migration (libmodplug -> libxmp)

Validates:
1.  libxmp discovery.
2.  Unavailable-lib clean behavior.
3.  ctypes signature setup (no implicit-conversion crashes).
4.  Valid context creation.
5.  Module load failure isolation (malformed file, does not crash).
6.  PCM conversion to float32.
7.  Stereo shape/interleaving.
8.  Normalization bounds ([-1.0, 1.0]).
9.  EOF handling.
10. Decoder reset (repeated load() on the same instance).
11. Seek path.
12. Duration path.
13. Player recovery after a tracker error.
14. Conventional decoder unaffected.
15. No tracker-specific changes in AnalysisHandoff's contract.

Uses REAL local tracker files from the sibling MetalWar-Installer donor
repo (never copied into this repository — referenced by absolute path,
skipped honestly if not present) for genuine, non-fabricated validation,
per this cut's explicit "do not manufacture fake byte arrays" instruction.
"""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DONOR_DIR = REPO_ROOT.parent / "Metalwar-Installer"

REAL_IT = DONOR_DIR / "08_sad_song.it"
REAL_XM = DONOR_DIR / "dalezy-lotus_drei_remix.xm"
REAL_MOD_A = DONOR_DIR / "alleviation-metal hr.mod"
REAL_MOD_B = DONOR_DIR / "tubularbells-metal hr.mod"
# No real .s3m fixture was available anywhere in this environment (see
# docs/release/RC_069_002B_tracker_libxmp.md) — S3M is architecturally
# supported by libxmp/TrackerDecoder identically to the other three
# formats, but genuinely untested here. Not faked.
REAL_S3M = DONOR_DIR / "does_not_exist.s3m"

REAL_TRACKER_FILES = [p for p in (REAL_IT, REAL_XM, REAL_MOD_A, REAL_MOD_B) if p.is_file()]


def _require_libxmp():
    from toroidamp.audio.decoders.tracker import TrackerDecoder
    if not TrackerDecoder.is_available():
        raise unittest.SkipTest("libxmp native library not found in this environment")


class TestRC069002BTrackerDiscovery(unittest.TestCase):
    """Items 1-2: discovery + clean unavailable behavior."""

    def test_01_libxmp_discovery(self):
        from toroidamp.audio.decoders.tracker import TrackerDecoder
        path = TrackerDecoder._discover_libxmp()
        # In THIS environment (pygame-ce bundles libxmp on Windows), discovery
        # must succeed — this is the core empirical finding this cut is based on.
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        self.assertIn("libxmp", os.path.basename(path).lower())

    def test_02_unavailable_lib_path_construction_raises_cleanly(self):
        from toroidamp.audio.decoders.tracker import TrackerDecoder
        with self.assertRaises(RuntimeError) as ctx:
            TrackerDecoder(lib_path="C:\\definitely\\does\\not\\exist\\libxmp.dll")
        self.assertIn("libxmp", str(ctx.exception).lower())


class TestRC069002BContextAndBinding(unittest.TestCase):
    """Items 3-4: ctypes signatures + context creation."""

    def setUp(self):
        _require_libxmp()

    def test_03_ctypes_signatures_no_implicit_conversion_crash(self):
        """Constructing a decoder exercises every _bind_functions() argtypes/restype assignment; a wrong signature would surface as an immediate ctypes ArgumentError or access violation."""
        from toroidamp.audio.decoders.tracker import TrackerDecoder
        d = TrackerDecoder()
        try:
            self.assertIsNotNone(d._ctx)
        finally:
            d.close()

    def test_04_valid_context_creation(self):
        from toroidamp.audio.decoders.tracker import TrackerDecoder
        d = TrackerDecoder()
        try:
            self.assertTrue(d._ctx)
            self.assertGreater(d._ctx, 0)
        finally:
            d.close()


class TestRC069002BRealModuleDecoding(unittest.TestCase):
    """Items 5-12: real-file load, PCM shape/normalization, EOF, reset, seek, duration."""

    def setUp(self):
        _require_libxmp()
        from toroidamp.audio.decoders.tracker import TrackerDecoder
        self.decoder = TrackerDecoder()

    def tearDown(self):
        self.decoder.close()

    def test_05_malformed_module_load_failure_is_isolated(self):
        tmpdir = tempfile.mkdtemp()
        bad = Path(tmpdir) / "garbage.mod"
        bad.write_bytes(b"not a real tracker module, just plain garbage bytes 0123456789")
        with self.assertRaises(RuntimeError):
            self.decoder.load(str(bad))
        # No crash reaching this line is itself the assertion; the decoder
        # object must remain usable afterward (see test_10).

    def test_05b_nonexistent_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.decoder.load(str(Path(tempfile.mkdtemp()) / "nope.mod"))

    def _assert_real_files_available(self):
        if not REAL_TRACKER_FILES:
            self.skipTest("no real local tracker fixtures found under the sibling MetalWar-Installer directory")

    def test_06_07_08_pcm_float32_stereo_normalized(self):
        self._assert_real_files_available()
        for f in REAL_TRACKER_FILES:
            with self.subTest(file=f.name):
                self.decoder.load(str(f))
                pcm = self.decoder.read_frames(4096)
                self.assertEqual(pcm.dtype, np.float32)
                self.assertEqual(pcm.ndim, 2)
                self.assertEqual(pcm.shape[1], 2)  # stereo, interleaved-then-reshaped
                self.assertGreater(pcm.shape[0], 0)
                self.assertTrue(np.all(pcm >= -1.0001))
                self.assertTrue(np.all(pcm <= 1.0001))
                # Genuinely non-silent — real audio content, not a degenerate all-zero buffer.
                self.assertGreater(np.count_nonzero(pcm), 0)

    def test_09_eof_returns_empty_array(self):
        self._assert_real_files_available()
        f = REAL_IT if REAL_IT.is_file() else REAL_TRACKER_FILES[0]
        self.decoder.load(str(f))
        # Seek near the very end and read past it — must eventually yield an empty array, never raise.
        self.decoder.seek(max(0.0, self.decoder.get_duration() - 0.5))
        got_empty = False
        for _ in range(50):
            pcm = self.decoder.read_frames(44100)
            if pcm.shape[0] == 0:
                got_empty = True
                break
        self.assertTrue(got_empty, "expected read_frames() to eventually signal EOF with an empty array")

    def test_10_decoder_reset_via_repeated_load(self):
        """The SAME TrackerDecoder instance must support load() being called multiple times (PlayerEngine's lazy-singleton reuse pattern)."""
        self._assert_real_files_available()
        for f in REAL_TRACKER_FILES:
            self.decoder.load(str(f))
            pcm = self.decoder.read_frames(1024)
            self.assertGreater(pcm.shape[0], 0)

    def test_11_seek(self):
        self._assert_real_files_available()
        f = REAL_IT if REAL_IT.is_file() else REAL_TRACKER_FILES[0]
        self.decoder.load(str(f))
        duration = self.decoder.get_duration()
        self.assertGreater(duration, 0.0)
        target = duration * 0.3
        self.decoder.seek(target)
        pcm = self.decoder.read_frames(4096)
        self.assertGreater(pcm.shape[0], 0)
        # Tracker seek is pattern/row-granular, not sample-accurate — this
        # test only asserts it doesn't raise and still produces real audio,
        # per this cut's documented seek-precision limitation.

    def test_12_duration(self):
        self._assert_real_files_available()
        for f in REAL_TRACKER_FILES:
            with self.subTest(file=f.name):
                self.decoder.load(str(f))
                self.assertGreater(self.decoder.get_duration(), 0.0)
                self.assertLess(self.decoder.get_duration(), 3600.0)  # sane upper bound, not unbounded/garbage


class TestRC069002BPlayerIntegration(unittest.TestCase):
    """Items 13-14: player recovery after tracker error, conventional decoder unaffected."""

    def setUp(self):
        from toroidamp.audio.player import PlayerEngine
        from toroidamp.analysis.audio_frame import AnalysisHandoff
        self.handoff = AnalysisHandoff(buffer_frames=2048)
        self.player = PlayerEngine(handoff=self.handoff)
        self.mp3_path = REPO_ROOT / "tests" / "assets" / "audio" / "Burn The World Waltz.mp3"

    def tearDown(self):
        self.player.close()

    def test_13_player_recovers_after_tracker_error(self):
        if not self.mp3_path.is_file():
            self.skipTest("conventional test fixture missing")
        tmpdir = tempfile.mkdtemp()
        bad = Path(tmpdir) / "garbage.mod"
        bad.write_bytes(b"not a real tracker module")

        with self.assertRaises(Exception):
            self.player.load(str(bad))
        self.assertTrue(self.player.decoder_failed)

        # Conventional playback must still work after a tracker failure.
        self.player.load(str(self.mp3_path))
        self.assertFalse(self.player.decoder_failed)

    def test_14_conventional_decoder_unaffected(self):
        if not self.mp3_path.is_file():
            self.skipTest("conventional test fixture missing")
        self.player.load(str(self.mp3_path))
        self.assertFalse(self.player.is_tracker)
        self.assertFalse(self.player.decoder_failed)
        self.assertEqual(self.player._sample_rate, 44100)


class TestRC069002BAnalysisHandoffUnchanged(unittest.TestCase):
    """Item 15: AnalysisHandoff receives normalized PCM identically regardless of decoder origin — no tracker-specific branching anywhere in the analysis path."""

    def test_15_tracker_pcm_feeds_analysis_handoff_like_any_other_source(self):
        _require_libxmp()
        if not REAL_TRACKER_FILES:
            self.skipTest("no real local tracker fixtures found")

        from toroidamp.audio.decoders.tracker import TrackerDecoder
        from toroidamp.analysis.audio_frame import AnalysisHandoff
        import inspect

        # Structural guarantee: AnalysisHandoff's source is never
        # inspected/branched on decoder type anywhere in its own source.
        src = inspect.getsource(AnalysisHandoff)
        self.assertNotIn("Tracker", src)
        self.assertNotIn("libxmp", src)
        self.assertNotIn("xmp_", src)

        decoder = TrackerDecoder()
        decoder.load(str(REAL_TRACKER_FILES[0]))
        handoff = AnalysisHandoff(buffer_frames=2048)

        pushed_any = False
        for _ in range(30):
            pcm = decoder.read_frames(2048)
            if pcm.shape[0] == 0:
                break
            handoff.push_audio(pcm)
            pushed_any = True
        decoder.close()

        self.assertTrue(pushed_any)
        frame = handoff.get_audio_frame(sr=44100)
        # A genuinely alive AudioFrame — not degenerate/all-zero — proves
        # the existing, unchanged analysis path works identically for
        # tracker-sourced PCM as it does for any other decoder.
        self.assertGreater(frame.rms, 0.0)
        self.assertFalse(np.isnan(frame.rms))
        self.assertGreater(np.count_nonzero(frame.spectrum), 0)
        self.assertGreater(np.count_nonzero(frame.waveform), 0)


if __name__ == "__main__":
    unittest.main()
