"""
QoL-001 -- Shuffle Initial Playback

Validates that initial playback resolves through the active playback order:
  * Shuffle OFF: first canonical playlist item.
  * Shuffle ON: first item of the generated shuffle order.
  * Next/Previous from an unset index use the same starting point.
  * Explicit selection still plays exactly the requested item.
  * Empty and single-item playlists remain safe.
  * Session restoration stays STOPPED (no autoplay).

Shuffle is made deterministic by patching the playlist module's
`random.shuffle` with a reversing function.
"""

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from toroidamp.audio.player import PlayerEngine, PlaybackState
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.ui.window_manager import WindowManager


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def reverse_shuffle(monkeypatch):
    """Makes every generated shuffle order a deterministic reversal."""
    def _reverse(sequence):
        sequence.reverse()

    monkeypatch.setattr("toroidamp.audio.playlist.random.shuffle", _reverse)


def _make_manager(count: int) -> PlaylistManager:
    pm = PlaylistManager()
    for i in range(count):
        pm.add_file(f"C:/music/track_{i:02d}.mp3")
    return pm


class _FakePlayer:
    def __init__(self, state=PlaybackState.STOPPED, has_loaded_track=False):
        self.state = state
        self.has_loaded_track = has_loaded_track


def _make_window_manager(playlist: PlaylistManager, player) -> WindowManager:
    """Builds a WindowManager shell without constructing real UI/audio."""
    wm = WindowManager.__new__(WindowManager)
    wm.playlist = playlist
    wm.player_engine = player
    wm.pl_mod = MagicMock()
    wm.osd = MagicMock()
    wm.retina_melt = MagicMock()
    wm.retina_melt.isVisible.return_value = True

    played: list[str] = []
    wm.load_and_play = lambda filepath, use_crossfade=True: played.append(filepath)
    wm.played_files = played
    return wm


# ---------------------------------------------------------------------------
# PlaylistManager: initial index resolution
# ---------------------------------------------------------------------------

def test_initial_index_shuffle_off_is_first_canonical_item():
    pm = _make_manager(4)
    assert pm.shuffle is False
    assert pm.get_initial_playback_index() == 0


def test_initial_index_shuffle_on_is_first_shuffle_item(reverse_shuffle):
    pm = _make_manager(4)
    pm.shuffle = True

    # Deterministic reversal: canonical [0, 1, 2, 3] -> active [3, 2, 1, 0].
    assert pm.get_initial_playback_index() == 3


def test_initial_index_empty_playlist_is_none():
    pm = PlaylistManager()
    assert pm.get_initial_playback_index() is None
    assert pm.get_next_index() is None
    assert pm.get_previous_index() is None

    pm.shuffle = True
    assert pm.get_initial_playback_index() is None
    assert pm.get_next_index() is None
    assert pm.get_previous_index() is None


def test_initial_index_single_item_playlist_is_safe():
    pm = _make_manager(1)
    pm.shuffle = True

    assert pm.get_initial_playback_index() == 0

    pm.current_index = -1
    assert pm.get_next_index() == 0
    assert pm.get_previous_index() == 0

    # Once the only item is current, it is both the end and the beginning.
    pm.current_index = 0
    assert pm.get_next_index() is None
    assert pm.get_previous_index() == 0


# ---------------------------------------------------------------------------
# PlaylistManager: navigation follows the active shuffle sequence
# ---------------------------------------------------------------------------

def test_navigation_from_unset_index_uses_shuffle_start(reverse_shuffle):
    pm = _make_manager(4)
    pm.shuffle = True
    pm.current_index = -1

    assert pm.get_next_index() == 3
    assert pm.get_previous_index() == 3


def test_navigation_follows_shuffle_sequence(reverse_shuffle):
    pm = _make_manager(4)
    pm.shuffle = True

    pm.current_index = pm.get_initial_playback_index()  # 3
    assert pm.current_index == 3

    assert pm.get_next_index() == 2
    pm.current_index = 2
    assert pm.get_next_index() == 1
    pm.current_index = 1
    assert pm.get_next_index() == 0
    pm.current_index = 0
    assert pm.get_next_index() is None  # end of shuffled sequence, no repeat

    # Previous walks the same sequence backwards.
    pm.current_index = 0
    assert pm.get_previous_index() == 1
    pm.current_index = 1
    assert pm.get_previous_index() == 2
    pm.current_index = 2
    assert pm.get_previous_index() == 3


def test_explicit_selection_navigates_from_its_shuffle_position(reverse_shuffle):
    pm = _make_manager(4)
    pm.shuffle = True

    pm.current_index = 2  # explicit request for canonical track 2
    assert pm.current_item.title == "track_02"
    assert pm.get_next_index() == 1   # active order is [3, 2, 1, 0]
    assert pm.get_previous_index() == 3


def test_navigation_does_not_reshuffle(monkeypatch):
    shuffle_calls = []

    def _tracking_shuffle(sequence):
        shuffle_calls.append(list(sequence))
        sequence.reverse()

    monkeypatch.setattr("toroidamp.audio.playlist.random.shuffle", _tracking_shuffle)

    pm = _make_manager(4)
    pm.shuffle = True
    pm.current_index = pm.get_initial_playback_index()

    shuffle_calls.clear()
    for _ in range(3):
        pm.get_next_index()
        pm.get_previous_index()
        pm.get_initial_playback_index()

    assert shuffle_calls == []


