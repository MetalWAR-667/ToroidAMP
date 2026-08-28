# RC-069-002 — Packaging Prerequisites & Runtime Hygiene

> **Status: IMPLEMENTED.** Source tree is now materially closer to
> ONEDIR-ready. Several concrete RC-069-001 blockers are resolved and
> empirically verified (not just theorized); the tracker/libmodplug and
> license items remain genuinely BLOCKED per honest investigation — see §7
> and §12.

## 0. Phase-0 Revalidation

Every RC-069-001 blocker relevant to this cut was reproduced/verified
before touching anything, per the mission's explicit instruction not to
mechanically implement a stale document:

| RC-069-001 finding | Revalidation result |
|---|---|
| Package-data gap (themes/shaders/images missing) | **Confirmed still true** — `pyproject.toml` still only declared `assets/branding/*`. |
| Tracker backend absent | **Confirmed still true** — `TrackerDecoder.is_available()` returns `False` in this environment right now; direct filesystem search of `pygame`'s bundled DLLs confirms `libmodplug-1.dll`/`libmodplug.dll` are absent (this build ships `libxmp.dll` instead — a different library with a different, incompatible API). |
| `miniaudio` declared, unused | **Confirmed still true** — zero imports anywhere in `src/toroidamp`. |
| `pyttsx3`/`pywin32`/`comtypes` used, undeclared | **Confirmed still true** — all three installed in this venv out-of-band (`pyttsx3==2.99`, `pywin32==312`, `comtypes==1.4.16`), none in `pyproject.toml`. |
| GPU LAB `user_shaders/`-relative path assumption | **Confirmed still true** — `fullscreen.py`'s three LAB dialog methods all computed `Path(__file__).resolve().parent.parent.parent.parent / "user_shaders"`. |
| No durable file logging | **Confirmed still true** — `logging.basicConfig()` console-only, no `FileHandler` anywhere. |
| No LICENSE found | **CORRECTED (not stale-confirmed, genuinely wrong)** — a `./LICENSE` file DOES exist at the repo root; RC-069-001 missed it. However, its actual content is `Copyright (c) 2026 MetalWAR` — a bare copyright notice with **no license grant, no permissions, no terms of any kind**. The corrected finding is not "no LICENSE file" but "a LICENSE file exists that does not actually constitute a license" — see §12, still a release blocker, just a more precise one. |
| Version metadata drift (`0.1.0` installed vs. `0.3.1` in pyproject.toml) | **Confirmed still true** — direct `pip list` check reproduces exactly this; root cause confirmed as ordinary editable-install dist-info staleness (see §11), not a source-of-truth defect. |

Git status was clean at the start of this cut (`nothing to commit, working
tree clean`) — no unrelated in-progress work was at risk of being
overwritten.

---

## 1-2. Resource-Resolution Architecture & Package Data

**One coherent strategy, not three.** Previously there were two
independently-duplicated implementations of essentially the same
"try `importlib.resources`, fall back to a `__file__`-relative path" logic
(`theme.py`'s own `_resolve_asset_path`, and `branding.py`'s own inline
version) **plus a third, structurally different pattern** (plain
`Path(__file__).resolve().parent.parent`, no `importlib.resources` at all)
used independently by `gpu_canvas.py`, `toroid_identity.py`,
`cyber_bloom.py`, and `audio_reactive_reference.py`.

**Consolidated into one new module**, [`src/toroidamp/resources.py`](../../src/toroidamp/resources.py):

```python
def resolve_package_asset(relative_subpath) -> Optional[Path]:
    # 1. importlib.resources.files("toroidamp") / relative_subpath
    # 2. Path(__file__).resolve().parent / relative_subpath  (checkout convenience)
    # Never raises. Returns None if neither resolves.
```

- `theme.py`'s `_resolve_asset_path`/`resolve_theme_asset_path` now delegate
  to it directly (all 6 call sites updated: theme QSS ×2, font, and 4
  CYBER YELLOW images).
