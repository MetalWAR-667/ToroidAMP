"""
ToroidAMP - Production Application Entry Point
Supports execution via 'python -m toroidamp' or the 'toroidamp' console script.
"""

import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from toroidamp import __version__
from toroidamp.branding import resolve_branding_icon
from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.player import PlayerEngine
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.audio.voice import VoiceService
from toroidamp.session import SessionManager
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
    logger.info(f"Starting ToroidAMP v{__version__}")

    app = QApplication(sys.argv)
    app.setApplicationName("ToroidAMP")
    app.setOrganizationName("")  # Clean single canonical path: %LOCALAPPDATA%/ToroidAMP
    app.setQuitOnLastWindowClosed(False)  # Ensure tray background lifecycle stays alive when windows hide

    # BRAND-001: official checkerboard toroid identity for every window that
    # doesn't set its own icon (taskbar, Alt-Tab, etc.). A missing/unreadable
    # asset only logs a warning — it must never block startup.
    brand_icon = resolve_branding_icon()
    if brand_icon is not None:
        app.setWindowIcon(brand_icon)


    # 1. Initialize Analysis Handoff
    handoff = AnalysisHandoff(buffer_frames=2048)

    # 2. Initialize Player Engine
    player = PlayerEngine(handoff=handoff)

    # 3. Initialize Playlist Manager
    playlist = PlaylistManager()

    # 4. Initialize Session Manager
    session_manager = SessionManager()

    # 5. Initialize Window Manager
    window_manager = WindowManager(
        player=player,
        handoff=handoff,
        playlist=playlist,
        session_manager=session_manager
    )

    # 6. Initialize Voice Service
    voice_service = VoiceService()

    # 7. Command-Line File Arguments Override Policy:
    cli_files = [os.path.abspath(f) for f in sys.argv[1:] if os.path.isfile(f)]
    if cli_files:
        logger.info(f"Loading {len(cli_files)} files from command-line arguments")
        playlist.clear()
        playlist.add_files(cli_files)
        window_manager.pl_mod.refresh()
        window_manager.load_and_play(cli_files[0])
    else:
        # Announce startup identity line asynchronously
        logger.info("Triggering asynchronous startup voice identity line")
        voice_service.speak_startup_phrase_async()

    exit_code = app.exec()

    player.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
