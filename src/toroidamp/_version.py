"""
ToroidAMP - Canonical Version Resolution

Single source of truth: `pyproject.toml`'s `[project].version`.

`importlib.metadata` alone is not sufficient here: for an editable install,
its snapshot is written once at install time and does not live-reflect
further edits to pyproject.toml (e.g. from tools/bump_version.py) without a
reinstall. Reading pyproject.toml directly keeps the running application
honest about the actual working tree during day-to-day development, while
falling back to installed package metadata for a real (non-editable,
non-checkout) install where pyproject.toml may not ship alongside the code.
"""

import tomllib
from importlib import metadata as _metadata
from pathlib import Path

FALLBACK_VERSION = "0.0.0-dev"


def _from_pyproject() -> str | None:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except Exception:
        return None


def _from_installed_metadata() -> str | None:
    try:
        return _metadata.version("toroidamp")
    except _metadata.PackageNotFoundError:
        return None


def resolve_version() -> str:
    return _from_pyproject() or _from_installed_metadata() or FALLBACK_VERSION