- `branding.py` now calls it for its primary (package-internal) tier, and
  keeps its own **separate, deliberate** repo-root "authoritative master
  mirror" fallback as an additional tier — this is NOT the same concept as
  the checkout-convenience fallback inside `resolve_package_asset` (the
  master mirror lives at `<repo_root>/assets/branding/`, a genuinely
  different location with its own sync workflow via
  `tools/generate_ico.py`), so it was deliberately kept distinct rather
  than forced into the shared helper.
- `gpu_canvas.py`'s packaged-texture resolver and all three official
  visualizer descriptors (`toroid_identity.py`, `cyber_bloom.py`,
  `audio_reactive_reference.py`) now call
  `resolve_package_asset("assets/official_shaders/<name>.frag")` /
  `resolve_package_asset("assets/images/ToroidAMP.png")` instead of their
  own ad-hoc `Path(__file__).resolve().parent.parent` computation.

**A real, previously-undetected bug was found and fixed while
consolidating**: `theme.py`'s OLD checkout-fallback computed
`checkout_root = Path(__file__).resolve().parents[2]` (= `src/`, from
`src/toroidamp/ui/theme.py`) then appended `"src" / "toroidamp" /
relative_subpath` — producing `.../src/src/toroidamp/...`, a doubled `src`
segment that **never resolved to a real file**. This was completely masked
because the `importlib.resources` primary tier always succeeded in every
development/test run (editable install). Verified directly before the fix:
`candidate.exists()` was `False` for this exact path. The new shared
resolver's fallback tier (`Path(__file__).resolve().parent`, i.e. this
module's OWN package directory) does not have this bug, and is now the
single implementation all four resolvers share — so it can't drift back
out of sync independently.

### pyproject.toml package-data

```toml
[tool.setuptools.package-data]
toroidamp = [
    "assets/branding/*.png",
    "assets/branding/*.ico",
    "assets/images/*.png",
    "assets/official_shaders/*.frag",
    "assets/themes/**/*",
]
```

Deliberately **excludes** `tests/`, `docs/`, `experiments/`, `tools/`,
`user_shaders/` (git-ignored, and not a package concept at all) — only
runtime product assets are declared, per the mission's explicit "do not
blindly include the entire repository" instruction.

### Exact package-data inventory (empirically verified, not assumed)

A real wheel was built (`python -m build --wheel`) and its contents
inspected directly — not merely "should work per the config":

```text
toroidamp/assets/branding/toroidamp.ico
toroidamp/assets/branding/toroidamp_icon.png
toroidamp/assets/images/ToroidAMP.png
toroidamp/assets/images/toroidamp_video_thumbnail.png   (see §14 — README-only, harmless to include, not runtime-loaded)
toroidamp/assets/official_shaders/audio_reactive_reference.frag
toroidamp/assets/official_shaders/cyber_bloom.frag
toroidamp/assets/official_shaders/minimal_reference.frag
toroidamp/assets/official_shaders/toroid_identity.frag
toroidamp/assets/themes/cyber_yellow/fonts/license.txt
toroidamp/assets/themes/cyber_yellow/fonts/quantum.ttf
toroidamp/assets/themes/cyber_yellow/fonts/readme.txt
toroidamp/assets/themes/cyber_yellow/images/chassis.png
toroidamp/assets/themes/cyber_yellow/images/hazard_strip.png
toroidamp/assets/themes/cyber_yellow/images/logo.png
toroidamp/assets/themes/cyber_yellow/images/panel_brushed_metal.png
toroidamp/assets/themes/cyber_yellow/images/wordmark.png
toroidamp/assets/themes/cyber_yellow/theme.qss
toroidamp/assets/themes/default/theme.qss
```

Then that exact wheel was **installed into a fresh, throwaway, non-editable
venv** (`wheel_test_venv`, deleted after verification — never committed)
and every resource re-resolved from there:

```text
toroidamp.__file__: ...\wheel_test_venv\Lib\site-packages\toroidamp\__init__.py
theme:     ...\wheel_test_venv\Lib\site-packages\toroidamp\assets\themes\default\theme.qss
cyber qss: ...\wheel_test_venv\Lib\site-packages\toroidamp\assets\themes\cyber_yellow\theme.qss
font:      ...\wheel_test_venv\Lib\site-packages\toroidamp\assets\themes\cyber_yellow\fonts\quantum.ttf
shader:    ...\wheel_test_venv\Lib\site-packages\toroidamp\assets\official_shaders\cyber_bloom.frag
image:     ...\wheel_test_venv\Lib\site-packages\toroidamp\assets\images\ToroidAMP.png
```

