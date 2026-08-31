"""
ToroidAMP - Production Application Entry Point
Supports execution via 'python -m toroidamp' or the 'toroidamp' console script.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from toroidamp import __version__
from toroidamp.branding import resolve_branding_icon
from toroidamp.analysis.audio_frame import AnalysisHandoff
from toroidamp.audio.player import PlayerEngine
from toroidamp.audio.playlist import PlaylistManager
from toroidamp.audio.voice import VoiceService
from toroidamp.paths import get_logs_dir
from toroidamp.session import SessionManager
from toroidamp.ui.window_manager import WindowManager

_LOG_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
_LOG_DATEFMT = "%H:%M:%S"
_HANDLER_MARKER = "_toroidamp_handler"


def setup_logging():
    """
    Configures console logging (unchanged, dev-friendly) plus a durable,
    modestly-sized rotating file log for release troubleshooting
    (RC-069-002) — `%LOCALAPPDATA%\\ToroidAMP\\logs\\toroidamp.log`, 2 MiB
    per file, 3 backups kept (~8 MiB ceiling; never unbounded growth).

    Idempotent: safe to call more than once (e.g. across tests importing
    this module repeatedly in one process) — re-invocation is a no-op
    rather than accumulating duplicate handlers on the root logger.

    ToroidAMP's logging is LOCAL ONLY: nothing here writes anywhere but this
    process's own console and this one local file. No network reporting, no
    telemetry, no external service of any kind — see
    docs/release/RC_069_002_runtime_hygiene.md for the explicit privacy
    statement this implementation follows (no file contents, no secrets).
    """
    root_logger = logging.getLogger()
    if any(getattr(h, _HANDLER_MARKER, False) for h in root_logger.handlers):
        return

    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    setattr(console_handler, _HANDLER_MARKER, True)
    root_logger.addHandler(console_handler)

    # File logging must never prevent startup — a permissions/disk issue
    # here is logged (to the console handler above, which is already live)
    # and otherwise swallowed; the application keeps running console-only.
    try:
        log_path = get_logs_dir() / "toroidamp.log"
        file_handler = RotatingFileHandler(
            log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        setattr(file_handler, _HANDLER_MARKER, True)
        root_logger.addHandler(file_handler)
    except Exception as e:
        logging.getLogger("toroidamp.main").warning(
            f"Could not initialize persistent file logging (continuing with console logging only): {e}"
        )


def main():
    setup_logging()
    logger = logging.getLogger("toroidamp.main")
    logger.info(f"Starting ToroidAMP v{__version__}")

    try:
        _run(logger)
    except SystemExit:
        raise
    except Exception:
        # RC-069-002: minimal startup-failure capture — not a crash
        # reporter, just a guarantee that an uncaught failure reaches the
        # persistent log file (already configured above) before the
        # process exits, since a packaged --windowed build has no console
        # for a bare traceback to land on. Never swallowed — re-raised
        # unchanged after logging so the process's actual exit behavior
        # (and exit code) is completely unchanged.
        logger.exception("ToroidAMP failed to start")
        raise


def _run(logger: logging.Logger):
    # GLSL-002: request an explicit OpenGL 3.3 Core Profile context before
    # the QApplication is constructed -- must happen before, since Qt only
    # applies the default surface format to windows/contexts created after
    # this call. Every official/user shader is wrapped with `#version 330
    # core`, and the GPU Authoring Lab (experiments/gpu_visualizers/
    # lab_app.py::run_gpu_lab) already requests exactly this; production
    # previously left it unset, silently falling back to whatever default
    # context the platform/driver negotiates. That divergence was harmless
    # on Windows (GPU vendor drivers accept #version 330 core regardless)
    # but is a real, auditable gap between the Lab and the production
    # hosts (RETINA MELT, and NORMAL's official GPU visualizers) that this
    # cut's GPU-architecture audit surfaced.
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setApplicationName("ToroidAMP")
    app.setOrganizationName("")  # Clean single canonical path: %LOCALAPPDATA%/ToroidAMP
    app.setQuitOnLastWindowClosed(False)  # Ensure tray background lifecycle stays alive when windows hide
    # Declares the desktop-entry identity ("toroidamp" -> a future
    # toroidamp.desktop) this running process corresponds to. Harmless
    # no-op on Windows/macOS. On Linux, this is the Qt-documented, portable
    # mechanism a Wayland compositor's app_id / an X11 WM_CLASS-based dock
    # uses to associate a running window with an installed .desktop file's
    # Icon= entry -- correct and forward-compatible to set now even though
    # no .desktop file ships yet (packaging, out of this cut's scope): a
    # GNOME/Wayland-style dock specifically resolves its icon by looking up
    # an *installed* .desktop file, which a source checkout (`python -m
    # toroidamp`) never has, so the dock icon itself will still show a
    # generic fallback until a real .desktop file is packaged and
    # installed -- this alone does not fake that, it only makes the
    # declared identity consistent and ready for when one exists.
    app.setDesktopFileName("toroidamp")

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
