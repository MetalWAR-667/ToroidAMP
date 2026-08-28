"""
ToroidAMP - Central Runtime Resource Resolution (RC-069-002)

Single resolution strategy for every bundled, READ-ONLY package asset
(theme QSS/fonts/images, official GPU shaders, packaged GPU textures) —
consolidates what were previously several independent, duplicated
`Path(__file__).resolve().parent...` implementations scattered across
`theme.py` and the GPU visualizer/canvas modules (one of which — the old
`theme.py` checkout-fallback — was found to be silently broken during this
consolidation; see docs/release/RC_069_002_runtime_hygiene.md).

Resolution order, safe across all three deployment shapes RC-069-001
identified:

    A. source checkout (editable install)
    B. a normal installed Python package (wheel/sdist)
    C. a future frozen PyInstaller application

1. `importlib.resources.files("toroidamp")` — the packaging-correct path.
   Works identically for an editable install and a real installed
   wheel/sdist, PROVIDED the asset is declared in pyproject.toml's
   `[tool.setuptools.package-data]` (see RC-069-002's package-data fix).
2. A direct filesystem path relative to this module's own package
   directory (`Path(__file__).resolve().parent`, i.e. `src/toroidamp/` in
   a checkout, or the installed package directory otherwise) — a
   convenience fallback for a source checkout whose package-data hasn't
   been synced/declared yet. This is NOT a different "master copy"
   concept (branding.py's separate repo-root master-mirror fallback is
   its own, deliberately distinct thing — see branding.py) — it is the
   SAME package-internal location as tier 1, just resolved without
   `importlib.resources`.

Never raises. Returns `None` on total failure; every caller decides its
own missing-asset behavior (log a warning and continue, never crash).
"""

import logging
from importlib.resources import files as _pkg_files
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger("toroidamp.resources")

_PACKAGE_DIR = Path(__file__).resolve().parent  # src/toroidamp (checkout) or the installed package dir


def resolve_package_asset(relative_subpath: Union[str, Path]) -> Optional[Path]:
    """
    Resolves `relative_subpath` (e.g. "assets/themes/default/theme.qss" or
    "assets/official_shaders/cyber_bloom.frag") relative to the `toroidamp`
    package root. Returns an absolute `Path` if found, else `None`.
    """
    rel_posix = Path(relative_subpath).as_posix()

    try:
        candidate = _pkg_files("toroidamp") / rel_posix
        if candidate.is_file():
            return Path(str(candidate))
    except Exception:
        pass

    try:
        candidate = _PACKAGE_DIR / relative_subpath
        if candidate.is_file():
            return candidate
    except Exception:
        pass

    return None