This is the exact scenario ("B. a normal installed Python package") that
RC-069-001 predicted would break — **empirically confirmed fixed**, not
just configured differently.

---

## 3. Resource-Access Regression Tests

`tests/test_rc_069_002.py::TestRC069002ResourcePaths` — theme, official
shader, and GPU texture resolution; a dedicated foreign-CWD test
(`test_07_resource_lookup_works_from_foreign_cwd`, `chdir`s to the OS temp
directory before resolving) proves resolution is anchored to the package
location, never the process's current working directory.

---

## 4. Runtime Dependency Declaration Cleanup

```toml
dependencies = [
    "PySide6>=6.6.0",
    "pygame-ce>=2.5.0",
    "numpy>=1.24.0",
    "sounddevice>=0.4.6",
    "soundfile>=0.12.0",
    "pyttsx3>=2.90",
    "pywin32>=305; sys_platform == 'win32'",
    "comtypes>=1.1.14; sys_platform == 'win32'",
]
```

- **`miniaudio` removed** — confirmed genuinely dead (zero imports
  anywhere in `src/toroidamp`; `ConventionalDecoder` uses `soundfile`
  exclusively for MP3/WAV/OGG/FLAC).
- **`pyttsx3` declared** as a hard dependency — it backs the documented
  core startup-lifecycle voice line (RC-069-001's own "IN 0.69" feature
  inventory), so a clean install should get a working voice feature by
  default, matching the currently-working dev experience. `voice.py`'s
  existing `try/except ImportError` (`TTS_AVAILABLE` flag) is completely
  unchanged — this declaration makes the happy path reproducible, it does
  not remove the defensive fallback for whatever edge case still lacks it.
- **`pywin32`/`comtypes` declared with `sys_platform == 'win32'` markers**
  — these are specifically `pyttsx3`'s Windows SAPI5 backend's own
  dependencies (macOS/Linux use different, unrelated TTS backends with no
  pywin32/comtypes involvement at all), so they are not forced onto every
  OS despite ToroidAMP's classifiers claiming
  `Operating System :: OS Independent`.
- **`pytest` added as a new `test` extra** (`[project.optional-dependencies]`)
  — previously installed ad hoc with no declaration anywhere, making a
  clean test-environment setup non-reproducible. `dev` (Pillow, for
  `tools/generate_ico.py`) is unchanged.

### Intentionally undeclared

Nothing else was found actually imported-but-undeclared. `cffi`/`pycparser`
present in this venv are ordinary transitive dependencies of
`soundfile`/`sounddevice`'s own CFFI bindings — not something ToroidAMP
itself needs to declare.

---

## 5-8. Tracker Backend — libmodplug

### Complete audit of `TrackerDecoder` (unchanged by this cut except §8's failure-semantics fix)

- **Discovery order** (`_discover_libmodplug`): (1) inside `pygame`'s
  installed package directory, checking for
  `libmodplug-1.dll`/`libmodplug.dll` (Windows) or
  `libmodplug.so.1`/`libmodplug.so` (Linux); (2)
  `ctypes.util.find_library("modplug")` (system-wide discovery); (3) a
  short hardcoded fallback candidate list.
- **Loading**: `ctypes.CDLL(self._dll_path)` — a fully dynamic runtime load,
  invisible to static import-graph analysis (relevant for packaging, §12
  of the RC-069-001 survey — not re-litigated here).
- **Exact API surface used** (`_bind_functions`): `ModPlug_Load`,
  `ModPlug_Unload`, `ModPlug_Read`, `ModPlug_GetName`,
  `ModPlug_GetLength`, `ModPlug_Seek` — the classic `libmodplug.h` C API.
- **Architecture expectation**: implicit — whatever architecture matches
  the running Python interpreter (no explicit bitness check in the code);
  a 64-bit Python process requires a 64-bit `libmodplug` DLL.
