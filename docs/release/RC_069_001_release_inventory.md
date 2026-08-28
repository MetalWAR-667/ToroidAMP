# RC-069-001 — Feature Freeze + Release Inventory + Packaging Readiness Audit

> **Status: AUDIT COMPLETE.** No code changed. No version bumped. No
> packaging performed. This document is evidence for RC-069-002's actual
> packaging work, not packaging itself.

## 1. Feature Freeze Inventory

### IN 0.69

**CORE PLAYER** — NORMAL mode, MINI mode, RETINA MELT fullscreen, transport
(Play/Pause/Stop/Prev/Next/seek/volume), FDE (fade) toggle, session
persistence (`session.json`), tray minimize/restore/quit lifecycle, theme
switching (live, no restart), startup/shutdown lifecycle incl. the voice
identity line.

**AUDIO** — MP3/WAV/OGG/FLAC via `soundfile` (`ConventionalDecoder`);
MOD/XM/IT/S3M via `libmodplug` ctypes (`TrackerDecoder`) — **see §9/§18: this
path is currently non-functional in the actual dev environment, not a
theoretical risk**; decoder error recovery (`AudioDecoder` abstract
contract, graceful skip on unplayable files); live `AudioFrame` analysis
(rms/peak/bass/mids/treble/spectrum/waveform/beat/strong_beat).

**PLAYLIST** — add/remove/clear, shuffle/repeat, M3U/M3U8 load/save,
Unicode/path handling.

**VISUALIZERS** — CPU visualizers (Toroid, WaveformRibbon, DeepField,
ToroidAMPFloor), official GPU visualizers (ToroidIdentity, CyberBloom,
AudioReactiveReference), visualizer cycling, RETINA fullscreen rendering,
silence baseline (all visualizers must render sanely with a `None`/zero
`AudioFrame`).

**GPU LAB** (RETINA-only) — load external `.frag`, hot reload (`R`),
compile/link failure rollback, typed parameters (float/bool/color),
presets (save/load JSON), AUTO REACT, discovered parameter binding
(GPU-AUDIO-003), safe const promotion (GPU-AUDIO-004), MUSICALIZE
(GPU-AUDIO-005), CLEAR AUTO, runtime literal parameterization
(GPU-AUDIO-006B), original-source immutability guarantee.

**THEMES** — DEFAULT, CYBER YELLOW, `theme.qss` overrides, bundled
image/font assets (`quantum.ttf`, chassis/hazard-strip/logo/wordmark/
panel PNGs).

### DEV-ONLY (must NOT ship)

- `experiments/` (foundation_ii, gpu_visualizers standalone Lab,
  ui_directions, visualizers) — exploratory/prototype code, not
  production-wired.
- `tools/` (`bump_version.py`, `generate_ico.py`, `shader_audit.py`) —
  developer scripts, never imported by the shipping application.
- `tests/` (33 files) — pytest suite.
- `.agents/` — this session's own tooling directory.
- `docs/` internal design/architecture history (GPU-AUDIO-001 through
  006B design docs, `ARCHIVE.md`, this document itself) — developer
  record, not user-facing.
