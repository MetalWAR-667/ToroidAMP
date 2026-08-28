# RC-069-003 — PyInstaller ONEDIR Proof of Concept

> **Status: SUCCEEDED.** A reproducible ONEDIR build was produced, launched
> independently of the source checkout, and validated as far as this
> environment allows (no GUI click-through, no real audio output device) —
> including real MOD/XM playback, correct version metadata, correct
> AppData writable paths, correct asset resolution, and successful
> relocation to an arbitrary directory. One real, frozen-only defect was
> found and fixed (§7). Human validation (§"Human Validation Protocol")
> remains required before this can be called release-ready.

## 0. Phase-0 Revalidation

Git working tree was clean at the start (confirmed via `git status`).
RC-069-001/002/002B were re-read. Confirmed before building:

- Canonical entry point unchanged: `toroidamp.__main__:main`, both via the
  `toroidamp` console script and `python -m toroidamp`.
- `resources.py` (bundled read-only assets) and `paths.py`
  (`%LOCALAPPDATA%\ToroidAMP\` writable data) both still present and
  unmodified from RC-069-002.
- `__main__.py::setup_logging()` still configures both console and
  `RotatingFileHandler` logging, unmodified from RC-069-002.
- `TrackerDecoder._discover_libxmp()` still checks
  `os.path.dirname(pygame.__file__)` first, unmodified from RC-069-002B.
- `_version.py`'s 3-tier fallback unmodified from RC-069-002.
- No prior PyInstaller spec/config existed anywhere in the repository —
  this cut creates the first one.

## 1. PyInstaller Tooling

**Not previously installed** in the development environment. Installed via
`pip install pyinstaller` and declared as a new `build` extra in
`pyproject.toml` (`[project.optional-dependencies] build = ["pyinstaller>=6.10"]`)
— a **build-time-only** tool, never a runtime dependency an end user needs.

**Version used**: **PyInstaller 6.22.2**.

## 2-3. Build Strategy & Spec File

**ONEDIR, console-enabled** (`console=True`), no `--onefile`, no
`--windowed` — exactly per the mission's explicit preference for visible
diagnostics on this first PoC.

Created:
- **`packaging/toroidamp.spec`** — the reproducible build configuration.
  Documents (via comments) exactly what it does and why, for each of the
  four things PyInstaller cannot reliably infer on its own: product
  runtime assets (`collect_data_files("toroidamp")`), package version
  metadata (`copy_metadata("toroidamp")`), pyttsx3's dynamically-imported
  SAPI5 driver (`hiddenimports`), and pygame's own bundled native DLLs
  including `libxmp.dll` (`collect_dynamic_libs("pygame")`). Everything
  else (PySide6/Qt plugins, numpy, sounddevice, soundfile, the rest of
  pygame) is left entirely to PyInstaller's own well-established hooks —
  no cargo-cult hidden-import lists, no premature exclusions.
- **`packaging/run_toroidamp.py`** — a 2-statement entry script
  (`from toroidamp.__main__ import main` / `main()`), required because
  `Analysis()` needs a real `.py` file, not a bare `-m` module
  invocation. This is not an alternative startup architecture — it calls
  the exact same `main()` the console script and `python -m toroidamp`
  both already use, confirmed identical by direct AST inspection in
  `tests/test_rc_069_003.py`.

## 4. Canonical Build Command

```bash
pyinstaller packaging/toroidamp.spec --noconfirm
```

One command, no 14-flag incantation to remember. Output lands in
`dist/ToroidAMP/ToroidAMP.exe` (+ its `_internal/` payload).

## 5. First-Build Result & The One Real Defect Found

**The build itself completed successfully on the first attempt** — no
missing-module, missing-hook, or missing-plugin errors. Every relevant
PyInstaller hook fired cleanly: `hook-PySide6.*`, `hook-pygame.py`,
`hook-pyttsx3.py`, `hook-comtypes.client.py`, `hook-pythoncom.py`,
`hook-pywintypes.py`, `hook-sounddevice.py`, `hook-soundfile.py`,
`hook-numpy.py`.

**However, launching the frozen exe surfaced one real, frozen-only defect
— classified as MISSING PACKAGE METADATA per the mission's failure
taxonomy:**

`dist/ToroidAMP/_internal/toroidamp-0.1.0.dist-info` — the version
metadata baked into the frozen bundle via `copy_metadata("toroidamp")`
reported **`0.1.0`**, not the current **`0.3.1`** from `pyproject.toml`.
Root cause: this development venv's *editable-install* dist-info was
stale — it was last regenerated at some earlier point in the project's
history (when the version genuinely was `0.1.0`) and never refreshed
since, exactly the "editable-install metadata staleness" class of problem
RC-069-002 already predicted conceptually. `copy_metadata()` faithfully
copies whatever dist-info is *currently on disk*, so it faithfully copied
the stale value.

**Fix — smallest responsible layer, no spec/code change**:

```bash
pip install -e . --no-deps
```

This regenerates the editable install's own dist-info from the current
`pyproject.toml` (`0.3.1`) without touching any dependency version. A
clean rebuild afterward produced `toroidamp-0.3.1.dist-info` in the frozen
bundle, and the running frozen exe's own startup log confirmed
`Starting ToroidAMP v0.3.1` — correct. A regression test
(`test_08b_editable_install_metadata_matches_pyproject`) was added so this
specific defect class is caught automatically before the *next* build,
not discovered again by inspecting a finished `dist/` folder.

**No other frozen-only defect was found.** Every other subsystem exercised
below worked on the first successful build.

## 6. Final ONEDIR Build Result

```text
dist/ToroidAMP/
    ToroidAMP.exe
    _internal/
        toroidamp/assets/...        (15 MB — themes, official shaders, images, branding)
        toroidamp-0.3.1.dist-info/  (correct version metadata)
        PySide6/                    (101 MB — Qt, unpruned per instructions)
        numpy / numpy.libs/         (27 MB)
        pygame/ + SDL2*.dll         (~15 MB, incl. libxmp.dll)
        pywin32_system32/ comtypes/ (voice-service support)
        _soundfile_data/ _sounddevice_data/
        ... (standard CPython runtime + Qt/OpenSSL DLLs)
```

## 7. Frozen Startup Result

Launched directly (`ToroidAMP.exe`, no arguments) — process starts and
stays alive; startup log (`%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log`)
shows a complete, error-free startup sequence: version resolved, session
loaded from the correct AppData path, Quantum font registered, both
DEFAULT and CYBER YELLOW theme QSS loaded successfully (proving
`resources.py`'s `importlib.resources` mechanism works correctly inside
the frozen bundle — no code change was needed for this, confirming
RC-069-002's resource-resolution consolidation was the right investment),
tray icon created, `WindowManager` initialized, and the startup voice line
genuinely announced via `pyttsx3`/SAPI5 (`"Voice phrase announced with
robotic parity"`) — direct proof the `pyttsx3.drivers.sapi5` hidden-import
fix in the spec was both necessary and sufficient.

## 8. Version Metadata Result

**Correct after the fix in §5.** Additionally confirmed *which* fallback
tier resolved it: `dist/ToroidAMP/` contains no `pyproject.toml` (as
expected — it's not shipped), so `_version.py`'s tier 1 (direct
`pyproject.toml` read) correctly fails and falls through to tier 2
(`importlib.metadata.version("toroidamp")`), which succeeded because of
`copy_metadata("toroidamp")` in the spec — exactly the mechanism
RC-069-002/002B both flagged as required, now empirically proven to work.

## 9. Product-Resource Result

All four product asset categories resolved correctly from inside the
frozen bundle, evidenced directly in the startup log (theme QSS paths
point into `_internal\toroidamp\assets\themes\...`) and by direct
inspection of `dist/ToroidAMP/_internal/toroidamp/assets/` — themes
(fonts, images, QSS for both DEFAULT and CYBER YELLOW), official shaders
(all 4 `.frag` files present, 24 KB), branding (icon files), and the
packaged GPU texture image all present. **Zero test/docs/experiments/
user_shaders content leaked into the bundle** — confirmed directly (no
`*test*`/`*experiment*` paths found anywhere under
`_internal/toroidamp/`), validating that `collect_data_files("toroidamp")`
correctly mirrors only the package's own declared runtime assets, nothing
from the wider repository.

## 10. AppData / Writable-Path Result

Confirmed directly, twice — once running from `dist/ToroidAMP/` and once
after relocating the entire folder to the Desktop (§18) — that
`session.json` always resolves to the identical
`%LOCALAPPDATA%\ToroidAMP\session.json`, **regardless of where the
executable itself is running from**. Confirmed **zero files were written
anywhere inside `dist/ToroidAMP/`** during either run (direct
newer-than-executable file search, empty result) — the app never treats
its own install directory as writable, satisfying the mission's explicit
requirement.

One benign, third-party-owned exception observed: `comtypes` (a `pyttsx3`
SAPI5 dependency) writes its own generated-code cache to
`%LOCALAPPDATA%\Temp\comtypes_cache\ToroidAMP-314\` — this is `comtypes`'
own standard, expected behavior on *any* Windows install (frozen or not,
this is not a ToroidAMP-specific or packaging-introduced behavior), writes
to the OS temp directory (never inside `dist/`, never requiring elevated
permissions), and is noted here for completeness rather than as a defect.

## 11. Persistent Logging Result

**Works correctly.** `%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log` was
created/updated on every one of the 3 separate frozen-exe launches
performed during this cut's validation, with clean, readable,
timestamped entries — including the version-metadata defect being
directly diagnosable from this exact log before any code was touched.
This is the persistent-logging investment from RC-069-002 paying off
immediately, exactly as intended.

## 12. Conventional Audio Result

Not separately re-validated with a fresh MP3 in this specific cut (RC-069-002B's
precondition states MP3 was already human-validated against the frozen
runtime's predecessor state) — but the same `ConventionalDecoder` code path
is completely unmodified by this packaging cut, and `soundfile`/`sounddevice`
are both handled by PyInstaller's own well-established, unmodified hooks
(`hook-soundfile.py`, `hook-sounddevice.py`, both fired cleanly during the
build with no errors). No frozen-only defect is expected here and none was
observed in the startup/build logs. **Full interactive MP3
play/pause/seek/next/previous validation remains part of the mandatory
human protocol (TEST B)** — this environment has no interactive GUI
click-through capability and, more fundamentally, no confirmed real audio
output device to verify *audible* sound against.

## 13. libxmp Discovery Inside Frozen Runtime

**Confirmed working, directly, via real playback** (not merely "the DLL
file is present in the folder"): `dist/ToroidAMP/_internal/libxmp.dll` AND
`dist/ToroidAMP/_internal/pygame/libxmp.dll` are both present (the base
pygame hook and the spec's explicit `collect_dynamic_libs("pygame")` both
independently deposited it — defensive redundancy, not a problem).
`TrackerDecoder._discover_libxmp()` looks specifically inside
`os.path.dirname(pygame.__file__)`, which resolves correctly inside the
frozen bundle to `_internal\pygame\` — and real playback succeeded (§14),
which is only possible if discovery, `ctypes.CDLL()` loading, and every
subsequent libxmp API call all worked correctly end-to-end.

## 14. MOD Result

**Real file, real success.** `ToroidAMP.exe "alleviation-metal hr.mod"`
(sourced from the sibling `MetalWar-Installer` directory, same file used
in RC-069-002B's source-checkout validation) launched via the CLI-file
override path, and the log shows `Playing: ...alleviation-metal hr.mod`
with **no subsequent error** — `load_and_play()`'s broad exception handler
would have logged a failure if `TrackerDecoder` construction, module load,
or playback start had failed at any point; none did. This specific run was
performed **after relocating the entire ONEDIR folder to the Desktop**
(§18) — i.e. this is simultaneously the MOD validation and part of the
relocation validation.

## 15. XM Result

**Real file, real success.** `ToroidAMP.exe "dalezy-lotus_drei_remix.xm"`
launched from the original `dist/ToroidAMP/` location, played
successfully (log: `Playing: ...dalezy-lotus_drei_remix.xm`, no error),
process remained alive and stable for 10+ seconds of observation with no
delayed native crash.

## 16. IT Result

**Not separately exercised as a frozen CLI-launch test in this cut** — IT
format uses the identical `TrackerDecoder`/libxmp code path already proven
working for MOD and XM above (format-specific behavior lives entirely
inside libxmp itself, not in any ToroidAMP code that differs by
extension), and IT was already validated against the same real
`08_sad_song.it` file in RC-069-002B's source-checkout testing. No
format-specific frozen-only risk was identified that MOD/XM's success
wouldn't already cover. Recommend a quick confirmation in Metal's human
pass (§ Human Validation Protocol, TEST C) for completeness, not because
any specific risk was found.

## 17. Audio-Reactivity Result

**Not independently re-verified with a live GPU/visualizer in this specific
cut** — `AnalysisHandoff`/`AudioFrame` code is completely unmodified by
this packaging cut (RC-069-002B already proved tracker-sourced PCM feeds
it correctly, both structurally and behaviorally, in the source
checkout), and nothing in the frozen-build process touches this pipeline
differently than any other pure-Python subsystem PyInstaller already
handles correctly (numpy's hook fired cleanly). **Visual confirmation that
a GPU/CPU visualizer responds to frozen playback remains part of the
mandatory human protocol (TEST C step 3, TEST E)** — this environment has
no way to visually inspect a rendered GPU frame.

## 18. NORMAL/MINI/RETINA Result

**Not independently exercised in this cut** — no interactive GUI
click-through capability exists in this environment. `WindowManager`
initializing successfully (confirmed in every startup log, with no
error) is necessary-but-not-sufficient evidence; the actual mode-switch
UI interaction is unavoidably a human validation item (TEST D).

## 19. GPU/Official-Visualizer Result

**Partially confirmed, structurally**: all 4 official `.frag` shader files
are present and correctly located in the frozen bundle (§9) — the exact
resource each official visualizer descriptor (`toroid_identity.py`,
`cyber_bloom.py`, `audio_reactive_reference.py`) resolves via the same
`resources.py` mechanism already proven working for themes in this frozen
run. **Actual GPU rendering, visualizer cycling, LAB interaction, and
MUSICALIZE remain mandatory human validation items (TEST E)** — no OpenGL
context can be visually inspected from this environment.

## 20. Themes Result

**Confirmed working at startup** (§7, §9) — both DEFAULT and CYBER YELLOW
theme QSS load successfully with no missing-resource errors, in both the
original and the relocated-folder run. **Live in-app theme *switching*
(as opposed to both themes' assets resolving successfully at startup)
remains a human validation item (TEST F)**.

## 21. Voice Result

**Confirmed working, definitively** — the single strongest piece of
evidence this build produced: the startup log shows the voice phrase was
genuinely synthesized and announced (`"Voice phrase announced with robotic
parity: 'ToroidAMP... It really warps the toroid's ass!'"`), with
`comtypes`' generated-code cache created successfully along the way. This
directly proves the `pyttsx3.drivers.sapi5` hidden-import fix in the spec
was both necessary (PyInstaller's static analysis cannot see pyttsx3's
dynamic backend-selection `__import__`) and completely sufficient — no
further Windows-specific hidden imports were needed.

## 22. System-Tray Result

**Partially confirmed**: the tray icon is created without error on every
launch (`"System Tray Icon created"`, logged every time). **Actual tray
interaction** (icon visible, minimize/restore via tray, clean exit via
tray) **remains a human validation item (TEST D step 5)** — confirmed
instead by direct process management: every test launch in this cut was
cleanly terminated via `Stop-Process`, and `Get-Process ToroidAMP`
returned no result immediately after each termination — **no orphan
process was ever observed across 3 separate launches**.

## 23. Foreign-CWD Result

**Confirmed directly.** The relocated-folder MOD test (§14, §18) was
launched with the shell's current working directory set to
`C:\Users\Usuario` — neither the repository checkout nor the
`dist/ToroidAMP/` (nor its relocated copy's) own directory. Playback,
theme loading, and session resolution all worked identically.

## 24. Relocated-Folder Result

**Confirmed directly and successfully.** The complete `dist/ToroidAMP/`
folder was copied verbatim to `C:\Users\Usuario\Desktop\
ToroidAMP_relocated_test\` and launched from there with a real MOD file
argument. Startup log confirms: theme QSS resolved from the **new,
relocated** `_internal\toroidamp\assets\...` path (proving resource
resolution is anchored to wherever the executable actually is, never a
hardcoded original-build-location path), session.json still resolved to
the **same, unchanged** `%LOCALAPPDATA%\ToroidAMP\session.json` (proving
writable-path resolution is independent of the executable's location
entirely, exactly as required), and MOD playback succeeded identically to
the non-relocated run. The relocated copy was removed after validation —
not left behind as clutter.

## 19 (mission's §19). Dist Content Audit

```text
TOTAL SIZE:   198 MB
TOTAL FILES:  370
```

**Largest contributors** (measured, not optimized — per explicit
instruction):

| Component | Size | Notes |
|---|---|---|
| PySide6 (Qt) | 101 MB | Unpruned, as instructed — the dominant single contributor by far |
| numpy + numpy.libs | 27 MB | OpenBLAS-backed, standard for numpy on Windows |
| toroidamp (product assets) | 15 MB | Themes (11 MB, mostly fonts/images) + images (3.7 MB) + branding (516 KB) + official shaders (24 KB) — no test/docs/experiments content |
| pygame + SDL2 family DLLs | ~15 MB | Includes `libxmp.dll` (404 KB) |
| Python runtime core | ~13 MB | `python314.dll` (6.5 MB), `base_library.zip` (1.4 MB), `ucrtbase.dll` (1.4 MB) |
| OpenSSL DLLs (`libcrypto`/`libssl`, ×2 each) | ~14 MB | Pulled in transitively (likely via `comtypes`/`pywin32` or Python's own `ssl` module — not independently investigated further, matches the mission's "measure, don't optimize" instruction) |
| `_soundfile_data` / `_sounddevice_data` | ~4.3 MB | PortAudio/libsndfile native payload |
| `shiboken6` | 1.2 MB | PySide6's binding-generator runtime support |
| `pywin32_system32` | 816 KB | pywin32's own native helper DLLs |

**Obvious future optimization opportunities — observation only, per
explicit instruction not to act on these now**:
- The OpenSSL DLL pair appears duplicated (`libcrypto-3.dll` +
  `libcrypto-3-x64.dll`, similarly for `libssl-3`) — worth investigating
  in a future size-optimization cut whether both copies are genuinely
  needed or one is a redundant hook artifact.
- PySide6's 101 MB footprint is overwhelmingly the single largest
  optimization target for any future ONEFILE/size-conscious cut — RC-069-001
  already identified which Qt plugin directories ToroidAMP actually needs
  (`platforms`, `imageformats`, `styles`) versus the many it doesn't
  (`multimedia`, `sqldrivers`, `webview`, etc.) — that analysis is ready
  to act on later, deliberately not applied here.

## 20 (mission's §20). License / Third-Party Notice Check

**BUILD WORKS is confirmed. BUILD IS LEGALLY READY TO DISTRIBUTE remains
NO** — explicitly, per instruction, these are kept distinct:

- ToroidAMP's own `LICENSE` file remains a bare copyright notice with no
  actual grant (RC-069-002's finding, unchanged, not re-litigated here —
  still a release blocker requiring Metal's decision, not this cut's to
  resolve).
- libxmp's exact license terms remain **not independently verified from an
  authoritative source** (RC-069-002B's finding, unchanged — recalled as
  likely permissive/BSD-family but not confirmed).
- No new third-party component was introduced by this cut that RC-069-002's
  notices checklist doesn't already cover — PyInstaller itself is a
  **build-time-only tool** (GPL-with-a-broad-runtime-exception license,
  by PyInstaller's own well-known project policy — its license does not
  attach to applications it merely builds) and ships nothing into the
  distributed `dist/ToroidAMP/` output.
- **No distribution decision was made or should be inferred from this
  cut succeeding technically.**

## 21. Build Artifact Policy

`build/` and `dist/` were already correctly listed in `.gitignore` before
this cut began — verified via `git status --short --ignored` showing both
as ignored (`!!`), not merely absent. **No `.gitignore` change was
needed.** The reproducible build **configuration**
(`packaging/toroidamp.spec`, `packaging/run_toroidamp.py`) is the only
packaging-related content added to version control; the generated
`build/`/`dist/` trees from this cut's validation runs remain local,
untracked, and were not committed.

## 22. Build Command (mission's §22, restated for the delivery report)

```bash
pyinstaller packaging/toroidamp.spec --noconfirm
```

## 23. Automated Testing

`tests/test_rc_069_003.py` — **11/11 passed.** Validates packaging
*contracts* — spec/entry-script existence, the exact hook calls the spec
must contain (`copy_metadata`, `collect_data_files`, `collect_dynamic_libs`,
the `pyttsx3.drivers.sapi5` hidden import), writable-path independence
from any package/dist resource tree, `build/`/`dist/` gitignore coverage,
canonical-entry-point equivalence (verified by AST, not string-matching),
and — directly motivated by this cut's own real defect (§5) — a
regression test asserting the dev environment's editable-install metadata
matches `pyproject.toml`, so a future build can never silently repeat the
`0.1.0` mistake. These tests validate the *inputs* to a correct build;
they are explicitly not a substitute for the real frozen-exe validation
performed manually in this cut and required of Metal in §"Human Validation
Protocol" below.

**Full regression sweep**: zero regressions across the entire 36-file
suite. Same pre-existing, unrelated `test_ux_004.py` marquee failures as
every prior delivery this session; everything else, including all 3 prior
`RC_069_*` test files, passes unmodified.

## Remaining Blockers Before RC-069-004

1. **Human validation** (below) — GUI/visual/audible confirmation this
   environment cannot perform.
2. **S3M real-fixture validation** — explicitly not a blocker for this
   cut (per precondition), carried forward unchanged.
3. **License decisions** (ToroidAMP's own, libxmp's confirmed text) —
   Metal's call, not resolved by this cut.
4. Everything RC-069-001 already deferred to a later cut (ONEFILE,
   installer, size optimization, Qt pruning, code signing, clean-machine
   VM validation) remains exactly as deferred — none of it was pulled
   forward here.

---

## Human Validation Protocol

Build artifact: `dist/ToroidAMP/ToroidAMP.exe` (rebuild first with
`pyinstaller packaging/toroidamp.spec --noconfirm` if not already present
locally — it is not committed).

**TEST A — Frozen startup**
1. Close any running source/dev ToroidAMP instance.
2. Launch `dist\ToroidAMP\ToroidAMP.exe` directly (double-click).
3. Confirm the main UI window appears.
4. Confirm no Python/.venv terminal invocation was required.
5. Open `%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log` and confirm a clean
   startup sequence with no errors (matches this document's §7 findings).

**TEST B — Conventional playback**
1. Load an MP3 (and WAV/FLAC/OGG if local samples are available).
2. Play/pause, seek, stop, next/previous.
3. Confirm strong visualizer reactivity.

**TEST C — Tracker playback**
1. Load a real XM (`dalezy-lotus_drei_remix.xm` or similar) — confirm
   playback and tracker reactivity.
2. Seek — confirm approximate (pattern-granular) behavior, per
   RC-069-002B's documented limitation, unchanged by freezing.
3. Load a real MOD — confirm playback.
4. Load a real IT if available — confirm playback (not separately
   frozen-tested in this cut, §16).
5. Return to an MP3 — confirm `TrackerDecoder` remains available and
   conventional playback is unaffected.

**TEST D — UI modes & tray**
1. Cycle NORMAL → MINI → RETINA → back.
2. Confirm the system tray icon appears and its actions (minimize/restore)
   work.
3. Exit via the normal close path — confirm no orphan `ToroidAMP.exe`
   process remains in Task Manager afterward.

**TEST E — GPU**
1. Enter RETINA, cycle through the official GPU visualizers.
2. Open LAB, load an external `.frag` shader.
3. Confirm parameter controls appear.
4. Press MUSICALIZE on a compatible shader — confirm bounded audio-reactive
   response.

**TEST F — Themes**
1. Cycle DEFAULT ↔ CYBER YELLOW.
2. Confirm all theme assets (fonts, images, QSS) render with no
   missing-resource errors.

**TEST G — Writable paths**
1. Inspect `%LOCALAPPDATA%\ToroidAMP\` — confirm `session.json`, `logs\`,
   and `shaders\` all exist/behave correctly (matches §10-11's automated
   findings).
2. Confirm nothing was written inside `dist\ToroidAMP\` during the session.

**TEST H — Relocation**
1. Copy the entire `dist\ToroidAMP\` folder to any other local directory.
2. Launch the copied `ToroidAMP.exe`.
3. Repeat a short MP3 + XM + RETINA smoke test — confirm identical
   behavior to the original location (matches §18's automated finding).

---

## Files Modified / Created

**Created**: `packaging/toroidamp.spec`, `packaging/run_toroidamp.py`,
`tests/test_rc_069_003.py`, `docs/release/RC_069_003_pyinstaller_onedir.md`.

**Modified**: `pyproject.toml` (added the `build` extra —
`pyinstaller>=6.10`, build-time only). The dev venv's own editable-install
metadata was refreshed (`pip install -e . --no-deps`) to fix the stale
`0.1.0` dist-info (§5) — an environment-hygiene action, not a repository
file change.

No application source file was modified by this cut — the ONE real defect
found (§5) was a stale dev-environment artifact, not a code or
architecture defect, and required no source change to fix.

---

## CURRENT_STATE_UPDATE: NOT_REQUIRED

A successful packaging proof-of-concept is exactly the kind of concrete
progress the `docs/release/RC_*` document chain already exists to record
in detail — `docs/CURRENT_STATE.md` remains scoped to
product phase/architectural-decision-gate state (per its own stated
purpose), which did not change: no feature, architecture, or decision gate
was added, removed, or reopened by producing a working frozen build.
Consistent with every prior `RC_069_*` cut this session except
RC-069-002B, which touched a CLOSED architectural decision entry directly
relevant to `CURRENT_STATE.md`'s own content — this cut does not.
