"""
ToroidAMP - RELEASE-POLISH-0.667 Test Suite
Validation of Canonical Version 0.667, Persistent File Logging,
Linux Desktop Packaging Asset, User-Writable Paths, and Platform Policies.
"""

import logging
import os
import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import toroidamp
from toroidamp import __version__
from toroidamp.__main__ import setup_logging
from toroidamp.paths import get_app_data_dir, get_logs_dir, get_user_shaders_dir
from toroidamp.audio.voice import VoiceService

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestReleaseVersionAndMetadata(unittest.TestCase):
    """Tests canonical version normalization."""

    def test_01_canonical_version_is_0_669(self):
        self.assertEqual(__version__, "0.669")
        self.assertEqual(toroidamp.__version__, "0.669")

    def test_02_pyproject_matches_canonical_version(self):
        pyproject_path = REPO_ROOT / "pyproject.toml"
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["version"], "0.669")


class TestFileLoggingAndDiagnostics(unittest.TestCase):
    """Tests file logging initialization, path resolution, and handler idempotency."""

    def test_03_logging_path_resolves_inside_logs_dir(self):
        logs_dir = get_logs_dir()
        self.assertTrue(logs_dir.is_dir())
        self.assertEqual(logs_dir.name, "logs")
        self.assertEqual(logs_dir.parent.name, "ToroidAMP")

    def test_04_setup_logging_is_idempotent(self):
        root_logger = logging.getLogger()
        setup_logging()
        count_after_first = len(root_logger.handlers)

        # Call setup_logging multiple additional times
        setup_logging()
        setup_logging()

        # Handlers should remain strictly equal to count_after_first
        self.assertEqual(len(root_logger.handlers), count_after_first)


class TestLinuxDesktopIntegrationAsset(unittest.TestCase):
    """Tests the canonical packaging/toroidamp.desktop configuration."""

    def test_05_desktop_file_exists_and_conforms(self):
        desktop_file = REPO_ROOT / "packaging" / "toroidamp.desktop"
        self.assertTrue(desktop_file.is_file(), "packaging/toroidamp.desktop must exist")

        content = desktop_file.read_text(encoding="utf-8")
        self.assertIn("Name=ToroidAMP", content)
        self.assertIn("Terminal=false", content)
        self.assertIn("Icon=toroidamp", content)
        self.assertIn("StartupWMClass=toroidamp", content)
        self.assertIn("Categories=AudioVideo;Audio;Player;Qt;", content)

        # No absolute developer paths
        self.assertNotIn("/home/", content)
        self.assertNotIn("C:\\\\", content)


class TestUserWritablePathsIsolation(unittest.TestCase):
    """Tests that writable paths target user-owned locations, never source/install tree."""

    def test_06_paths_do_not_target_repo_root(self):
        app_data = get_app_data_dir()
        logs_dir = get_logs_dir()
        shaders_dir = get_user_shaders_dir()

        repo_str = str(REPO_ROOT.resolve())
        self.assertFalse(str(app_data.resolve()).startswith(repo_str))
        self.assertFalse(str(logs_dir.resolve()).startswith(repo_str))
        self.assertFalse(str(shaders_dir.resolve()).startswith(repo_str))


class TestPlatformVoicePolicies(unittest.TestCase):
    """Tests Linux startup TTS deferral and Windows preservation."""

    def test_07_linux_startup_voice_deferred(self):
        vs = VoiceService()
        with patch("toroidamp.audio.voice.sys.platform", "linux"):
            with patch("toroidamp.audio.voice.logger") as mock_logger:
                vs.speak_startup_phrase_async()
                self.assertIsNone(vs._thread)
                info_calls = [str(c) for c in mock_logger.info.call_args_list]
                self.assertTrue(any("Startup voice disabled on Linux" in c for c in info_calls))

    def test_08_windows_startup_voice_enabled(self):
        vs = VoiceService()
        with patch("toroidamp.audio.voice.sys.platform", "win32"):
            with patch.object(vs, "_synthesize_and_play") as mock_play:
                vs.speak_startup_phrase_async("Windows Test")
                self.assertIsNotNone(vs._thread)
                if vs._thread is not None:
                    vs._thread.join(timeout=2.0)
                mock_play.assert_called_once_with("Windows Test")


if __name__ == "__main__":
    unittest.main()