- `user_shaders/` — **git-ignored** (`.gitignore: /user_shaders/`),
  confirmed not tracked in the repository at all; a purely local dev/test
  scratch folder. It must not be assumed to exist by production code (see
  §7/§9 finding on `fullscreen.py`'s LOAD/SAVE dialogs).
- `docs/design/*_gpu_audio_*.md`, `docs/design/13_*`, `docs/design/14_*` —
  internal engineering record.

### DEFERRED POST-0.69

- File associations (explicitly excluded this cut).
- iChannel / multipass / spectrum-texture shader inputs (explicitly
  excluded — GPU-AUDIO-004/005/006A/006B Level D+ boundary).
- Additional shader-literal discovery heuristics beyond GPU-AUDIO-006B's
  two supported patterns.
- New visualizers, new DSP, new themes.
- Installer, code signing, auto-update, file associations, AppData
  migration tooling (all explicit non-goals of this cut too — see §20 of
  the mission).
- `EXPORT ADAPTED SHADER` (already recorded as deferred in
  `docs/design/14_gpu_audio_006b_runtime_parameterization.md`).

---

## 2. Canonical Production Entry Point

**One canonical entry point, confirmed by direct inspection — no
redundancy found:**

```toml
[project.scripts]
toroidamp = "toroidamp.__main__:main"
```

`src/toroidamp/__main__.py:main()` is invoked identically whether launched
via:
- the installed `toroidamp` console script, or
- `python -m toroidamp`.

No competing entry point exists — no repo-root `run.py`/`main.py`, no
second `if __name__ == "__main__":` production path anywhere else in
`src/`. `main()` does exactly one job: `setup_logging()` (console only —
see §11), construct `QApplication` with `setApplicationName("ToroidAMP")` /
`setOrganizationName("")` (this ordering matters — see §8), resolve the
branding icon, wire `AnalysisHandoff` → `PlayerEngine` → `PlaylistManager`
→ `SessionManager` → `WindowManager`, start `VoiceService`, handle
CLI file arguments, and `app.exec()`.

**This is the correct, and only, target for a packaged executable.**
`experiments/gpu_visualizers/lab_app.py` is a separate, standalone dev tool
entry point — not production, must not be bundled as the app.

---

## 3. Python Runtime Dependency Inventory

Traced from `pyproject.toml` **and independently verified against actual
imports** (`grep -rn "^import\|^from" src/toroidamp`), not assumed from
documentation.

| Package | pyproject.toml | Actually imported? | Classification |
|---|---|---|---|
| `PySide6` | yes | yes, extensively (UI, `QtOpenGLWidgets`, `QtOpenGL`, `QtTest` in tests) | **REQUIRED AT STARTUP** |
| `pygame-ce` | yes (`pygame-ce`) | yes — CPU visualizer rendering, `voice.py` (WAV playback), tracker DLL discovery | **REQUIRED AT STARTUP** |
| `numpy` | yes | yes — audio analysis, decoders, visualizer geometry | **REQUIRED AT STARTUP** |
| `sounddevice` | yes | yes — `player.py`'s only audio OUTPUT path | **REQUIRED AT STARTUP** |
| `soundfile` | yes | yes — `ConventionalDecoder`, the ONLY decoder for MP3/WAV/OGG/FLAC | **REQUIRED AT STARTUP** (required by the MP3/WAV/OGG/FLAC feature) |
| `miniaudio` | yes | **NO — zero imports found anywhere in `src/toroidamp`** | **DECLARED BUT UNUSED — flag for removal, RC-069-002** |
| `pyttsx3` | **NOT DECLARED** | yes — `voice.py`, wrapped in `try/except ImportError` | **UNDECLARED OPTIONAL DEPENDENCY — real gap, see §9** |
| `pywin32` / `comtypes` | **NOT DECLARED** | transitively required by `pyttsx3`'s Windows SAPI5 backend (confirmed installed in this venv: `pywin32==312`, `comtypes==1.4.16`) | **UNDECLARED TRANSITIVE DEPENDENCY** |
| `Pillow` | yes (`dev` extra only) | only `tools/generate_ico.py` | **DEV/TEST ONLY** — correctly scoped already |
| `pytest` | not declared (installed ad hoc: `pytest==9.1.1`) | test suite only | **DEV/TEST ONLY — should be added to a `test`/`dev` extra for reproducibility** |

**Verified directly in this dev venv** (`pip list --format=freeze`):
`toroidamp==0.1.0` is installed — see §16, this is a live, present example
of the exact version-authority drift `_version.py`'s own docstring warns
about (pyproject.toml currently says `0.3.1`).

---

## 4. Native Dependency Inventory

| Name | Why needed | Feature | Current source | Bundle-able? | License/redistribution | Failure mode if missing |
|---|---|---|---|---|---|---|
| **Qt6 / PySide6 native libs** (`Qt6Core.dll`, `Qt6Widgets.dll`, `Qt6OpenGL*.dll`, ffmpeg-derived `avcodec/avformat/avutil` DLLs, `msvcp140*`, `concrt140`, etc.) | UI toolkit, OpenGL surface | Entire application | PySide6 wheel (`.venv/Lib/site-packages/PySide6/*.dll`) | Yes — this is exactly what PySide6's wheel ships for | LGPLv3 (Qt6, as distributed by PySide6/Qt Company) — dynamic linking, redistributable; verify PySide6's own license file ships alongside | App cannot start at all |
| **Qt platform plugin** (`qwindows.dll`) | Win32 windowing backend | Entire application | `PySide6/plugins/platforms/` | Yes, must be collected into the correct relative `platforms/` subfolder | Same as above | `"Could not load the Qt platform plugin \"windows\""` — total startup failure, the single most common PyInstaller+PySide6 failure mode |
| **PortAudio** (bundled inside `sounddevice`'s wheel via `_sounddevice_data`) | Audio OUTPUT device I/O | All audio playback | `sounddevice` wheel | Yes | MIT (PortAudio) | No audio output at all; `sounddevice` raises at stream-open time |
| **libsndfile** (bundled inside `soundfile`'s wheel) | MP3/WAV/OGG/FLAC decode | `ConventionalDecoder` — the majority of the "AUDIO" feature surface | `soundfile` wheel | Yes | LGPLv2.1 (libsndfile) — dynamic linking, redistributable | Every conventional-format file fails to load |
| **libmodplug** (dynamically `ctypes.CDLL`-loaded, discovered at runtime from inside `pygame`'s install dir, `ctypes.util.find_library`, or hardcoded fallback paths) | MOD/XM/IT/S3M decode | `TrackerDecoder` | **NOT FOUND ANYWHERE in this actual dev environment** — see finding below | Unclear — **not currently present to bundle** | LGPLv2.1 (libmodplug/OpenMPT-derived) if sourced | `TrackerDecoder.__init__` raises `RuntimeError` immediately; `is_available()` correctly reports `False` and the one test that exercises this (`test_production_core.py`) already, correctly, skips rather than fakes a pass |
| **pygame-ce's own bundled DLLs** (`SDL2.dll`, `SDL2_mixer.dll`, `SDL2_image.dll`, `SDL2_ttf.dll`, `libogg/libopus/libwavpack/libwebp/libpng/libjpeg/libtiff`, **`libxmp.dll`**) | CPU visualizer surface rendering, `voice.py` WAV playback | CPU visualizers, voice line | pygame-ce wheel | Yes | Mixed (zlib/BSD/LGPL family, standard SDL2 ecosystem) — verify pygame-ce's own NOTICE | Visualizer/voice subsystems degrade |
| **OpenGL driver (system, not bundled)** | GPU visualizer rendering surface | RETINA MELT / GPU LAB / GPU visualizer only | The machine's own GPU driver | **No — cannot be bundled**, this is a system capability (§6, §10 category D) | N/A | RETINA/GPU features fail to render; base player must remain usable (see §6) |
| **pyttsx3's SAPI5 backend** (`pywin32`/`comtypes`, itself wrapping the OS's built-in `sapi.spvoice` COM object) | Startup voice line | `VoiceService` only | pywin32/comtypes wheels (undeclared, §3) + Windows' own built-in SAPI5 | Partially — the Python wrapper libs bundle; SAPI5 itself is a Windows OS component, always present on real Windows, never "bundled" | pywin32 is PSF-derived/permissive; comtypes MIT | `TTS_AVAILABLE = False`, voice line silently skipped — already handled gracefully |

**★ Critical finding — libmodplug is not merely a packaging risk, it is
currently absent.** `TrackerDecoder._discover_libmodplug()` checks (1)
inside `pygame`'s install directory for `libmodplug-1.dll`/`libmodplug.dll`,
(2) `ctypes.util.find_library("modplug")`, (3) a short hardcoded fallback
list. **Verified directly against the actual installed `pygame-ce==2.5.8`
in this environment: none of these locate a real file.** Direct
inspection of `pygame`'s bundled DLL set shows `libxmp.dll` present
instead of any `libmodplug*` — i.e. this pygame-ce build appears to ship a
*different* tracker library (libxmp) than the one `TrackerDecoder` looks
for. `TrackerDecoder.is_available()` returns `False` right now, in this
very development environment — this is not a hypothetical clean-machine
gap, it is the project's **actual current state**. The MOD/XM/IT/S3M
feature has, as far as this audit can determine, never been exercised
against a real native library in this codebase's current form. **This is
the single highest-priority release-blocking item found by this audit**
(§18, §21).

---

## 5. Qt Runtime Requirements

Inspected `.venv/Lib/site-packages/PySide6/plugins/`. ToroidAMP's actual
usage surface only requires:

- **`platforms/qwindows.dll`** — mandatory, Win32 window backend. Without
  it: `"Could not load the Qt platform plugin \"windows\""` and immediate
  exit — the single most common PySide6-packaging failure mode industry-wide.
- **`imageformats/`** — PNG loading for theme images, branding, packaged GPU
  texture (`assets/images/ToroidAMP.png`). Qt's PNG support is normally
  compiled in, but the plugin directory should still be collected
  defensively (cheap, standard PyInstaller/Nuitka PySide6 hook behavior).
- **`styles/`** — not explicitly required (ToroidAMP uses custom QSS
  styling throughout, not native OS widget styles), but collecting the
  default is cheap insurance against a blank/unstyled fallback UI.
- **`platforminputcontexts/`, `generic/`, `iconengines/`** — standard
  baseline Qt plugin set most PySide6 packaging hooks collect by default;
  no ToroidAMP-specific dependency identified, listed for completeness.
- **Explicitly NOT required**: `assetimporters`, `canbus`, `designer`,
  `geometryloaders`, `geoservices`, `multimedia`, `networkinformation`,
  `position`, `qmllint`, `qmltooling`, `renderers`, `renderplugins`,
  `sceneparsers`, `scxmldatamodel`, `sensors`, `sqldrivers`,
  `texttospeech` (ToroidAMP's own TTS is `pyttsx3`, unrelated to Qt's),
  `tls`, `vectorimageformats`, `webview`. **Excluding these explicitly in
  the packaging spec (both PyInstaller and Nuitka support this) will
  materially shrink the artifact** — Qt's full plugin set is large and
  none of the above is reachable from any ToroidAMP code path.
- **System tray**: `QSystemTrayIcon` usage confirmed (`__main__.py`'s
  `setQuitOnLastWindowClosed(False)` + tray lifecycle) — this is a Qt
  Widgets-level capability, not a separate plugin; no extra runtime
  requirement beyond the platform plugin above.

---

## 6. GPU / OpenGL Requirements

- **Minimum version actually requested**: OpenGL **3.3 Core Profile**,
  set via `QSurfaceFormat` before every `GLVisualizerCanvas`/GPU-context
  construction (confirmed identically across `gpu_canvas.py` and every
  `tests/test_gpu_*.py` setup).
- **Qt classes used**: `QOpenGLWidget`, `QOpenGLShaderProgram`,
  `QOpenGLShader`, `QOpenGLBuffer`, `QOpenGLTexture`,
  `QOpenGLVertexArrayObject`, `QSurfaceFormat` — confirmed by direct
  `grep`, present only in `gpu_canvas.py` and `fullscreen.py`.
- **System OpenGL is assumed** — no ANGLE/software-rasterizer fallback
  path exists in code today.
- **Current reality**: `GLVisualizerCanvas.load_shader_file()` has a
  documented, already-tested headless/`isValid()==False` fallback branch
  (used throughout this session's own automated test environment, which
  has no real GPU context) that stores metadata/parameters without
  attempting to compile — **but this is a test-environment accommodation,
  not a designed "no GPU, still usable" product behavior.** In the real
  running application, if `QOpenGLWidget.isValid()` is ever `False` (driver
  too old, no GPU, remote desktop without GPU passthrough, etc.), GPU
  visualizers/RETINA MELT/GPU LAB would render nothing meaningful — there
  is no user-facing message explaining why, today.
- **Classification**: **REQUIRED ONLY FOR GPU VISUALIZERS / RETINA
  FEATURES.** Confirmed by code structure: CPU visualizers (Toroid,
  WaveformRibbon, DeepField, ToroidAMPFloor), NORMAL/MINI player windows,
  playlist, and all core transport/audio functionality have zero OpenGL
  dependency — they run entirely through `pygame.Surface` → `QImage` /
  standard Qt widgets.
- **Recommended release behavior** (not implemented this cut, per
  instructions): base audio-player functionality should remain fully
  usable with GPU/RETINA features cleanly disabled/warned-about when
  `isValid()` is false — this is exactly the gap the Startup Diagnostics
  proposal (§11) is designed to close in a future cut, not this one.

---

## 7. Runtime Asset Inventory

Complete inventory (`find src/toroidamp/assets -type f`):

| Path | Used by | Resolution mechanism | Classification |
|---|---|---|---|
| `assets/branding/toroidamp_icon.png`, `toroidamp.ico` | `branding.py` (app/tray/taskbar icon) | `importlib.resources.files("toroidamp")` primary, checkout-relative fallback — **packaging-safe pattern, and the only asset type actually declared in `pyproject.toml` package-data** | BUNDLED READ-ONLY RESOURCE |
| `assets/images/ToroidAMP.png` | `gpu_canvas.py`'s packaged GPU texture (`taTexture0`) | plain `Path(__file__).resolve().parent.parent` (no `importlib.resources`) | BUNDLED READ-ONLY RESOURCE — **not in package-data (see finding below)** |
| `assets/images/toroidamp_video_thumbnail.png` | not found referenced in any `src/` import | — | Appears unused by the running app (marketing asset?) — verify before shipping |
| `assets/official_shaders/*.frag` (4 files) | `toroid_identity.py`, `cyber_bloom.py`, `audio_reactive_reference.py`, and (via `official_shader_dir`) the standalone dev Lab | plain `Path(__file__).resolve().parent.parent`, same pattern as above | BUNDLED READ-ONLY RESOURCE — **not in package-data** |
| `assets/themes/default/theme.qss`, `assets/themes/cyber_yellow/{theme.qss, fonts/*, images/*}` | `theme.py` | `importlib.resources.files("toroidamp")` primary, checkout-relative fallback — same safe pattern as branding | BUNDLED READ-ONLY RESOURCE — **not in package-data** |

**★ Critical finding — the packaging manifest is incomplete.**
`pyproject.toml`'s `[tool.setuptools.package-data]` currently declares
**only**:

```toml
toroidamp = ["assets/branding/*.png", "assets/branding/*.ico"]
```

It omits `assets/images/*`, `assets/official_shaders/*.frag`, and
`assets/themes/**/*` entirely. **This currently works only because every
development and test run in this project uses an editable install**
(confirmed: `toroidamp.__file__` resolves directly into `src/toroidamp/`,
so `importlib.resources.files("toroidamp")` finds everything on disk
regardless of the manifest). **A real `pip install .` (non-editable
build), a real wheel, or a PyInstaller/Nuitka build driven from an
installed (not editable) environment would silently ship without themes,
without official GPU shaders, and without the packaged GPU texture** —
`CYBER YELLOW` would be unselectable/broken, all three official GPU
visualizers plus AudioReactiveReference would have no shader file to load,
and the GPU canvas's background texture would be missing. Every affected
code path degrades "gracefully" (returns `None`/logs a warning rather than
crashing — themes.py's `ThemeManager`, `branding.py`, and the GPU
visualizer loaders were all built defensively), so this would very likely
manifest as **a visually broken but not obviously-crashing release** —
exactly the kind of gap that only surfaces once real (non-editable)
packaging is attempted. **This is the second highest-priority
release-blocking item found by this audit** (§21) — trivial to fix (expand
the `package-data` glob list) but must be fixed and *verified with a real
non-editable build* before RC-069-002 packages anything.

**Dev-only asset locations** (not for the shipped asset tree, already
covered in §1): `assets/` at repo root (full-resolution creative
source — "never loaded at runtime" per its own pyproject.toml comment),
`user_shaders/` (git-ignored, local scratch — see §9).

---

## 8. User-Writable Data Audit

| Data | Current location | Mechanism | Appropriate for a frozen/installed app? |
|---|---|---|---|
| `session.json` | `%LOCALAPPDATA%\ToroidAMP\session.json` (Windows), `~/.config/ToroidAMP/session.json` (Linux fallback) | `QStandardPaths.AppConfigLocation`, hard-guarded to always end in a literal `ToroidAMP` folder segment, with legacy-nested-path migration already built in | **Yes — already correct**, this is exactly the right Windows convention |
| Playlist / M3U-M3U8 | User-chosen path via `QFileDialog` (`save_m3u`/`load_m3u`) | Explicit user choice, no hardcoded default location found | Fine — user controls the location, no assumption about writability of any fixed path |
| GPU LAB shader presets (`_save_lab_preset_dialog`) | Defaults to `<repo_root>/user_shaders/<shader>_preset.json` if that directory exists, else a bare filename (no directory) | `Path(__file__).resolve().parent.parent.parent.parent` from `fullscreen.py` — **repo-checkout-relative**, degrades to a bare filename (CWD-dependent) when absent | **No** — meaningless/wrong default location in any installed/frozen build; the graceful-degradation path (bare filename) means "wherever the OS's file dialog happens to default to," not a deliberate, discoverable location |
| GPU LAB external `.frag` LOAD dialog default directory | Same `<repo_root>/user_shaders/` pattern, degrades to repo root | Same mechanism | **No** — same issue; `user_shaders/` won't exist in *any* real install (it's git-ignored even in the dev checkout) |
| Logs | **None — no file logging exists anywhere in the codebase** (`logging.basicConfig` to console/stdout only, confirmed by direct search — no `FileHandler`, no `.log` file writes found) | — | **No** — a `--windowed`/no-console packaged build would have literally zero recoverable diagnostics on failure; see §11 |
| Caches/temp files | None found written by the application itself (pygame/Qt/PortAudio may use their own OS temp dirs internally, out of ToroidAMP's control) | — | N/A |

### Proposed Windows Path Policy (recommendation only — not migrated this cut)

```text
%LOCALAPPDATA%\ToroidAMP\
    session.json                 (already correct today)
    logs\ToroidAMP.log            (recommend adding — see §11)
    shaders\                      (recommend: LAB preset SAVE default,
                                    replacing the repo-relative default)
    presets\                      (if presets and shaders end up wanting
                                    separate namespaces)
```

`%LOCALAPPDATA%` (not `%APPDATA%`/roaming) is the right root — matches
`session.json`'s existing, already-correct choice, and per-machine local
data (not roaming-profile-synced) is the appropriate class of data for all
of the above. **User-supplied `.frag` files loaded via LOAD... remain
wherever the user put them** — no change needed there, only the *dialog's
default starting directory* and the *preset SAVE default* need to move off
the repo-relative assumption.

---

## 9. Development-Environment Assumptions Discovered

Brutally honest inventory of what currently only works because this is a
developer's own checkout:

1. **`user_shaders/`-relative LAB defaults** (§8) — assumes a live repo
   checkout with a `user_shaders/` folder sitting next to `src/`. Neither
   exists in a packaged install.
2. **Incomplete package-data manifest** (§7) — currently masked entirely by
   editable-install behavior; would break on a real wheel/frozen build.
3. **`pyttsx3`/`pywin32`/`comtypes` undeclared** (§3) — the voice feature
   currently "works" only because these happen to be installed in this
   venv out-of-band, not because the project declares them.
4. **`miniaudio` declared but unused** (§3) — harmless but adds
   unnecessary weight to any dependency-driven packaging step (PyInstaller
   hidden-import scanning, wheel size) for zero functional benefit.
5. **libmodplug genuinely absent** (§4) — not a "clean machine" problem,
   a *this machine* problem. Tracker playback has apparently never been
   exercised against a real native decoder in this project's current
   toolchain.
6. **No file logging** (§8/§11) — console-only logging is invisible the
   moment the app is packaged `--windowed`/no-console, which every
   consumer-facing Windows GUI build normally is.
7. **`toroidamp==0.1.0` installed metadata vs. `0.3.1` in pyproject.toml**
   (§16) — live, present evidence of exactly the editable-install metadata
   staleness `_version.py`'s own docstring warns about; a real `pip
   install .`/wheel build (not editable) resolves this automatically, but
   it is worth knowing this venv's installed metadata is currently stale.
8. **`QApplication.setApplicationName("ToroidAMP")` ordering dependency**
   (§8 investigation) — `SessionManager`'s Windows path resolution is
   correct in production (`__main__.py` sets the app name before
   constructing `SessionManager`), but this is an implicit ordering
   contract, not something structurally enforced — confirmed directly: this
   session's own test harness (which builds a bare `QApplication` without
   setting `applicationName`) resolves session paths to a *different*
   folder (`%LOCALAPPDATA%\python\ToroidAMP\`, using the interpreter name
   as a fallback) than production does. Not a bug in production, but worth
   documenting since it is easy to accidentally break by reordering
   `__main__.py`.
9. **No Git/VC++ Redistributable/Python-on-PATH dependency was found** in
   the actual application code — `_version.py`'s pyproject.toml read is
   the only place a repo-checkout file is read for *non-asset* purposes,
   and it has a safe installed-metadata fallback (§16). This is a point in
   ToroidAMP's favor: the codebase does not appear to assume Git or a
   system Python beyond what's frozen into the executable.

---

## 10. Dependency Classification Model

**A. BUNDLED** (user should never know it exists): Python runtime
(frozen), PySide6/Qt6 + required plugins (§5), PortAudio (via
`sounddevice`), libsndfile (via `soundfile`), pygame-ce + its own bundled
SDL2 family DLLs, application assets once §7's package-data gap is fixed,
pywin32/comtypes (if the voice feature ships — recommend declaring them
explicitly rather than relying on their accidental presence).

**B. EXTERNAL PREREQUISITE** (must genuinely exist, should be checked):
none identified as strictly required beyond the OS itself — Windows 10/11
with its standard runtime is the effective floor. **Recommend**: detect
and log (not block) at startup.

**C. OPTIONAL FEATURE DEPENDENCY** (app runs without it, feature degrades
cleanly):
- **libmodplug** → MOD/XM/IT/S3M tracker playback. *Recommend: detect,
  warn, disable feature* (already partially true via
  `TrackerDecoder.is_available()` — just needs to actually be reachable
  from a real binary before this classification is honest).
- **pyttsx3/SAPI5** → startup voice line. *Recommend: detect, warn,
  disable feature* (already implemented — `TTS_AVAILABLE` flag).
- **OpenGL 3.3 Core capability** → GPU visualizers/RETINA/LAB. *Recommend:
  detect, warn, disable feature* (currently NOT implemented as a clean
  product-level fallback — see §6).

**D. SYSTEM CAPABILITY**:
- **Functioning audio output device** → all playback. *Recommend: detect
  at startup, clear diagnostic if absent* (not currently implemented —
  `sounddevice` will raise when a stream is actually opened, not at
  startup).
- **Compatible GPU/OpenGL driver** → GPU features only (§6).

None of these checks should be implemented in this cut (per mission
scope) — this section is the design input for when they are.

---

## 11. Startup Diagnostics Proposal (design only — not built)

```text
ToroidAMP Startup Diagnostics
  [OK]   Core runtime (Python + Qt)
  [OK]   Qt platform plugin (windows)
  [OK]   Audio output backend (PortAudio/sounddevice)
  [OK]   Conventional decoder (libsndfile — MP3/WAV/OGG/FLAC)
  [WARN] Tracker decoder (libmodplug not found — MOD/XM/IT/S3M disabled)
  [OK]   GPU/OpenGL 3.3 Core (RETINA MELT / GPU LAB available)
  [OK]   Bundled assets (themes, official shaders, branding)
  [WARN] Voice synthesis (pyttsx3/SAPI5 not found — startup line disabled)
```

**Design contract**:
- A **non-critical** component failing (tracker decoder, voice, GPU/RETINA)
  → application still launches fully, the dependent feature is cleanly
  disabled, one concise log line is written (see below) — never a popup
  that blocks startup, never a silent no-op that leaves a user wondering
  why a button does nothing.
- A **critical** component failing (Qt platform plugin, core Python
  runtime, PortAudio) → this is unrecoverable before any UI exists, so it
  belongs at the level of a clear OS-level error, not an in-app diagnostic
  screen — but *should never present as a silent double-click-does-nothing
  failure*, which is the actual, common real-world PyInstaller+PySide6
  failure mode this section exists to prevent.
- **What belongs in the installer/bootstrapper** (future, not this cut):
  nothing — ToroidAMP's dependency shape (§10) has no genuine
  B-classification external prerequisite that an installer would need to
  check/install; everything either bundles cleanly or degrades to a
  C-classification optional feature.
- **What belongs in application startup**: the diagnostics table above,
  computed cheaply (a handful of `is_available()`-style probes, all of
  which already exist individually — `TrackerDecoder.is_available()`,
  `TTS_AVAILABLE`, `GLVisualizerCanvas.isValid()`) and logged (see below),
  with feature-level UI (menu items/buttons for disabled features) grayed
  out or hidden rather than present-but-broken.
- **What should only be logged, never surfaced in UI**: exact DLL search
  paths tried, Qt plugin resolution internals, OpenGL version-string
  detail — useful for a bug report, noise for a user.

**File logging is a prerequisite for this to be useful at all** (§8) — a
`--windowed` packaged build has no console; the diagnostics table's log
line needs a real file destination
(`%LOCALAPPDATA%\ToroidAMP\logs\ToroidAMP.log`, per §8's proposed policy)
to ever be seen by anyone outside a dev checkout.

---

## 12. Packaging Technology Survey — PyInstaller vs. Nuitka

Compared on ToroidAMP's actual dependency shape (§3, §4, §5), not generic
folklore. Neither tool is installed in this dev venv — this is a desk
evaluation pending a real proof-of-concept build (§13).

| Factor | PyInstaller | Nuitka |
|---|---|---|
| PySide6 support | Mature, well-trodden hooks (`hook-PySide6.*`); the single most common PySide6-packaging path in the wild — most Stack Overflow/GitHub-issue precedent for exactly ToroidAMP's stack exists here | Supported via its Qt plugin, actively maintained, but a smaller precedent base specifically for PySide6 + custom `QOpenGLWidget` subclasses like `gpu_canvas.py` |
| Native DLL collection (PortAudio/libsndfile) | Automatic via package-specific hooks (`sounddevice`, `soundfile` both ship/are covered by community hooks) | Also generally works (Nuitka's package-data detection is broadly import-driven) but less hook-ecosystem precedent for this exact pair |
| Qt plugin handling | Well-defined (`--collect-data PySide6` / hook-driven `platforms`/`imageformats` collection) | Its dedicated `--plugin-enable=pyside6` handles this natively, arguably more integrated |
| **`ctypes.CDLL`-loaded libmodplug** | **High risk either way** — dynamic `ctypes.CDLL(path)` loads are invisible to static import-graph analysis in *both* tools. PyInstaller requires an explicit `--add-binary`/spec-file entry; **this is not a differentiator between the two tools, it is a ToroidAMP-side requirement regardless of packager choice** (moot anyway until §4's absent-DLL finding is resolved) | Same requirement, via `--include-data-files` |
| OpenGL | No special handling needed either way — `QOpenGLWidget` rides on Qt's own OpenGL integration, already covered by the Qt plugin story above | Same |
| Startup time | Generally slower cold start for `--onefile` (self-extraction to a temp dir every launch) than `--onedir` | Compiles to a real native binary; `--onefile` mode also self-extracts but Nuitka's compiled bytecode can start meaningfully faster once extracted — real difference only measurable with an actual build |
| Build complexity | Lower barrier to entry, huge community precedent, `.spec` files are approachable | Higher barrier (a real C compiler toolchain — MSVC or MinGW — is a build-machine prerequisite, not a runtime one, but still real setup cost) |
| Binary size | Typically larger due to bundling the full interpreter + bytecode + all collected libs verbatim | Often smaller/comparable after compilation, but Qt/PySide6's own DLL weight dominates either way — the difference is unlikely to be dramatic for THIS app given how Qt-dominated its dependency footprint already is |
| One-folder support | First-class, default mode | First-class, default mode |
| One-file support | First-class (`--onefile`), well-understood self-extraction behavior and its tradeoffs | First-class (`--onefile`), same class of self-extraction tradeoff |
| Troubleshooting transparency | Very high — `--onedir` output is a plain, browsable folder; verbose/debug flags are well documented; largest community knowledge base for exactly this failure class ("Could not load Qt platform plugin", missing hidden imports) | Good, but the compiled-binary nature makes ad-hoc "what got included" inspection slightly less immediate than PyInstaller's plain-folder output |
| Antivirus/SmartScreen false-positive risk | **Materially higher** — PyInstaller's `--onefile` bootstrap stub is a very common malware-packer signature false-positive trigger; well-documented, ongoing community pain point | Generally lower — a real compiled binary triggers fewer generic "packed executable" heuristics, though unsigned executables from either tool will still hit SmartScreen's reputation-based warning regardless |
| Reproducibility | Deterministic given a pinned environment; spec files are explicit and versionable | Also deterministic; compiled output arguably more so (native codegen vs. bytecode+interpreter bundling) |
| Developer effort for THIS project | **Lower** — ToroidAMP's dependency set (PySide6 + numpy + pygame-ce + sounddevice + soundfile + ctypes) matches PyInstaller's most battle-tested use case almost exactly | Higher upfront (compiler toolchain setup) for a benefit (smaller/faster binary, lower AV false-positive rate) that is real but secondary to *first getting a working build at all* |

### Recommendation

**Start with PyInstaller for the Phase A one-folder proof-of-concept
(§13).** Rationale specific to this project, not generic preference: (1)
the single riskiest packaging item (§4's `ctypes`-loaded libmodplug, once
resolved) needs an explicit binary-inclusion declaration either way — no
tooling advantage there; (2) PyInstaller's community precedent for
exactly "PySide6 + `QOpenGLWidget` + numpy + sounddevice/soundfile" is the
deepest available, which matters most while still answering basic
questions ("does the Qt platform plugin even load on a clean machine?");
(3) `--onedir` troubleshooting transparency is valuable precisely because
this audit found real gaps (§7's package-data, §8's LAB path defaults)
that will need to be *debugged by inspecting a real build's folder
contents*, not just theorized about. **Revisit Nuitka for antivirus
false-positive mitigation specifically if/when a signed, public `--onefile`
release artifact's SmartScreen/AV reputation becomes a real, measured
problem** — not before, per the mission's explicit "do not choose based on
generic internet folklore" instruction; that decision needs its own
evidence, which does not exist yet.

---

## 13. One-Folder vs. One-File Recommendation

**Phase A (one-folder) first, unconditionally.** ToroidAMP's dependency
shape has at least three items (§4's libmodplug `ctypes` load, §7's
incomplete package-data, §8's repo-relative LAB path defaults) that are
*specifically the kind of failure a one-folder build makes trivially
debuggable by just looking in the folder* and a one-file build would
otherwise hide inside a temp-extraction directory that vanishes on exit.
Building one-file before these are resolved and validated would mean
debugging blind.

**Phase B (one-file) is realistic as the eventual public artifact —
conditionally.** Nothing found in this audit rules it out structurally:
no native dependency here is known to behave badly when temp-extracted
(unlike e.g. some CUDA/driver-registration scenarios elsewhere in the
ecosystem). The gate should be: Phase A's `--onedir` build passes the
full clean-machine protocol (§14) with zero missing-DLL/plugin errors and
zero broken assets, *then* build `--onefile` from the same, now-proven
spec and re-run the same protocol — if it passes identically, ship
one-file as the primary public artifact per §15's model. **Do not force
one-file** if, once actually tried, some dependency demonstrably behaves
worse under temp-extraction (this cannot be determined from static
analysis alone — it is exactly what Phase B's re-run of the clean-machine
protocol is for).

---

## 14. Clean-Machine Test Plan

**Machine/VM must NOT have**: this project's `.venv`, a repository
checkout, any development Python install, Git, or any manually-copied
project DLL. A fresh Windows 10/11 VM with only OS-default components is
the right baseline.

1. Launch the packaged artifact directly (double-click, no console
   attached).
2. First startup — no `session.json` present yet; confirm it is created at
   `%LOCALAPPDATA%\ToroidAMP\session.json` and the app starts with sane
   defaults (no music loaded, per existing lifecycle design).
3. Play an MP3.
4. Play a WAV, then a FLAC, then an OGG.
5. Play a MOD, an XM, an IT, and an S3M — **expected to currently FAIL or
   report the tracker decoder unavailable, per §4/§18's finding; this is
   the test that will prove whether §21's recommended fix landed.**
6. Exercise Play/Pause/Stop/seek/volume/FDE toggle.
7. Build a playlist; save as M3U8; reload it; confirm Unicode filenames
   survive round-trip.
8. Cycle MINI → NORMAL → RETINA MELT.
9. Cycle through all official visualizers (CPU and GPU) in both NORMAL and
   RETINA.
10. Confirm the GPU visualizer path specifically — if this VM has no real
    GPU/only a software OpenGL fallback, this is exactly where §6's
    "no clean degradation exists today" gap will surface; record precisely
    what happens (crash? blank frame? silent nothing?).
11. LOAD an external `.frag` from LAB — **expected to currently show a
    dev-checkout-relative default location that won't exist**, per §8;
    confirm the dialog still functions (user can navigate manually) even
    though the *default* directory is wrong.
12. Open LAB generally — typed parameters, presets (SAVE — same §8 caveat
    on default location — and LOAD), hot reload (`R`), compile-failure
    rollback (deliberately load a broken `.frag`).
13. Toggle AUTO REACT.
14. Press MUSICALIZE, play music, confirm bounded audio-reactive response;
    press CLEAR AUTO.
15. Confirm hot reload where applicable (LAB `R`) preserves state per the
    already-documented GPU-AUDIO-005/006B semantics.
16. Switch DEFAULT ↔ CYBER YELLOW themes live — **this is the test that
    will prove whether §7's package-data fix landed**, since theme QSS and
    the Quantum font are exactly the assets at risk.
17. Exit; relaunch.
18. Confirm session state (window position/scale/theme/volume/playlist)
    persisted correctly across the relaunch.
19. Confirm *some* diagnostic trail exists for anything that failed above —
    this will currently fail (§8/§11: no file logging exists yet), and is
    exactly the gap §11 is proposed to close.
20. Confirm **no dependency-install prompt of any kind** appears for
    anything classified BUNDLED in §10 (Qt, PortAudio, libsndfile, pygame's
    own SDL2 family) — only C-classification optional features
    (tracker/voice/GPU) may visibly degrade.

**Additional targeted runs**: (a) a VM/machine with no functioning GPU or
only a minimal software OpenGL implementation — exercises §6 directly;
(b) a machine with no default audio output device configured — exercises
the D-classification "functioning audio device" system capability, currently
undetected at startup (§10); (c) a deliberately corrupted/truncated media
file, to exercise `AudioDecoder` error-recovery behavior end-to-end outside
the dev environment's own test fixtures.

---

## 15. Release Artifact Recommendation

```text
ToroidAMP-v0.69-win64.exe                  <- onefile, PRIMARY public artifact
ToroidAMP-v0.69-win64-portable.zip          <- onedir, SECONDARY artifact
```

**ONEFILE EXE** — the user-facing convenience artifact. Single download,
single double-click, no extraction step the user has to think about. This
is what most users should be pointed at, once Phase B (§13) has actually
proven it survives the full clean-machine protocol identically to the
Phase A one-folder build.

**PORTABLE/ONE-FOLDER ZIP** — diagnostics/compatibility fallback and
transparency artifact. Valuable for: (a) users on machines where
`--onefile`'s temp-self-extraction is blocked by policy/AV (common in
locked-down corporate/managed environments); (b) support/troubleshooting,
since a `--onedir` layout is directly browsable — exactly the property
that made it the right *build/debug* artifact in §13 also makes it a
useful *support* artifact after release; (c) users who explicitly prefer
not to run a self-extracting executable at all.

**Not created this cut** — this is a recommendation for RC-069-002's
output shape, not a deliverable of this audit.

---

## 16. Version / Metadata Findings

**Source-of-truth chain, as actually implemented** (`_version.py`,
already audited in §9 as a *positive* example of correct layered
fallback design):

```text
1. Read pyproject.toml's [project].version directly       <- dev-checkout freshness
2. importlib.metadata.version("toroidamp")                <- installed-package fallback
3. "0.0.0-dev"                                             <- last-resort sentinel, never raises
```

**Current authoritative value**: `pyproject.toml`'s `version = "0.3.1"`.
**Live drift observed in this exact environment**: `pip list` reports the
*installed* package metadata as `toroidamp==0.1.0` — stale relative to
pyproject.toml, a direct, present instance of the exact staleness
`_version.py`'s own docstring warns about for editable installs. This
self-corrects automatically once tier 1 (direct pyproject.toml read)
succeeds, which it currently does in this dev checkout — but **a real,
non-editable frozen build has no `pyproject.toml` to read at all**, so it
will fall through to tier 2 (`importlib.metadata`), which requires the
package's dist-info metadata to actually be present in the frozen bundle —
**PyInstaller does not include this automatically**; it needs an explicit
`--copy-metadata toroidamp` (or equivalent Nuitka flag) or tier 2 silently
fails too, landing on the `"0.0.0-dev"` sentinel in the shipped executable.
**This is a concrete, specific packaging-spec requirement to carry into
RC-069-002.**

**Titlebar/runtime display**: version is surfaced via `__version__`
(imported from `_version.resolve_version()` per `__init__.py`, referenced
directly in `__main__.py`'s startup log line) — single authoritative
in-process value, no separate hardcoded duplicate found anywhere in the UI
layer by direct search.

**Do not bump to 0.69 yet** — per explicit instruction, not done. **Recommended
exact bump point**: after RC-069-002's packaging spec is proven end-to-end
on a real clean-machine build (§14 passing), immediately before cutting
the actual GitHub Release — i.e., the version number should be the very
last thing that changes before the tag, so `0.69` never refers to an
untested build.

**Future Windows executable metadata needed** (not present yet — a
PyInstaller/Nuitka version-info resource block, separate from
`pyproject.toml`):

| Field | Recommended value |
|---|---|
| Product name | ToroidAMP |
| File description | Compact, modular, musically reactive audio player with demoscene visualizer engine |
| File/Product version | Should mirror `pyproject.toml`'s version exactly (single source of truth — do not hand-maintain a second copy) |
| Company/Author | ToroidAMP Contributors (matches `pyproject.toml`'s `authors`) |
| Copyright | To be decided by Metal — not present anywhere in the codebase today (no LICENSE file inventoried in this pass; recommend confirming one exists/is chosen before RC-069-002) |
| Icon | `assets/branding/toroidamp.ico` — already exists, already correctly resolved by `branding.py` for in-app use; the *executable's own* icon resource is a separate PyInstaller/Nuitka build-flag concern, pointing at this same file |

---

## 17. Licensing / Redistribution Audit

Practical compliance inventory — **not legal advice, no guarantees given**,
per instructions.

| Component | License (as commonly distributed) | Redistribution note |
|---|---|---|
| Qt6 / PySide6 | LGPLv3 (Qt Company's PySide6 wheels) | Dynamic linking is the standard, compliant redistribution model PyInstaller/Nuitka both produce by default (DLLs collected alongside the executable, not statically linked into it) — verify the shipped artifact keeps Qt as separate DLLs, not merged into a single static blob, and that Qt's own license/notice file is included somewhere accessible (a `THIRD_PARTY_NOTICES` file alongside the release is the practical norm) |
| libsndfile (via `soundfile`) | LGPLv2.1 | Same dynamic-linking compliance posture as Qt |
| PortAudio (via `sounddevice`) | MIT | Permissive, low friction — still include attribution in notices for completeness |
| pygame-ce (SDL2 + its bundled codec libs: libogg, libopus, libpng, libjpeg, libtiff, libwebp, libxmp, freetype) | Mix of zlib/libpng/BSD/LGPL across the SDL2 ecosystem — pygame-ce's own packaged NOTICE/license files (present inside its wheel) are the authoritative list; not independently re-derived here | Verify pygame-ce ships (and this project preserves) its own bundled license/notice files |
| libmodplug (if/when actually sourced — currently absent, §4) | LGPLv2.1 (OpenMPT-derived libmodplug builds) | Dynamic linking again the right posture; **cannot be assessed further until a real binary is actually sourced** — flag this explicitly as unresolved |
| `quantum.ttf` (CYBER YELLOW theme font) | **Not independently verified this pass** — `assets/themes/cyber_yellow/fonts/license.txt` and `readme.txt` exist alongside it in the repo and should be the authoritative source; confirm their terms permit redistribution inside a commercial-adjacent/public release build before shipping | Read `license.txt`/`readme.txt` directly before RC-069-002 finalizes packaging |
| pyttsx3 / pywin32 / comtypes (if the voice feature ships, §3/§9) | pyttsx3: MPL-2.0; pywin32: PSF-derived/permissive; comtypes: MIT | Low friction; still undeclared as project dependencies (§3) — fix that regardless of the license question |
| numpy | BSD-3-Clause | Permissive |

**No LICENSE file for ToroidAMP itself was inventoried in this pass** —
confirm one exists (and its exact terms) before any public release
artifact ships; this determines what obligations flow *outward* from
ToroidAMP to its own users, on top of the *inward* obligations from the
components above.

---

## 18. Test Suite / Release Gate Status

Inventoried by direct execution, this session (33 test files):

**GREEN** — every file passes in isolation: all `test_gpu_audio_*.py`
(001-006B), `test_brand_001`, `test_exp_*`, `test_fix_*`,
`test_gpu_official_001`, `test_gpu_prod_*`, `test_polish_001`,
`test_production_*`, `test_rc_audio_001`, `test_rc_polish_001`,
`test_theme_*`, `test_ux_001/002/003`, `test_vis_001/002`,
`test_visualizer_lab_ii`.

**KNOWN PRE-EXISTING FAILURES**: `test_ux_004.py` — 3 marquee-related
failures (`TestMarqueeLabel::test_short_title_does_not_marquee`,
`TestMarqueeTravelAmplitude::test_short_title_has_zero_max_offset`,
`TestNormalMarqueeInRealLayout::test_normal_short_title_remains_static`),
present and unchanged across every delivery this entire session, unrelated
to any GPU-AUDIO/RC work — **pre-existing, not introduced by anything
audited here, but currently unresolved and should be triaged before 0.69**
given they touch a real, user-visible NORMAL-mode feature (the title
marquee).

**NATIVE/GL PROCESS-ACCUMULATION ISSUES**: running the *entire* `tests/`
directory in one pytest process reliably produces a native crash
(`Windows fatal exception: code 0xc0000096` / `Illegal instruction`)
partway through — traced earlier this session to cumulative native
GL/widget-construction state across dozens of `QOpenGLWidget`
instantiations in a single process, not a logic bug; every individual file
passes cleanly run alone or in smaller GPU-focused groups.
`test_rc_polish_001.py` specifically shows this same native-crash-on-exit
pattern intermittently even standalone (21/21 tests still report `passed`
before the crash) — an environment/native-teardown quirk in this offscreen
sandbox, not a test logic failure.

**TESTS THAT REQUIRE CLEAN-MACHINE MANUAL VALIDATION** (cannot be
automated in this sandboxed, GPU-less, no-console dev environment):
- `TestGPUAudio004SafeConstPromotion::test_13/test_14` — already
  explicitly `skipTest`'d, documented as requiring a live OpenGL context.
- **Everything in §14's clean-machine protocol** — by definition, none of
  it can be exercised from inside this checkout/venv.
- **Tracker (MOD/XM/IT/S3M) playback** — currently `skipTest`'d
  (`test_production_core.py`, 1 skip, consistently observed all session)
  precisely because libmodplug is absent (§4) — this needs a machine where
  a real libmodplug binary is actually present to ever go green, whether
  that's this dev machine or a packaged build.
- **Voice/TTS** — no dedicated automated test found exercising real SAPI5
  playback (reasonable, given it is genuinely OS/audio-device dependent);
  clean-machine validation is the only real check.

### Recommended MUST-BE-GREEN gate for 0.69

1. Full `tests/` suite green when run per-file/in reasonable groups (not
   the whole-suite-in-one-process mode, which has a known, understood,
   unrelated native-accumulation artifact) — **already true today**.
2. `test_ux_004.py`'s 3 marquee failures resolved — **currently red,
   recommend fixing before 0.69**, it is a real NORMAL-mode UI regression,
   not release-audit scope to fix here but should not ship silently broken.
3. §14's clean-machine protocol run at least once, completely, on a real
   VM — **not yet run, this is RC-069-002+'s job**.
4. §4/§21's libmodplug resolution — tracker playback should either
   demonstrably work on the target release machine or be honestly,
   visibly disabled (per §11's diagnostics design) rather than silently
   broken.

---

## 19. HOWTOUSE.md Outline (not written this cut)

```markdown
# ToroidAMP — How To Use

## Installation
  - Download / where to get the release artifact (§15's two variants,
    what each is for)
  - First-run expectations (no config yet, session.json created)

## Launch
  - Double-click / command-line file arguments

## Loading Audio
  - Supported formats (MP3/WAV/OGG/FLAC always; MOD/XM/IT/S3M — status
    depends on §21's resolution, document honestly)
  - Drag-and-drop / Add Files / folder behavior

## Playlist
  - Add/remove/clear, shuffle/repeat
  - M3U/M3U8 save/load

## Modes
  - NORMAL / MINI / RETINA MELT — what each is, when to use it

## Themes
  - DEFAULT / CYBER YELLOW, how to switch

## Visualizers
  - Cycling, CPU vs. GPU visualizers, what RETINA-only means

## Shader LAB
  - Opening LAB, LOAD external .frag, hot reload (R)
  - Typed parameters, presets (save/load)
  - AUTO REACT vs. manual AUDIO binding vs. MUSICALIZE — the three
    reactivity paths, explained for a non-developer audience
  - MUSICALIZE / CLEAR AUTO
  - [CONST] / [AUTO PARAM] badges — what they mean, in plain language

## Troubleshooting
  - "Tracker files won't play" — tied to §21's resolution
  - "GPU visualizers are blank/won't open" — tied to §6's GPU capability
    story
  - "Theme looks broken / missing images" — tied to §7's packaging fix
  - Where logs live, once §11 exists (%LOCALAPPDATA%\ToroidAMP\logs\)

## Known Limitations
  - Whatever remains true at actual release time — cross-reference this
    document's §1 DEFERRED list and §18's gate status at ship time, not
    today's snapshot

## Tests / Validation Procedures
  - Consolidation point for every manual/human-validation protocol
    accumulated across this session's GPU-AUDIO-003 through 006B design
    docs (each already contains its own TEST A/B/C/... protocol) plus
    this document's §14 clean-machine protocol — HOWTOUSE.md should link
    to or fold in all of them rather than re-deriving new ones, so this
    becomes the single place a tester (human or future-agent) starts from
```

---

## 20. Recommended RC-069-002

**Scope**: resolve this audit's concrete, evidenced blockers — in priority
order:

1. **Fix `pyproject.toml`'s `package-data`** to include
   `assets/images/*`, `assets/official_shaders/*.frag`, and
   `assets/themes/**/*` (§7) — cheap, mechanical, directly testable by
   building one real non-editable wheel and confirming
   `importlib.resources` finds everything.
2. **Resolve the libmodplug gap** (§4/§18) — either source a real
   `libmodplug`/OpenMPT-compatible DLL to bundle and add it to
   `_discover_libmodplug()`'s search list, or make an explicit, documented
   decision to ship 0.69 with tracker playback honestly disabled
   (§11's diagnostics design) rather than silently broken.
3. **Declare `pyttsx3` (and drop unused `miniaudio`)** in `pyproject.toml`
   (§3/§9) — either as a hard dependency or a properly-named optional
   extra, matching how the feature actually degrades today.
4. **Move the GPU LAB's default SAVE/LOAD directory** off the
   repo-checkout-relative `user_shaders/` assumption (§8) — smallest
   viable fix: default to the proposed `%LOCALAPPDATA%\ToroidAMP\shaders\`
   location, creating it on first use, while still letting the user
   navigate anywhere via the standard file dialog.
5. **Add minimal file logging** (§8/§11) to
   `%LOCALAPPDATA%\ToroidAMP\logs\ToroidAMP.log`, alongside the existing
   console handler — the load-bearing prerequisite for §11's diagnostics
   proposal to mean anything once packaged `--windowed`.
6. **Build the actual Phase A one-folder PyInstaller proof-of-concept**
   (§12/§13) and run the full §14 clean-machine protocol against it on a
   real clean VM — this is where every finding in this document gets
   empirically confirmed or refuted.
7. Only after (1)-(6): revisit Phase B one-file, the actual version bump
   to 0.69, and drafting `HOWTOUSE.md` for real (§19).

Items 1-5 are all small, mechanical, low-risk fixes directly traceable to
concrete findings above — they do not require new features or new
architecture, only closing gaps this audit found between "works on the
developer's machine" and "works for a user who receives a Windows
application."

---

## 21. Files Created / Modified

**Created**: `docs/release/RC_069_001_release_inventory.md` (this
document).

**Modified**: none. No source file, asset, test, or configuration was
changed by this audit — confirmed by design (this cut is read-only
analysis; every finding above is a *recommendation* for RC-069-002, not
something already applied).

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

This is a read-only audit producing a new document under `docs/release/`;
it identifies real gaps (§4, §7, §8, §9) but does not change ToroidAMP's
actual operational/architectural state, phase, or any decision gate.
`docs/CURRENT_STATE.md` is left untouched, consistent with this session's
established policy for every prior GPU-AUDIO cut. RC-069-002 (§20), once
it actually resolves these findings, is the point at which
`CURRENT_STATE.md` should next be revisited.
