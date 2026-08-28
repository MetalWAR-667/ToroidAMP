"""
tests/test_rc_069_002.py — RC-069-002: Packaging Prerequisites & Runtime Hygiene

Validates:
1.  Application data root resolves outside the repository.
2.  Log directory resolves correctly under the app data root.
3.  User shader directory is writable/application-owned (not repo-relative).
4.  Official shader resource resolves as a bundled, read-only resource.
5.  Theme resource resolves.
6.  GPU texture resolves.
7.  Resource lookup works from a foreign CWD.
8.  First-run directory creation is idempotent.
9.  File logger can write.
10. Repeated logger setup does not duplicate handlers.
11. Log rotation configuration exists/bounded.
12. Tracker-unavailable path fails cleanly (not a bare, uncaught ctypes traceback).
13. Tracker backend discovery uses the intended (documented) locations.
14. Version fallback remains functional.
15. Source checkout still runs correctly (smoke).
"""

import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestRC069002ResourcePaths(unittest.TestCase):
    """Items 1-8: writable app-data paths + read-only resource resolution, incl. foreign CWD."""

    def setUp(self):
        self._original_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self._original_cwd)

    def test_01_app_data_root_resolves_outside_repo(self):
        from toroidamp.paths import get_app_data_dir
        d = get_app_data_dir()
        self.assertTrue(d.is_absolute())
        self.assertFalse(str(d).lower().startswith(str(REPO_ROOT).lower()))

    def test_02_logs_dir_resolves_under_app_data_root(self):
        from toroidamp.paths import get_app_data_dir, get_logs_dir
        root = get_app_data_dir()
        logs = get_logs_dir()
        self.assertEqual(logs.parent, root)
        self.assertEqual(logs.name, "logs")
        self.assertTrue(logs.is_dir())

    def test_03_user_shader_dir_is_writable_app_owned(self):
        from toroidamp.paths import get_app_data_dir, get_user_shaders_dir
        root = get_app_data_dir()
        shaders_dir = get_user_shaders_dir()
        self.assertEqual(shaders_dir.parent, root)
        self.assertTrue(shaders_dir.is_dir())
        # Genuinely writable — not just "exists".
        probe = shaders_dir / "_rc069002_write_probe.tmp"
        probe.write_text("ok", encoding="utf-8")
        self.assertTrue(probe.is_file())
        probe.unlink()
        # Never repo-relative.
        self.assertFalse(str(shaders_dir).lower().startswith(str(REPO_ROOT).lower()))

    def test_04_official_shader_resolves_as_bundled_resource(self):
        from toroidamp.resources import resolve_package_asset
        p = resolve_package_asset("assets/official_shaders/cyber_bloom.frag")
        self.assertIsNotNone(p)
        self.assertTrue(p.is_file())
        self.assertTrue(p.is_absolute())

    def test_05_theme_resource_resolves(self):
        from toroidamp.resources import resolve_package_asset
        p = resolve_package_asset("assets/themes/default/theme.qss")
        self.assertIsNotNone(p)
        self.assertTrue(p.is_file())

    def test_06_gpu_texture_resolves(self):
        from toroidamp.resources import resolve_package_asset
        p = resolve_package_asset("assets/images/ToroidAMP.png")
        self.assertIsNotNone(p)
        self.assertTrue(p.is_file())

    def test_07_resource_lookup_works_from_foreign_cwd(self):
        from toroidamp.resources import resolve_package_asset
        os.chdir(tempfile.gettempdir())
        try:
            official = resolve_package_asset("assets/official_shaders/toroid_identity.frag")
            theme = resolve_package_asset("assets/themes/cyber_yellow/theme.qss")
            texture = resolve_package_asset("assets/images/ToroidAMP.png")
        finally:
            os.chdir(self._original_cwd)
        for p in (official, theme, texture):
            self.assertIsNotNone(p)
            self.assertTrue(p.is_file())
            self.assertTrue(p.is_absolute())

    def test_07b_app_data_dir_resolves_from_foreign_cwd(self):
        from toroidamp.paths import get_app_data_dir
        os.chdir(tempfile.gettempdir())
        try:
            d = get_app_data_dir()
        finally:
            os.chdir(self._original_cwd)
        self.assertTrue(d.is_absolute())
        self.assertTrue(d.is_dir())

    def test_08_first_run_directory_creation_is_idempotent(self):
        from toroidamp.paths import get_app_data_dir, get_logs_dir, get_user_shaders_dir
        # Calling repeatedly must never raise (mkdir(..., exist_ok=True) contract).
        for _ in range(3):
            get_app_data_dir()
            get_logs_dir()
            get_user_shaders_dir()
        self.assertTrue(get_logs_dir().is_dir())
        self.assertTrue(get_user_shaders_dir().is_dir())


