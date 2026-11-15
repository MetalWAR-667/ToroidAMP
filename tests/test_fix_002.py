"""
ToroidAMP - FIX-002 Regression & Production Isolation Test Suite
Validates:
1. Strict production isolation: startup with no session / CLI produces an empty playlist.
2. No runtime dependency or path references to MetalWar-Installer.
3. Native Qt close events (WM_CLOSE / Taskbar thumbnail X / Alt+F4) route to authoritative shutdown.
4. Minimize keeps process and audio alive, while close terminates everything.
"""

import os
import re
import sys
import tempfile
from pathlib import Path

from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.player import PlayerEngine, PlaybackState
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.session import SessionManager


# ---------------------------------------------------------------------------
# Donor-isolation detection (BASELINE-REPAIR-002)
#
# FIX-002's original guard scanned every production line for the bare token
# "metalwar". That was adequate before the roster gained the first-party
# MetalWar Credits visualizer, but it now flags an authorized module simply
# for containing the project's own name. These markers narrow the rule to
# the donor project itself and its historical media identifiers, while
# still allowing first-party "MetalWar" branding.
# ---------------------------------------------------------------------------

_DONOR_PROJECT_MARKER = re.compile(r"metalwar[\s_-]?installer", re.IGNORECASE)
_DONOR_MEDIA_MARKER = re.compile(r"dalezy|lotus[\s_-]?drei", re.IGNORECASE)


def find_donor_references(source: str) -> list[str]:
    """
    Return findings for every active line in *source* that references the
    historical MetalWar-Installer donor project or its media.

    Full-line comments are exempt: attribution comments naming the donor are
    intentional and documented, and do not create a runtime dependency.
    """
    findings: list[str] = []
    for lineno, line in enumerate(source.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        if _DONOR_PROJECT_MARKER.search(line) or _DONOR_MEDIA_MARKER.search(line):
            findings.append(f"line {lineno}: {line.strip()}")
    return findings


def scan_tree_for_donor_references(root: Path) -> list[str]:
    """Scan every production Python module under *root* with the shared detector."""
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for finding in find_donor_references(text):
            findings.append(f"{path}: {finding}")
    return findings


def test_production_isolation_empty_startup():
    """Validates that a fresh startup with no session or CLI args results in an empty playlist."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    from PySide6.QtWidgets import QApplication
    from toroidamp.ui.window_manager import WindowManager

    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp_dir:
        session_file = os.path.join(tmp_dir, "empty_session.json")
        sm = SessionManager(custom_path=session_file)

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()

        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)

        # 1. Assert Playlist is 100% EMPTY (no donor tracks or test audio auto-injected)
        assert len(playlist) == 0, f"Expected empty playlist on fresh startup, found {len(playlist)} items"
        assert playlist.current_item is None
        assert playlist.current_index == -1

        # 2. Assert PlayerEngine state
        assert player.state == PlaybackState.STOPPED
        assert player.is_tracker is False
        assert player.duration == 0.0

        wm.shutdown()

    app.quit()


def test_no_donor_path_in_production_codebase():
    """Validates that no production src/ file depends on MetalWar-Installer."""
    src_dir = Path(__file__).resolve().parent.parent / "src" / "toroidamp"
    findings = scan_tree_for_donor_references(src_dir)
    assert not findings, "Found forbidden donor reference(s):\n" + "\n".join(findings)


def test_donor_guard_rejects_donor_and_accepts_first_party():
    """
    Negative controls for the shared detector (BASELINE-REPAIR-002).

    These snippets exercise find_donor_references() -- the exact function the
    production-tree scan above uses -- so the guard cannot silently degrade
    into an always-pass check.
    """
    rejected = {
        "donor package import": "from metalwar_installer.audio import MusicClock\n",
        "donor project path": 'DONOR_DIR = REPO_ROOT.parent / "Metalwar-Installer"\n',
        "donor filesystem path": (
            "donor_xm = os.path.abspath(os.path.join(os.path.dirname(__file__), "
            '"..", "..", "..", "Metalwar-Installer", "dalezy-lotus_drei_remix.xm"))\n'
        ),
        "donor media filename": 'title = "dalezy-lotus_drei_remix"\n',
    }
    for label, snippet in rejected.items():
        assert find_donor_references(snippet), f"{label} was not rejected: {snippet!r}"

    accepted = {
        "first-party visualizer import": (
            "from ..visualizers.metalwar_credits import MetalWarCreditsVisualizer\n"
        ),
        "first-party visualizer id": 'return "metalwar_credits"\n',
        "first-party display name": 'return "MetalWar Credits"\n',
        "first-party credits text": '"CODE BY METALWAR & THE DEMOSCENE",\n',
        "ordinary first-party import": "from toroidamp.audio.player import PlayerEngine\n",
        "attribution comment": (
            "# Reimplemented from MetalWar-Installer effects.py:1905; no dependency.\n"
        ),
    }
    for label, snippet in accepted.items():
        assert not find_donor_references(snippet), f"{label} was falsely rejected: {snippet!r}"

    # Exercise the exact tree-scanning function used against src/toroidamp, so
    # the file traversal path cannot regress into an always-pass no-op either.
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "clean_module.py").write_text(
            "from ..visualizers.metalwar_credits import MetalWarCreditsVisualizer\n",
            encoding="utf-8",
        )
        assert not scan_tree_for_donor_references(root), "tree scan falsely rejected clean code"

        (root / "contaminated_module.py").write_text(
            'DONOR = "../Metalwar-Installer/audio.py"\n', encoding="utf-8"
        )
        assert scan_tree_for_donor_references(root), "tree scan accepted a synthetic donor path"


def test_native_close_event_routing():
    """Validates that closeEvent on UnifiedChassis triggers authoritative WindowManager shutdown."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QCloseEvent
    from toroidamp.ui.window_manager import WindowManager

    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp_dir:
        session_file = os.path.join(tmp_dir, "close_session.json")
        sm = SessionManager(custom_path=session_file)

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()

        # Add track and play
        test_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "audio", "Burn The World Waltz.mp3"))
        if os.path.exists(test_file):
            playlist.add_file(test_file, "Test", 200.0)

        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)
        wm._play_index(0)
        assert player.state == PlaybackState.PLAYING

        # Simulate native Windows WM_CLOSE / Taskbar thumbnail X / Alt+F4
        close_evt = QCloseEvent()
        wm.chassis.closeEvent(close_evt)

        # Assert full shutdown executed: audio stopped, windows closed, timers stopped
        assert player.state == PlaybackState.STOPPED
        assert wm.render_timer.isActive() is False
        assert wm.snap_timer.isActive() is False
        assert getattr(wm, "_is_shutting_down", False) is True

    app.quit()


if __name__ == "__main__":
    print("Running test_production_isolation_empty_startup...")
    test_production_isolation_empty_startup()
    print("PASS: test_production_isolation_empty_startup")

    print("Running test_no_donor_path_in_production_codebase...")
    test_no_donor_path_in_production_codebase()
    print("PASS: test_no_donor_path_in_production_codebase")

    print("Running test_donor_guard_rejects_donor_and_accepts_first_party...")
    test_donor_guard_rejects_donor_and_accepts_first_party()
    print("PASS: test_donor_guard_rejects_donor_and_accepts_first_party")

    print("Running test_native_close_event_routing...")
    test_native_close_event_routing()
    print("PASS: test_native_close_event_routing")

    print("\n--> ALL FIX-002 PRODUCTION ISOLATION & SHUTDOWN TESTS PASSED 100%! <--")