- **Does it expect a system install?** No — tier 1 explicitly checks
  *inside pygame's own install directory first*, i.e. the code's own
  design intent is "ride along with whatever pygame's Windows wheel
  bundles," not "require the user to install something globally."

### The actual finding: this design intent no longer holds

**Direct inspection of the actual installed `pygame-ce==2.5.8`'s bundled
DLLs in this environment shows no `libmodplug*` file at all** — instead,
`libxmp.dll` is present. `libxmp` is a **different tracker library with a
different, incompatible C API** (`xmp_*` function names, not `ModPlug_*`)
— even if discovery were pointed at it, `_bind_functions()`'s
`getattr(self._modplug, "ModPlug_Load")` would raise `AttributeError`
(symbol not found), not work. Retargeting `TrackerDecoder` to libxmp's API
would be a real, non-trivial rewrite of the binding layer — explicitly out
of scope for this cut (a source-code architecture change, not a packaging
prerequisite fix).

**No usable `libmodplug` binary was found anywhere reasonably searchable
on this machine** (pygame's own directory; `ctypes.util.find_library`;
`C:\Windows\System32`, `C:\Program Files`, `C:\Program Files (x86)`
searched directly, read-only, nothing downloaded).

### Acquisition strategy (documented, not executed this cut)

Per the mission's explicit "do not download arbitrary DLLs from random
binary sites" and "do not silently install global system dependencies"
constraints, **no binary was fetched**. Reproducible, legitimate sourcing
options for Metal to choose from and execute manually:

1. **vcpkg** (`vcpkg install libmodplug:x64-windows`) — reproducible,
   version-pinned, widely used for exactly this kind of native Windows
   dependency; produces a real, redistributable `libmodplug-1.dll` this
   project could then bundle and add to `_discover_libmodplug()`'s search
   list.
2. **Build from the official libmodplug/OpenMPT-derived source** with
   MSVC — more control, more effort.
3. **A NuGet package** providing a prebuilt `libmodplug` DLL, if one with
   acceptable provenance exists — least effort if suitable.

Whichever source is chosen, the redistribution posture should mirror what
this project already does correctly for `soundfile`/PortAudio (§17 of
RC-069-001): dynamic linking, DLL shipped alongside the executable, not
statically merged.

### Status: **TRACKER BACKEND — BLOCKED.**

MOD/XM/IT/S3M support is **not release-validated** and must not be claimed
as working in 0.69 until a real `libmodplug` binary is sourced and
validated per §7 of the mission (real-file smoke test) — not attempted
this cut, since none is available. This is an honest, explicit blocker,
not a silently-weakened claim.

### Failure semantics — real bug found and fixed

Independent of whether libmodplug is ever resolved, the mission required
verifying the app **fails cleanly** when tracker support is unavailable.
It did not. Traced the exact code path: `PlayerEngine.load()` called
`self._get_tracker_decoder()` (which constructs `TrackerDecoder`, raising
`RuntimeError` when libmodplug is missing) **before** entering the
`try/except` block that populates `_decoder_failed`/`_last_error_msg` —
the same bookkeeping `WindowManager._tick()` polls every frame to cleanly
log-and-auto-advance the playlist on any other decode failure (corrupted
MP3, etc.). The tracker-unavailable `RuntimeError` bypassed this entirely:
`window_manager.py`'s `load_and_play()` catches it (so the app does not
crash), but the playlist's `current_index` is left pointing at the failed
track with no playback, no auto-advance, and no `_decoder_failed`-tracked
error — a genuinely silent failure from the user's perspective, exactly
what mission §8 exists to prevent.

**Fix** (`src/toroidamp/audio/player.py::PlayerEngine.load`): moved
decoder selection/construction *inside* the existing `try:` block, so a
missing-tracker-backend failure now gets **identical** treatment to every
other decode failure. Verified directly — with libmodplug genuinely absent
in this environment, loading a `.mod` file now sets `decoder_failed=True`
and populates `check_and_clear_error()` with the real path and message,
exactly like a corrupted MP3 would. Zero change to the success path or to
any other decoder's behavior.

---

## 9-11. User-Writable Path Policy & GPU LAB Shader Path

