# -*- mode: python ; coding: utf-8 -*-
"""
ToroidAMP - PyInstaller ONEDIR Build Configuration (RC-069-003)

Reproducible build:
    pyinstaller packaging/toroidamp.spec

Output:
    dist/ToroidAMP/ToroidAMP.exe   (+ its supporting ONEDIR payload)

v0.666: windowed (console=False) for normal packaged launch -- ToroidAMP is
a music player, not a diagnostic console. This is safe now that
`__main__.py::setup_logging()` (RC-069-002) writes a durable rotating log
file (`%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log`) independent of the
console handler; a packaged build with no console still has full startup/
runtime diagnostics on disk. Console output itself is untouched -- running
from source (`python -m toroidamp`, the `toroidamp` console script) still
prints to whatever terminal invoked it, exactly as before; only the frozen
.exe's own window changes.

This spec is otherwise still a first, honest PROOF-OF-CONCEPT: ONEDIR (not
ONEFILE), no size optimization, no aggressive Qt pruning. It documents ONLY
what PyInstaller cannot reliably infer on its own:

  - product runtime assets (RC-069-002's package-data set — themes,
    official shaders, images, branding);
  - package version metadata (`importlib.metadata.version("toroidamp")`
    needs real dist-info present in the frozen bundle, or the app's
    existing 3-tier version fallback silently lands on its "0.0.0-dev"
    sentinel — see src/toroidamp/_version.py);
  - pyttsx3's platform-specific TTS driver module, which it imports
    dynamically (`__import__`) rather than statically, invisible to
    PyInstaller's normal import-graph analysis;
  - pygame's own bundled native DLLs (including libxmp.dll, which
    TrackerDecoder loads dynamically via `ctypes.CDLL` — also invisible to
    static import analysis, per RC-069-002B's explicit recommendation).

Everything else (PySide6/Qt plugins, numpy, sounddevice, soundfile, the
rest of pygame) is left to PyInstaller's own well-established hooks —
per this cut's explicit instruction, correctness first, no premature
pruning or cargo-cult hidden-import lists.
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), ".."))
ENTRY_SCRIPT = os.path.join(REPO_ROOT, "packaging", "run_toroidamp.py")
ICON_PATH = os.path.join(REPO_ROOT, "src", "toroidamp", "assets", "branding", "toroidamp.ico")

block_cipher = None

# --- Product runtime assets (RC-069-001/002's package-data set) ------------
# collect_data_files() walks the `toroidamp` package's own non-.py files —
# the exact same mechanism `resources.py`'s `importlib.resources` primary
# tier expects to find populated at runtime. Reusing this hook (rather than
# hand-listing every asset path here a second time) means this spec cannot
# silently drift out of sync with pyproject.toml's package-data set.
datas = collect_data_files("toroidamp")

# --- Release legal/user documentation (RC-069-003B) -------------------------
# A public ONEDIR distribution should carry its own license, third-party
# notices, and full third-party license texts alongside the executable —
# not just inside the source checkout nobody frozen-build users have.
# HOWTOUSE is included for the same reason (it's the practical user guide);
# CHANGELOG is small and directly useful to an end user checking what
# changed, so it is included too rather than left checkout-only. Developer-
# only material (docs/, tests/, experiments/) is deliberately NOT collected.
_RELEASE_DOCS = [
    ("LICENSE", "."),
    ("THIRD_PARTY_NOTICES.md", "."),
    ("HOWTOUSE.md", "."),
    ("CHANGELOG.md", "."),
    ("licenses", "licenses"),
]
for _src_name, _dest_dir in _RELEASE_DOCS:
    _src_path = os.path.join(REPO_ROOT, _src_name)
    if os.path.isdir(_src_path):
        for _root, _dirs, _files in os.walk(_src_path):
            for _fname in _files:
                _full = os.path.join(_root, _fname)
                _rel_dir = os.path.join(_dest_dir, os.path.relpath(_root, _src_path))
                datas.append((_full, _rel_dir))
    elif os.path.isfile(_src_path):
        datas.append((_src_path, _dest_dir))

# --- Version metadata ---------------------------------------------------
# Without this, a frozen build has no pyproject.toml (tier 1 of
# _version.py's fallback fails) AND no dist-info (tier 2 also fails),
# silently landing on the "0.0.0-dev" sentinel — exactly the requirement
# RC-069-002/002B both flagged and left for this cut to actually apply.
datas += copy_metadata("toroidamp")

# --- pyttsx3's Windows SAPI5 driver -----------------------------------------
# pyttsx3 selects its platform backend via a dynamic `__import__()` inside
# its own engine factory, not a static `import` statement — invisible to
# PyInstaller's import-graph analysis. Confirmed dependency, not a
# preemptive guess (RC-069-002 declared pyttsx3/pywin32/comtypes as real,
# used dependencies).
hiddenimports = ["pyttsx3.drivers", "pyttsx3.drivers.sapi5"]

# --- pygame's own bundled native DLLs (incl. libxmp.dll) --------------------
# TrackerDecoder loads libxmp.dll via ctypes.CDLL(path) at runtime — a
# dynamic load PyInstaller's static analysis cannot see. pygame's own DLLs
# (SDL2 family, libxmp) are collected explicitly and defensively, per
# RC-069-002B's explicit recommendation, rather than assumed to be swept up
# incidentally by the base PySide6/pygame hooks.
binaries = collect_dynamic_libs("pygame")

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[os.path.join(REPO_ROOT, "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ToroidAMP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # RC-069-003 explicit non-goal: no UPX merely to reduce size
    console=False,  # v0.666: windowed release build; see module docstring
    icon=ICON_PATH if os.path.isfile(ICON_PATH) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ToroidAMP",
)

# --- Public portable-layout doc copies (RC-069-003C) ------------------------
# PyInstaller 6+ ONEDIR nests everything COLLECT()-ed (including the
# `datas` entries above) under `_internal/`, by design, to keep the
# top-level dist folder clean -- there is no `datas` destination that
# resolves outside `_internal/` short of reverting the whole build to the
# legacy flat `contents_directory=''` layout, which would move every DLL
# and not just these docs (a real architectural change, out of scope for
# a documentation cut). So a user opening the portable ONEDIR folder only
# sees ToroidAMP.exe at the top level; the release docs are one level
# down in _internal/.
#
# To make LICENSE/HOWTOUSE/THIRD_PARTY_NOTICES/licenses/ actually visible
# next to ToroidAMP.exe (what a user opening the folder will look for
# first), this step copies them a second time directly into the
# top-level dist/ToroidAMP/ folder, after COLLECT has already written it.
# This runs after `coll` above, so dist/ToroidAMP/ already exists. The
# _internal/ copies from the `datas` mechanism are left in place too
# (harmless, and keeps _internal/ self-contained); this is a deliberate
# duplication, not a move.
import shutil

_DIST_ROOT = os.path.join(DISTPATH, "ToroidAMP")
_PUBLIC_LAYOUT_DOCS = [
    ("LICENSE", "file"),
    ("THIRD_PARTY_NOTICES.md", "file"),
    ("HOWTOUSE.md", "file"),
    ("CHANGELOG.md", "file"),
    ("licenses", "dir"),
]
if os.path.isdir(_DIST_ROOT):
    for _name, _kind in _PUBLIC_LAYOUT_DOCS:
        _src = os.path.join(REPO_ROOT, _name)
        _dst = os.path.join(_DIST_ROOT, _name)
        if _kind == "file" and os.path.isfile(_src):
            shutil.copy2(_src, _dst)
        elif _kind == "dir" and os.path.isdir(_src):
            shutil.copytree(_src, _dst, dirs_exist_ok=True)
