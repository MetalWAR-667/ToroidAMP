"""
ToroidAMP - Writable Application Data Paths (RC-069-002)

Single resolution point for every directory ToroidAMP itself writes to.
This is the WRITABLE counterpart to `resources.py` (which resolves
bundled, read-only package assets) — keep the two concepts separate, per
RC-069-001/002's explicit guidance: official/bundled content stays in
`resources.py`'s territory, user-owned/application-owned state lives here.

    Windows:  %LOCALAPPDATA%\\ToroidAMP\\
    Linux:    ~/.config/ToroidAMP/            (QStandardPaths fallback)

    %LOCALAPPDATA%\\ToroidAMP\\
        session.json      (session.py — unchanged, still resolves its own
                            file name; only the shared root directory logic
                            now lives here)
        logs\\             (RC-069-002: persistent file logging)
        shaders\\          (RC-069-002: GPU LAB user-owned SAVE/LOAD default,
                            replacing the old repo-relative `user_shaders/`
                            assumption)

`get_app_data_dir()` requires `QApplication.setApplicationName("ToroidAMP")`
to already have been called for `QStandardPaths` to resolve the intended
per-machine local directory — `__main__.py` already does this before
constructing anything that touches this module. Without it, Qt falls back
to using the interpreter's own process name as a folder segment (a
pre-existing, harmless dev/test-only quirk — see
docs/release/RC_069_001_release_inventory.md §9).
"""

import logging
import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths

logger = logging.getLogger("toroidamp.paths")


def get_app_data_dir() -> Path:
    """
    Resolves, and idempotently creates, the root ToroidAMP application-data
    directory. Safe to call repeatedly and from any thread that already has
    a QApplication constructed — never raises; a creation failure is logged
    and the (possibly non-existent) path is still returned, so callers can
    decide how to degrade rather than have this module crash startup.
    """
    base_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    if not base_dir:
        base_dir = os.path.expanduser("~/.config/ToroidAMP")

    target_dir = Path(base_dir)
    # Prevent duplicate nested 'ToroidAMP/ToroidAMP' (same guard session.py
    # has always used — kept here since this is now the shared root).
    if target_dir.name != "ToroidAMP":
        target_dir = target_dir / "ToroidAMP"

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"Could not create application data directory '{target_dir}': {e}")

    return target_dir


def get_logs_dir() -> Path:
    """Idempotently resolves+creates %LOCALAPPDATA%\\ToroidAMP\\logs\\."""
    d = get_app_data_dir() / "logs"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"Could not create logs directory '{d}': {e}")
    return d


def get_user_shaders_dir() -> Path:
    """
    Idempotently resolves+creates %LOCALAPPDATA%\\ToroidAMP\\shaders\\ — the
    GPU LAB's user-owned SAVE/LOAD default location (RC-069-002). Distinct
    from the bundled, read-only `assets/official_shaders/` resolved via
    `resources.py` — this directory is for the user's OWN loaded/saved
    shaders and presets, never pre-populated by ToroidAMP itself.
    """
    d = get_app_data_dir() / "shaders"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"Could not create user shaders directory '{d}': {e}")
    return d