New module [`src/toroidamp/paths.py`](../../src/toroidamp/paths.py) —
the **writable counterpart** to `resources.py`'s read-only asset
resolution, deliberately kept as a separate concept per the mission's
explicit instruction (§10):

```text
%LOCALAPPDATA%\ToroidAMP\
    session.json    (unchanged — session.py now delegates its shared root-
                      directory resolution to paths.get_app_data_dir(),
                      keeping only its own filename + legacy-migration logic)
    logs\            (new — RotatingFileHandler target, §12-14)
    shaders\         (new — GPU LAB SAVE/LOAD default, replacing the old
                      repo-relative `user_shaders/` assumption)
```

`get_app_data_dir()` / `get_logs_dir()` / `get_user_shaders_dir()` are all
idempotent (`mkdir(parents=True, exist_ok=True)`, safe to call repeatedly,
never raise — a creation failure is logged and the path still returned
rather than crashing startup). `session.py` was refactored to call
`get_app_data_dir()` instead of duplicating the `QStandardPaths` +
anti-double-nesting logic inline — one fewer place for that logic to drift.

**GPU LAB path fix** (`fullscreen.py`'s three dialog methods —
`_load_local_shader_dialog`, `_save_lab_preset_dialog`,
`_load_lab_preset_dialog`): all now default to `get_user_shaders_dir()`
instead of a repo-checkout-relative, git-ignored `user_shaders/` folder
that exists in no real install. The user can still browse anywhere via the
standard `QFileDialog` — only the *default starting directory* changed.
**Official shaders remain a completely separate, bundled, read-only
concept** (`resources.py`'s territory) — nothing in this cut copies any
repository test/official shader into AppData; the new `shaders\` directory
starts genuinely empty and is only ever populated by the user's own
SAVE/LOAD actions.

---

## 12-14. Persistent Logging & Startup Failure Capture

`__main__.py::setup_logging()` now configures **both** a console handler
(unchanged, dev-friendly) and a `RotatingFileHandler` targeting
`%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log` (2 MiB per file, 3 backups —
~8 MiB ceiling, never unbounded). Idempotent via a marker attribute on
each handler (`_toroidamp_handler`) checked before adding new ones —
calling `setup_logging()` twice in one process adds zero duplicate
handlers (verified directly). A file-creation failure (permissions, full
disk) is caught, logged to the still-live console handler, and startup
proceeds console-only — file logging can degrade, never block, startup.

**Startup failure capture**: `main()`'s body was extracted into `_run()`
and wrapped in a `try/except Exception` that calls `logger.exception(...)`
(capturing the full traceback into both the console AND the now-configured
file log) before **re-raising unchanged** — `SystemExit` passes through
untouched so the normal `sys.exit(exit_code)` path is unaffected. This is
the minimal top-level capture the mission asked for, not a crash
reporter: no dialog, no telemetry, no swallowed exceptions — a guarantee
that a startup failure has a real chance of being *found* later via the
persistent log, which matters specifically because a packaged
`--windowed`/no-console build has no console for a bare traceback to land
on at all.

**Privacy — LOCAL ONLY, explicitly**: no log content is ever sent
anywhere. Verified directly (`test_11b_no_network_handlers_present`) that
no `SocketHandler`/`HTTPHandler`/`SMTPHandler`/`SysLogHandler` — or
anything resembling one — is attached. Existing log statements throughout
the codebase were audited by inspection during this cut and found to log
file *paths* (for diagnostics — e.g. "Failed to load audio file
'<path>'") but never file *contents*; no credentials, tokens, or secrets
exist anywhere in this codebase's log statements to begin with. This
statement is the explicit privacy contract for 0.69: **no network
reporting, no telemetry, of any kind.**

---

## 15-17. License, Notices, Version Metadata

### License — RELEASE BLOCKER (corrected finding)

RC-069-001 stated "no LICENSE file found" — **this was factually
incorrect**, and per this mission's Phase-0 instruction to report (not
silently carry forward) a stale/wrong finding: `./LICENSE` genuinely
exists at the repo root. However, its entire content is:

```text
Copyright (c) 2026 MetalWAR
```

This is a bare copyright notice with **no license grant, no stated
permissions, no terms** — legally, absent an actual grant, this defaults
toward "all rights reserved," which is in tension with the project's own
`pyproject.toml` description and public, open GitHub presence. `pyproject.toml`
has no `license` field either, and `README.md` makes no licensing
statement.

**Per explicit instruction, no license was invented or chosen by this
cut.** Reporting exactly as required:

> **RELEASE BLOCKER — project license decision required.** A LICENSE file
> exists but does not contain an actual license grant. Metal needs to
> choose and add real license terms (MIT, GPL, Apache-2.0, or whatever the
> project intends) before any public release artifact ships, and ideally
> also add a matching `license`/`license-files` entry to `pyproject.toml`
> so it is machine-readable by packaging tooling (setuptools already
> auto-included the bare file into the wheel's `dist-info/licenses/`
> during this cut's verification build, confirming the mechanism works —
> it just has nothing substantive to include yet).

### Third-party notices

No `THIRD_PARTY_NOTICES.txt` was created this cut — the mission frames it
as a "possible future artifact," and creating an empty/placeholder file
now would be premature. Instead, here is the precise checklist for when it
is created (content largely inherited from RC-069-001 §17, re-verified,
not re-derived from scratch):

| Component | License | Action needed for the notices file |
|---|---|---|
| Qt6 / PySide6 | LGPLv3 | Include Qt's own license text/notice; confirm dynamic-linking compliance in the final packaged layout (separate DLLs, not merged) |
| libsndfile (via `soundfile`) | LGPLv2.1 | Same dynamic-linking posture |
| PortAudio (via `sounddevice`) | MIT | Attribution line |
| pygame-ce + its bundled SDL2-ecosystem libs (SDL2, libogg, libopus, libpng, libjpeg, libtiff, libwebp, libxmp, freetype) | Mixed zlib/BSD/LGPL family | Copy pygame-ce's own bundled NOTICE/license files verbatim — do not re-derive |
| libmodplug (if/when sourced, §7) | LGPLv2.1 (OpenMPT-derived) | **Cannot be finalized until a real binary is actually sourced** — flagged unresolved |
| `quantum.ttf` (CYBER YELLOW font) | Per `assets/themes/cyber_yellow/fonts/license.txt`/`readme.txt` (bundled alongside it) | Read those two files directly and transcribe their exact terms — not independently re-verified in this pass either, carried forward as a to-do |
| pyttsx3 / pywin32 / comtypes | MPL-2.0 / PSF-derived / MIT respectively | Attribution lines — low friction |
| numpy | BSD-3-Clause | Attribution line |

### Version metadata — drift explained, no defect found

Confirmed the observed drift (`toroidamp==0.1.0` installed vs. `0.3.1` in
`pyproject.toml`) is **ordinary editable-install dist-info staleness, not
a source-of-truth defect** — `_version.py`'s own documented 3-tier
fallback (`pyproject.toml` direct read → `importlib.metadata` →
`"0.0.0-dev"` sentinel) already self-corrects this in every real scenario
that matters:

- **Source checkout** (today): tier 1 always wins, reads `pyproject.toml`
  live — always current, drift is invisible to the running app.
- **Real (non-editable) wheel install**: `pyproject.toml` doesn't ship
  inside the wheel, so tier 1 fails cleanly (caught `Exception`) and tier 2
  (`importlib.metadata.version("toroidamp")`) takes over, reading the
  wheel's own `dist-info/METADATA` — which is **always correct at build
  time** (verified: this cut's test wheel build correctly stamped
  `toroidamp-0.3.1.dist-info`), so no drift is possible there either.
- **Frozen PyInstaller build (future, RC-069-003)**: tier 2 requires the
  package's `dist-info` metadata to actually be present in the frozen
  bundle. **PyInstaller does not include this automatically** — confirmed
  requirement, carried forward from RC-069-001: **`--copy-metadata
  toroidamp`** (or the Nuitka equivalent) must be an explicit build flag,
  or a frozen build silently falls through to the `"0.0.0-dev"` sentinel.
  This is now the single, precise, actionable requirement for
  RC-069-003's spec — no further ambiguity remains.

**No version was bumped.** `0.3.1` remains authoritative until the actual
0.69 release sequence.

---

## 18. Dead / Unreferenced Asset — `toroidamp_video_thumbnail.png`

**Reverified, and reclassified — not deleted.** Confirmed via direct
search: zero references in `src/toroidamp` (the running application never
loads it) — RC-069-001 correctly found this half of the picture. But it
**is** referenced, directly, in `README.md`:

```markdown
[![Watch ToroidAMP melt the retina](src/toroidamp/assets/images/toroidamp_video_thumbnail.png)](...)
```

**Classification: RELEASE/DOCUMENTATION asset, not runtime, not dead.**
It is a GitHub README thumbnail image, unrelated to the running
application's own asset resolution. Left exactly where it is — it was
already correctly excluded from `pyproject.toml`'s package-data glob
(`assets/images/*.png` in the new manifest technically *does* still match
and include it in the wheel, since it lives in the same directory as the
genuinely-runtime `ToroidAMP.png` — harmless, a few extra KB, not worth a
narrower glob purely to exclude a small already-public image; noted here
rather than "fixed," since it isn't actually broken).

---

## 19. Packaging Readiness Check

```text
[x] Runtime Python deps accurately declared         — miniaudio removed, pyttsx3/pywin32/comtypes declared with platform markers
[x] Runtime assets explicitly packageable            — package-data fixed, verified via a real wheel build + fresh non-editable install
[x] Runtime resources independent of CWD              — consolidated resolver, foreign-CWD test passing
[x] User-writable paths install-safe                  — paths.py, %LOCALAPPDATA%\ToroidAMP\{logs,shaders}\, session.py delegated
[x] Persistent file logging works                      — RotatingFileHandler, idempotent, verified writing real entries
[x] Tracker backend strategy resolved                  — root cause understood precisely (libxmp vs. libmodplug API mismatch); acquisition options documented
[ ] Tracker playback actually validated OR explicitly BLOCKED  — explicitly BLOCKED (no binary available to validate against; not faked)
[x] Project license status known                        — corrected finding: file exists, contains no actual grant; explicit RELEASE BLOCKER reported
[x] Third-party notice requirements known               — checklist produced (§17), file itself deferred as instructed
[x] Version source understood                            — 3-tier fallback confirmed sound; exact PyInstaller flag requirement (--copy-metadata) pinned down
[x] No new release-blocking regression                   — full test suite re-run after every change, zero regressions beyond the same pre-existing, unrelated test_ux_004.py failures
```

**Two items remain explicitly open going into RC-069-003**: tracker
playback validation (blocked on binary acquisition, a decision for Metal)
and the LICENSE decision (also Metal's call, cannot be made here). Neither
blocks a ONEDIR *proof-of-concept* build from proceeding — both should
simply not be claimed as "done" in any 0.69 release notes until resolved.

---

## 20. Tests Added

`tests/test_rc_069_002.py` — **17/17 passed.** Covers all 15 items from
the mission's testing section (§20) plus 2 supplementary assertions
(foreign-CWD app-data resolution; no-network-handler privacy check).
Items 16-19 (real libmodplug validation) were **not** added — no binary is
available in this environment to validate against, and the mission is
explicit that fake byte arrays do not constitute release validation;
`test_12` instead directly exercises and pins the *documented, honest*
unavailable-path behavior.

---

## 21. Regression

Full `tests/` suite (33 files) re-run per-file after every change in this
cut. **Zero regressions.** Identical to every prior delivery this session:
the same 3 pre-existing, unrelated `test_ux_004.py` marquee failures, and
the same intermittent native-teardown artifact in `test_rc_polish_001.py`
(21/21 tests still report `passed` before the occasional crash-on-exit;
reproduced as flaky/non-deterministic across repeated runs, confirmed
unrelated to this cut's changes). `test_gpu_audio_*`, `test_gpu_official_001`,
`test_gpu_prod_*`, `test_theme_*`, `test_brand_001`, and every
session-persistence-adjacent test all pass unmodified.

---

## 22. Documentation

This document. `docs/release/RC_069_001_release_inventory.md` was **not**
rewritten — per instruction, history is not revised merely because a
blocker was subsequently fixed; §16's "LICENSE not found" claim is the one
factual correction, recorded here in §0/§15 rather than edited into the
original document.

---

## 23. Strict Non-Goals — Honored

No EXE built, no ONEFILE, no installer, no file associations, no
auto-update, no dependency auto-download, no `pip` calls from the
application, no system-dependency auto-install, no size optimization, no
Qt plugin pruning, no code signing, no registry writes, no startup
diagnostics UI, no new visualizers, no shader-discovery expansion, no
iChannel/multipass, and the version was not bumped.

---

## 24. Human Validation Protocol

**TEST A — Source checkout still works**
1. Launch normally (`python -m toroidamp` or the `toroidamp` console
   script).
2. Play a conventional (MP3/WAV/OGG/FLAC) file.
3. Switch NORMAL → MINI → RETINA MELT.
4. Open LAB, LOAD an external `.frag`.

**TEST B — Writable paths**
1. Locate `%LOCALAPPDATA%\ToroidAMP\` in Explorer.
2. Confirm `session.json`, `logs\`, and `shaders\` all exist and are
   populated/populatable.
3. Confirm the GPU LAB's LOAD/SAVE dialogs default into `shaders\`, not
   any location inside the repository checkout.

**TEST C — Persistent log**
1. Launch, play a track, open LAB, load a shader, exit normally.
2. Open `%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log`.
3. Confirm timestamped, readable entries exist for the session just
   performed.

**TEST D — Tracker**
- Backend is currently **unavailable** in this environment (§7): load a
  `.mod`/`.xm`/`.it`/`.s3m` file and confirm the app does **not** crash,
  the playlist cleanly auto-advances (or stops if it was the only track),
  and the log records a clear `libmodplug`-related error — not a bare
  Python traceback with no context.
- **If** Metal has separately sourced a working libmodplug DLL and placed
  it where `_discover_libmodplug()` looks: play one real file from each of
  MOD/XM/IT/S3M, exercise seek, and switch conventional ↔ tracker mid-session.

**TEST E — Resource independence**
1. Launch ToroidAMP from a shortcut/working directory that is NOT the repo
   checkout (e.g. double-click from Explorer with CWD elsewhere).
2. Confirm both themes render fully (fonts, images, QSS) and all official
   GPU visualizers load their shaders correctly.

---

## 25. Files Modified / Created

**Created**: `src/toroidamp/resources.py`, `src/toroidamp/paths.py`,
`tests/test_rc_069_002.py`,
`docs/release/RC_069_002_runtime_hygiene.md`.

**Modified**: `pyproject.toml` (package-data + dependencies),
`src/toroidamp/session.py` (delegates root-dir resolution to `paths.py`),
`src/toroidamp/branding.py` (uses `resources.py` for its primary tier),
`src/toroidamp/ui/theme.py` (all asset resolution delegates to
`resources.py`; the doubled-`src` bug is gone as a side effect),
`src/toroidamp/ui/fullscreen.py` (3 LAB dialog methods use
`get_user_shaders_dir()`), `src/toroidamp/visualizers/gpu_canvas.py`,
`src/toroidamp/visualizers/toroid_identity.py`,
`src/toroidamp/visualizers/cyber_bloom.py`,
`src/toroidamp/visualizers/audio_reactive_reference.py` (all four use
`resources.py`), `src/toroidamp/audio/player.py` (tracker-unavailable
failure-semantics fix), `src/toroidamp/__main__.py` (persistent file
logging + startup failure capture).

No shader source file, theme asset, or any file under `tests/`/`docs/`
(other than this new document) was touched. No LICENSE content was
invented or changed.

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

This cut resolves concrete, previously-identified packaging prerequisites
within the already-established release-readiness track (RC-069-001 →
RC-069-002 → RC-069-003); it does not change ToroidAMP's product phase,
feature scope, or any architectural decision gate. Two genuine open items
(tracker backend, license) are explicitly flagged as blockers in this
document rather than silently resolved — consistent with the project's
practice of keeping `docs/CURRENT_STATE.md` for phase/gate-level state, not
a running packaging-readiness log (that role belongs to
`docs/release/RC_*` documents specifically).
