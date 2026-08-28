"""
ToroidAMP - Production Test Suite
Validates Audio Engine, Decoders, Playlist Manager, M3U I/O, UI Window States, and Visualizers.
"""

import os
import sys
import tempfile
import numpy as np
import pytest

# Verify imports directly from installed toroidamp package
from toroidamp.analysis.audio_frame import AudioFrame, AnalysisHandoff
from toroidamp.audio.decoders.conventional import ConventionalDecoder
from toroidamp.audio.decoders.tracker import TrackerDecoder
from toroidamp.audio.player import PlayerEngine, PlaybackState
from toroidamp.audio.playlist import PlaylistItem, PlaylistManager
from toroidamp.visualizers.toroid import ToroidVisualizer
from toroidamp.visualizers.ribbon import WaveformRibbonVisualizer


def test_playlist_manager():
    """Validates PlaylistManager operations: add, remove, reorder, shuffle, repeat, M3U."""
    pl = PlaylistManager()
    
    # 1. Add files
    i1 = pl.add_file("/path/to/track1.mp3", "Track 1", 120.0)
    i2 = pl.add_file("/path/to/track2.xm", "Track 2", 90.0)
    i3 = pl.add_file("/path/to/track3.ogg", "Track 3", 180.0)
    assert len(pl) == 3
    assert pl.current_index == 0
    assert pl.current_item == i1

    # 2. Progression
    assert pl.get_next_index() == 1
    assert pl.get_previous_index() == 0

    # 3. Repeat all
    pl.repeat = True
    pl.current_index = 2
    assert pl.get_next_index() == 0
    assert pl.get_previous_index() == 1

    # 4. Reorder
    pl.move_item(0, 2)
    assert pl.items[2].title == "Track 1"
    assert pl.items[0].title == "Track 2"

    # 5. M3U Save & Load
    with tempfile.NamedTemporaryFile(suffix=".m3u8", delete=False, mode="w") as tmp:
        tmp_path = tmp.name

    try:
        pl.save_m3u(tmp_path)
        assert os.path.exists(tmp_path)

        pl2 = PlaylistManager()
        # Mock file existence for M3U loading
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"#EXTINF:120,Direct Track\n")
            f.write(f"{tmp_path}\n") # Point to itself as valid existing file
        
        loaded = pl2.load_m3u(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].title == "Direct Track"
        assert loaded[0].duration == 120.0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # 6. Remove
    pl.remove_at(0)
    assert len(pl) == 2


def test_audio_and_decoders():
    """Validates real audio decoders and AudioFrame generation."""
    handoff = AnalysisHandoff(2048)
    player = PlayerEngine(handoff=handoff)

    # Check test assets
    mp3_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "audio", "Burn The World Waltz.mp3"))
    if os.path.exists(mp3_path):
        dec = ConventionalDecoder()
        dec.load(mp3_path)
        assert dec.get_duration() > 0.0
        pcm = dec.read_frames(512)
        assert pcm.shape == (512, 2)
        assert pcm.dtype == np.float32
        dec.close()

    xm_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Metalwar-Installer", "dalezy-lotus_drei_remix.xm"))
    if os.path.exists(xm_path) and TrackerDecoder.is_available():
        t_dec = TrackerDecoder()
        t_dec.load(xm_path)
        assert t_dec.get_duration() > 0.0
        t_pcm = t_dec.read_frames(512)
        assert t_pcm.shape == (512, 2)
        assert t_pcm.dtype == np.float32
        t_dec.close()
    # If libxmp isn't present, tracker coverage is skipped here rather
    # than failing this otherwise-independent (mp3/AudioFrame) test — see
    # test_production_core.py::test_tracker_decoder for the dedicated,
    # explicitly-skipping tracker regression test.

    # AudioFrame contract
    t = np.linspace(0, 512/44100, 512, endpoint=False)
    sig = (0.5 * np.sin(2 * np.pi * 120 * t)).astype(np.float32)
    chunk = np.column_stack((sig, sig))
    handoff.push_audio(chunk)
    frame = handoff.get_audio_frame(44100)
    
    assert 0.0 <= frame.rms <= 1.0
    assert 0.0 <= frame.bass <= 1.0
    assert len(frame.spectrum) == 64
    assert len(frame.waveform) == 128


def test_visualizers_contract():
    """Validates internal Visualizer base contract and implementations."""
    import pygame
    pygame.init()
    surf = pygame.Surface((420, 240))
    handoff = AnalysisHandoff(2048)
    frame = handoff.get_audio_frame(44100)

    toroid = ToroidVisualizer(420, 240)
    toroid.render(surf, frame, 0.016)
    assert toroid.get_name() == "3D Toroid"

    ribbon = WaveformRibbonVisualizer(420, 240)
    ribbon.render(surf, frame, 0.016)
    assert ribbon.get_name() == "Waveform Ribbon"


def test_ui_experience_scales():
    """Validates PySide6 UI window management, transitions, and module restoration."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    from PySide6.QtWidgets import QApplication
    from toroidamp.ui.window_manager import WindowManager

    app = QApplication.instance() or QApplication([])

    handoff = AnalysisHandoff(2048)
    player = PlayerEngine(handoff=handoff)
    playlist = PlaylistManager()
    playlist.add_file("/dummy/track.mp3", "Dummy", 100.0)

    wm = WindowManager(player=player, handoff=handoff, playlist=playlist)

    # 1. Start in NORMAL
    assert wm.chassis.mode == "normal"
    assert wm.chassis.width() == 420
    assert wm.chassis.height() == 135

    # 2. Open Modules
    wm._toggle_vis()
    wm._toggle_pl()
    assert wm.vis_mod.isVisible()
    assert wm.pl_mod.isVisible()

    # 3. Transition to MINI
    # UX-001 widened MINI from 380x36 to 460x36 for title/time readability —
    # authoritative dimensions now live on UnifiedChassis.MINI_WIDTH/HEIGHT.
    wm.chassis.set_mode("mini")
    assert wm.chassis.mode == "mini"
    assert wm.chassis.width() == wm.chassis.MINI_WIDTH
    assert wm.chassis.height() == wm.chassis.MINI_HEIGHT
    assert not wm.vis_mod.isVisible()
    assert not wm.pl_mod.isVisible()

    # 4. Return to NORMAL (Modules Restored)
    wm.chassis.set_mode("normal")
    assert wm.chassis.mode == "normal"
    assert wm.vis_mod.isVisible()
    assert wm.pl_mod.isVisible()

    # 5. RETINA MELT Entry from NORMAL
    wm._enter_retina_melt()
    assert wm.retina_melt.isVisible()
    assert not wm.chassis.isVisible()
    assert wm.prior_scale == "normal"

    # 6. Exit RETINA MELT
    wm._exit_retina_melt()
    assert not wm.retina_melt.isVisible()
    assert wm.chassis.isVisible()
    assert wm.chassis.mode == "normal"

    # 7. Render Tick
    wm._tick()

    app.quit()


if __name__ == "__main__":
    print("Running test_playlist_manager...")
    test_playlist_manager()
    print("PASS: test_playlist_manager")

    print("Running test_audio_and_decoders...")
    test_audio_and_decoders()
    print("PASS: test_audio_and_decoders")

    print("Running test_visualizers_contract...")
    test_visualizers_contract()
    print("PASS: test_visualizers_contract")

    print("Running test_ui_experience_scales...")
    test_ui_experience_scales()
    print("PASS: test_ui_experience_scales")

    print("\n--> ALL PRODUCTION CUT 1B TESTS PASSED 100%! <--")