# ---------------------------------------------------------------------------
# WindowManager: initial Play (shuffle off / on)
# ---------------------------------------------------------------------------

def test_toggle_play_shuffle_off_starts_first_item():
    pm = _make_manager(4)
    pm.current_index = -1
    wm = _make_window_manager(pm, _FakePlayer())

    wm._toggle_play()

    assert pm.current_index == 0
    assert wm.played_files == [pm.items[0].filepath]


def test_toggle_play_shuffle_on_starts_first_shuffle_item(reverse_shuffle):
    pm = _make_manager(4)
    pm.shuffle = True
    pm.current_index = -1
    wm = _make_window_manager(pm, _FakePlayer())

    wm._toggle_play()

    assert pm.current_index == 3
    assert wm.played_files == [pm.items[3].filepath]


def test_toggle_play_uses_shuffle_start_when_items_were_added_but_nothing_loaded(reverse_shuffle):
    # add_file() leaves current_index at canonical 0 on a fresh queue; no
    # decoder is loaded yet, so this is still initial playback.
    pm = _make_manager(4)
    pm.shuffle = True
    assert pm.current_index == 0
    wm = _make_window_manager(pm, _FakePlayer(has_loaded_track=False))

    wm._toggle_play()

    assert pm.current_index == 3
    assert wm.played_files == [pm.items[3].filepath]


def test_toggle_play_resumes_loaded_current_track(reverse_shuffle):
    pm = _make_manager(4)
    pm.shuffle = True
    pm.current_index = 2
    wm = _make_window_manager(pm, _FakePlayer(has_loaded_track=True))

    wm._toggle_play()

    assert pm.current_index == 2
    assert wm.played_files == [pm.items[2].filepath]


def test_toggle_play_empty_playlist_does_nothing():
    pm = PlaylistManager()
    wm = _make_window_manager(pm, _FakePlayer())

    wm._toggle_play()

    assert pm.current_index == -1
    assert wm.played_files == []


def test_play_index_always_plays_explicitly_requested_item(reverse_shuffle):
    pm = _make_manager(4)
    pm.shuffle = True
    wm = _make_window_manager(pm, _FakePlayer())

    wm._play_index(1)

    assert pm.current_index == 1
    assert wm.played_files == [pm.items[1].filepath]
    wm.pl_mod.refresh.assert_called()


def test_drag_drop_into_empty_playlist_starts_first_shuffle_item(reverse_shuffle):
    pm = PlaylistManager()
    pm.shuffle = True
    wm = _make_window_manager(pm, _FakePlayer())

    with tempfile.TemporaryDirectory() as tmp_dir:
        for name in ("01_track.mp3", "02_track.xm"):
            with open(os.path.join(tmp_dir, name), "w", encoding="utf-8") as f:
                f.write("dummy")
        wm._on_files_dropped([tmp_dir])

    # Deterministic reversal for two items: active order [1, 0].
    assert len(pm) == 2
    assert pm.current_index == 1
    assert wm.played_files == [pm.items[1].filepath]


# ---------------------------------------------------------------------------
# Session restoration: STOPPED, no autoplay, shuffle-aware initial index
# ---------------------------------------------------------------------------

def test_session_restore_with_shuffle_remains_stopped(reverse_shuffle):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    from PySide6.QtWidgets import QApplication
    from toroidamp.analysis.audio_frame import AnalysisHandoff
    from toroidamp.session import SessionManager

    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as tmp_dir:
        session_file = os.path.join(tmp_dir, "qol_001_session.json")
        files = []
        for i in range(3):
            path = os.path.join(tmp_dir, f"restored_{i}.mp3")
            with open(path, "wb") as f:
                f.write(b"RIFF dummy")
            files.append(path)

        sm = SessionManager(custom_path=session_file)
        sm.state.playlist_files = [
            {"filepath": path, "title": f"Restored {i}", "duration": 60.0}
            for i, path in enumerate(files)
        ]
        sm.state.shuffle = True
        sm.state.current_track_index = 2
        sm.save()

        handoff = AnalysisHandoff(2048)
        player = PlayerEngine(handoff=handoff)
        playlist = PlaylistManager()

        wm = WindowManager(player=player, handoff=handoff, playlist=playlist, session_manager=sm)

        # Startup contract: queue restored, nothing loaded, nothing playing.
        assert len(playlist) == 3
        assert player.state == PlaybackState.STOPPED
        assert playlist.current_index == -1
        assert playlist.current_item is None
        assert player.has_loaded_track is False

        # Deterministic reversal: active order [2, 1, 0].
        assert playlist.get_initial_playback_index() == 2

        # Initial Play must start at the active order's first item, without
        # needing a real decoder (load is stubbed for determinism).
        played: list[str] = []
        wm.load_and_play = lambda filepath, use_crossfade=True: played.append(filepath)
        wm._toggle_play()

        assert playlist.current_index == 2
        assert played == [playlist.items[2].filepath]

        wm.shutdown()

    app.quit()
