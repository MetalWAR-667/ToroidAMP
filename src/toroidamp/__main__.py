"""
ToroidAMP - Production Application Entry Point
Supports execution via 'python -m toroidamp' or the 'toroidamp' console script.
"""

import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.player import PlayerEngine
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.ui.window_manager import WindowManager


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )


def main():
    setup_logging()
    logger = logging.getLogger("toroidamp.main")
    logger.info("Starting ToroidAMP v0.1.0 (Production Core & Modular UI)")

    app = QApplication(sys.argv)
    app.setApplicationName("ToroidAMP")
    app.setOrganizationName("ToroidAMP")

    # 1. Initialize Analysis Handoff
    handoff = AnalysisHandoff(buffer_frames=2048)

    # 2. Initialize Player Engine
    player = PlayerEngine(handoff=handoff)

    # 3. Initialize Playlist Manager
    playlist = PlaylistManager()

    # Pre-populate sample tracks from known test assets if available
    asset_dir = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "assets", "audio")
    sample_mp3 = os.path.abspath(os.path.join(asset_dir, "Burn The World Waltz.mp3"))
    if os.path.exists(sample_mp3):
        playlist.add_file(sample_mp3, "Burn The World Waltz", duration=200.0)

    donor_xm = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Metalwar-Installer", "dalezy-lotus_drei_remix.xm"))
    if os.path.exists(donor_xm):
        playlist.add_file(donor_xm, "dalezy-lotus_drei_remix", duration=40.0)

    donor_it = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Metalwar-Installer", "08_sad_song.it"))
    if os.path.exists(donor_it):
        playlist.add_file(donor_it, "08_sad_song", duration=199.0)

    # 4. Initialize Window Manager
    window_manager = WindowManager(player=player, handoff=handoff, playlist=playlist)

    # If tracks were passed via CLI args, load them into playlist
    cli_files = [os.path.abspath(f) for f in sys.argv[1:] if os.path.isfile(f)]
    if cli_files:
        playlist.clear()
        playlist.add_files(cli_files)
        window_manager.pl_mod.refresh()
        window_manager.load_and_play(cli_files[0])

    exit_code = app.exec()
    player.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
