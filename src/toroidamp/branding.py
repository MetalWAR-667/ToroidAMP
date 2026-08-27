"""
ToroidAMP - Branding Asset Resolution

Single resolution point for the official application icon (the red/white
checkerboard toroid). Never depends on the current working directory.

Missing branding must never prevent startup: every accessor here returns a
safe fallback (None) and logs a warning rather than raising. Callers decide
what to do without an icon — the application always keeps running.
"""

import logging
from importlib.resources import files as _pkg_files
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QIcon

logger = logging.getLogger("toroidamp.branding")

_ICON_RELATIVE = Path("assets") / "branding" / "toroidamp_icon.png"


def resolve_branding_icon_path() -> Optional[Path]:
    """
    Resolves the official branding master PNG, packaging-safe:

    1. Inside the `toroidamp` package itself (`assets/branding/toroidamp_icon.png`
       relative to the package). This works identically for an editable dev
       install and a real installed wheel/sdist that ships the asset as
       package data (see pyproject.toml `[tool.setuptools.package-data]`) —
       no filesystem layout assumptions either way.
    2. Falls back to the repo-root checkout location, for a development
       tree where the package-internal copy hasn't been synced from the
       human-facing authoritative master yet.

    Returns None (never raises) if neither resolves.
    """
    try:
        candidate = _pkg_files("toroidamp") / "assets" / "branding" / "toroidamp_icon.png"
        if candidate.is_file():
            return Path(str(candidate))
    except Exception:
        pass

    try:
        checkout_root = Path(__file__).resolve().parents[2]
        candidate = checkout_root / _ICON_RELATIVE
        if candidate.is_file():
            return candidate
    except Exception:
        pass

    return None


def resolve_branding_icon() -> Optional[QIcon]:
    """Returns the official QIcon, or None (with a logged warning) if unavailable."""
    path = resolve_branding_icon_path()
    if path is None:
        logger.warning(
            "ToroidAMP branding icon not found (expected 'assets/branding/toroidamp_icon.png' "
            "inside the installed package or the repo checkout). Continuing without an "
            "official application icon."
        )
        return None

    icon = QIcon(str(path))
    if icon.isNull():
        logger.warning(f"ToroidAMP branding icon at '{path}' could not be loaded as a valid image.")
        return None

    return icon