class TestRC069002Logging(unittest.TestCase):
    """Items 9-11: persistent file logging."""

    def setUp(self):
        self._root_logger = logging.getLogger()
        self._saved_handlers = list(self._root_logger.handlers)
        for h in self._saved_handlers:
            self._root_logger.removeHandler(h)

    def tearDown(self):
        for h in list(self._root_logger.handlers):
            self._root_logger.removeHandler(h)
        for h in self._saved_handlers:
            self._root_logger.addHandler(h)

    def test_09_file_logger_can_write(self):
        from toroidamp.__main__ import setup_logging
        from toroidamp.paths import get_logs_dir
        setup_logging()
        marker = "RC-069-002 test_09 write probe"
        logging.getLogger("toroidamp.test_rc069002").info(marker)
        log_path = get_logs_dir() / "toroidamp.log"
        self.assertTrue(log_path.is_file())
        content = log_path.read_text(encoding="utf-8")
        self.assertIn(marker, content)

    def test_10_repeated_setup_does_not_duplicate_handlers(self):
        from toroidamp.__main__ import setup_logging
        setup_logging()
        count_after_first = len(self._root_logger.handlers)
        setup_logging()
        setup_logging()
        self.assertEqual(len(self._root_logger.handlers), count_after_first)
        self.assertGreaterEqual(count_after_first, 1)

    def test_11_log_rotation_is_bounded(self):
        from toroidamp.__main__ import setup_logging
        from logging.handlers import RotatingFileHandler
        setup_logging()
        file_handlers = [h for h in self._root_logger.handlers if isinstance(h, RotatingFileHandler)]
        self.assertEqual(len(file_handlers), 1)
        fh = file_handlers[0]
        self.assertGreater(fh.maxBytes, 0)
        self.assertGreaterEqual(fh.backupCount, 1)
        # Explicit ceiling check — never literally unbounded.
        self.assertLess(fh.maxBytes * (fh.backupCount + 1), 50 * 1024 * 1024)

    def test_11b_no_network_handlers_present(self):
        """ToroidAMP logging is LOCAL ONLY — no SocketHandler/HTTPHandler/SMTPHandler etc."""
        from toroidamp.__main__ import setup_logging
        setup_logging()
        for h in self._root_logger.handlers:
            self.assertNotIn("Socket", type(h).__name__)
            self.assertNotIn("HTTP", type(h).__name__)
            self.assertNotIn("SMTP", type(h).__name__)
            self.assertNotIn("Syslog", type(h).__name__)


class TestRC069002TrackerFailureSemantics(unittest.TestCase):
    """Items 12-13: tracker backend discovery + clean failure behavior."""

    def test_12_tracker_unavailable_path_fails_cleanly(self):
        """
        A missing native tracker backend must produce the SAME clean,
        tracked decoder-failure state every other decode failure gets
        (`decoder_failed` / `check_and_clear_error()`), not an exception
        that bypasses that bookkeeping entirely (the real, pre-existing gap
        this cut fixes in player.py's `load()`).
        """
        from toroidamp.audio.decoders.tracker import TrackerDecoder
        if TrackerDecoder.is_available():
            self.skipTest("the native tracker library is available in this environment — this test targets the unavailable path")

        from toroidamp.audio.player import PlayerEngine
        from toroidamp.analysis.audio_frame import AnalysisHandoff

        tmpdir = tempfile.mkdtemp()
        fake_mod = Path(tmpdir) / "fake.mod"
        fake_mod.write_bytes(b"not a real tracker module, just needs to exist on disk")

        handoff = AnalysisHandoff(buffer_frames=2048)
        player = PlayerEngine(handoff=handoff)
        try:
            with self.assertRaises(RuntimeError):
                player.load(str(fake_mod))
            self.assertTrue(player.decoder_failed)
            has_error, failed_path, msg = player.check_and_clear_error()
            self.assertTrue(has_error)
            self.assertEqual(failed_path, str(fake_mod))
            self.assertTrue(msg)  # RC-069-002B: exact wording is now backend-specific (libxmp), not asserted here
            # check_and_clear_error() is one-shot: the flag must now be clear.
            self.assertFalse(player.decoder_failed)
        finally:
            player.close()

    def test_13_tracker_discovery_uses_intended_locations(self):
        """
        Documents/pins the exact discovery order tracker.py uses, so a
        future change to it is a deliberate, visible diff — not silent.
        RC-069-002B: the backend migrated from libmodplug to libxmp (see
        docs/release/RC_069_002B_tracker_libxmp.md) — this test now pins
        the libxmp discovery method.
        """
        from toroidamp.audio.decoders.tracker import TrackerDecoder
        import inspect
        src = inspect.getsource(TrackerDecoder._discover_libxmp)
        self.assertIn("pygame", src)
        self.assertIn("ctypes.util.find_library", src)
        self.assertIn("libxmp", src)


class TestRC069002VersionAndSmoke(unittest.TestCase):
    """Items 14-15: version fallback, source-checkout smoke test."""

    def test_14_version_fallback_remains_functional(self):
        from toroidamp._version import resolve_version, FALLBACK_VERSION, _from_pyproject, _from_installed_metadata
        # In this source checkout, tier 1 (direct pyproject.toml read) must succeed.
        self.assertIsNotNone(_from_pyproject())
        version = resolve_version()
        self.assertIsInstance(version, str)
        self.assertNotEqual(version, "")
        # Every tier must be independently callable without raising.
        _from_installed_metadata()
        self.assertIsInstance(FALLBACK_VERSION, str)

    def test_15_source_checkout_still_runs(self):
        """End-to-end smoke: the core wiring __main__.main() performs still constructs cleanly."""
        import sys as _sys
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(_sys.argv)

        from toroidamp import __version__
        from toroidamp.branding import resolve_branding_icon
        from toroidamp.analysis.audio_frame import AnalysisHandoff
        from toroidamp.audio.player import PlayerEngine
        from toroidamp.audio.playlist import PlaylistManager
        from toroidamp.session import SessionManager
        from toroidamp.ui.window_manager import WindowManager

        self.assertTrue(__version__)
        handoff = AnalysisHandoff(buffer_frames=2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()
        session_manager = SessionManager()
        window_manager = WindowManager(
            player=player, handoff=handoff, playlist=playlist, session_manager=session_manager
        )
        self.assertIsNotNone(window_manager)
        player.close()


if __name__ == "__main__":
    unittest.main()
