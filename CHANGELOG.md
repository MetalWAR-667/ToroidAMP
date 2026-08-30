# Changelog

All notable user-facing changes to ToroidAMP are documented here.
Format loosely inspired by [Keep a Changelog](https://keepachangelog.com/).

ToroidAMP has **not yet had a formal public release**.

**A note on the version number:** ToroidAMP has been downgraded from the
internal working version 0.69 to **v0.666**. This is intentional, not a
typo and not a mistake by whatever tooling generated this file. Development
briefly got ahead of itself before Linux support, packaging, and basic UX
polish actually existed; the version number now reflects that honestly.
Progress will resume when morale improves.

## [Unreleased]

Nothing yet.

## [0.666] — Post Launch Hell & Welcome Linux Users

### Added

- **Core player**: NORMAL and MINI interface scales, session persistence
  (window layout, volume, theme, playlist), tray minimize/restore/quit
  lifecycle, live theme switching, a startup voice-identity line.
- **Audio playback**: MP3, WAV, OGG, and FLAC via `soundfile`; MOD, XM,
  IT, and S3M tracker module playback via `libxmp`; automatic decoder
  failure recovery (a bad file logs a clear error and cleanly advances
  the playlist instead of crashing or hanging).
- **Playlist**: add/remove/clear, shuffle, repeat, M3U/M3U8 save and
  load, Unicode filename support.
- **Visualizers**: several CPU visualizers plus official GPU visualizers
  (Toroid Identity, Cyber Bloom, Audio Reactive Reference), all cycled
  the same way; a fullscreen **RETINA MELT** mode for the GPU visualizer
  family.
- **Shader LAB** (RETINA-only): load any external `.frag` shader file,
  hot-reload it from disk with `R`, safely roll back to the previous
  working shader on a compile error, tune discovered typed parameters
  (float/bool/color) live, save/load JSON parameter presets, and bind
  any float parameter to a live audio source (bass/mids/treble/RMS/peak/
  beat) with an adjustable amount.
- **Safe const promotion**: shaders that tune themselves with
  `const float NAME = value;` constants automatically get LAB sliders for
  those values too — no shader edits required, and the original file on
  disk is never modified.
- **Runtime literal parameterization**: shaders that use a direct
  `iTime * value` time-scale multiplier, or a simple
  `float name = value;` local constant, also get automatically generated
  LAB controls for those — again with zero changes to the shader file.
- **MUSICALIZE**: a one-click action that generates bounded, deterministic
  audio bindings for a shader's eligible parameters — a fast starting
  point for making an arbitrary shader musically reactive without hand-
  tuning every control. Clearly marked `[AUTO]` in the LAB so it's
  obvious which bindings were generated versus set by hand; a dedicated
  **CLEAR AUTO** action removes only the generated ones, leaving any
  manual work untouched.
- **AUTO REACT**: a separate, generic presentation-layer audio reaction
  mode for Shadertoy-style shaders that don't author their own musical
  behavior.
- **Themes**: DEFAULT and CYBER YELLOW, switchable live, each with its
  own palette, chrome imagery, and (for CYBER YELLOW) a bundled display
  font.
- **Persistent logging**: a rotating log file at
  `%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log`, so a problem can be
  diagnosed after the fact instead of only in a console window.
- **Packaging**: a working PyInstaller ONEDIR build proof-of-concept —
  `ToroidAMP.exe` now runs standalone, from any folder, without a Python
  install.
- **Licensing**: ToroidAMP is released under the MIT License; a
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) inventories the
  open-source components the packaged build redistributes.
- **Linux support**: ToroidAMP now runs on Linux (validated on Linux Mint
  under VirtualBox) — startup, audio playback, system TTS, the PySide6 UI,
  and the official GPU/GLSL visualizers all confirmed working.
- **Playlist multi-selection**: standard desktop selection semantics in the
  playlist — click, Ctrl+click (additive), Shift+click (range) — with
  Delete/Backspace and the existing -DEL button now removing the entire
  selected set in one action instead of one track at a time.

### Changed

- Tracker (MOD/XM/IT/S3M) playback now uses `libxmp` instead of the
  originally-planned `libmodplug` — `libxmp` is already bundled by the
  existing `pygame-ce` dependency, so tracker playback requires no
  additional native library to source or install.
- Packaged Windows builds now launch windowed (no console window) —
  diagnostics remain fully available via the existing rotating log file at
  `%LOCALAPPDATA%\ToroidAMP\logs\toroidamp.log`. Running from source
  (`python -m toroidamp`, the `toroidamp` console script) is unaffected.
- NORMAL mode's breathing chassis border is noticeably more perceptible
  (wider amplitude swing plus a soft outer glow), so the window is easier
  to spot in peripheral vision among other desktop windows. MINI mode's
  deliberately understated presence is unchanged.
- Visualizer/reactivity analysis (RMS, bass/mids/treble, beat detection) is
  now derived from the decoded audio signal independent of the playback
  volume slider and independent of the fade-in/out envelope's amplitude
  contribution beyond true silence — lowering the volume no longer sedates
  the visualizers; genuine silence (e.g. a completed fade-out) still reads
  as silence.
- RETINA MELT is now an owned/transient window of the main chassis (like
  the Visualizer and Playlist modules already were), improving taskbar/dock
  grouping — a single ToroidAMP presence rather than one entry per window,
  where the desktop environment honors that relationship.
- The project version is now set consistently everywhere from one source
  (`pyproject.toml`'s `[project].version`, already the sole source
  `toroidamp/_version.py` reads at runtime) instead of drifting between the
  repository, the running application, and packaging metadata.

### Fixed

- A missing tracker backend used to fail silently (the selected track
  would just sit there, not playing, with no error and no automatic
  skip to the next track). It now fails exactly like any other bad file:
  a clear log entry, and a clean automatic advance to the next playlist
  entry.
- `ThemeDefinition` was used in two UI modules' type annotations without
  being imported — invisible on newer Python (3.14's deferred annotation
  evaluation) but a hard `NameError` on Python ≤3.13, including on Linux.
- Two official GPU shaders were checked in with a UTF-8 byte-order mark,
  which strict GLSL compilers (Mesa, used on Linux) rejected as an invalid
  token after ToroidAMP's own header got prepended to the shader source,
  while lenient Windows GPU drivers silently tolerated it. Shader files are
  now read BOM-safely regardless of platform.
- Running bare `pytest` from the repository root (rather than
  `python -m pytest`) failed to collect three experimental test modules;
  the project's pytest configuration now makes both invocations equivalent.
- A rare native crash (observed as an access violation on Windows, a
  segfault on Linux) during a full test-suite run was traced to a test
  leaving a real background audio thread running unattended, racing later
  GUI/GL work on the main thread. Also hardened: OpenGL cleanup could run
  twice per visualizer widget; the process-wide `ThemeManager` singleton
  could retain a live signal connection to an already-destroyed window.

### Known Limitations

- **Tracker seek is approximate, not sample-accurate.** Tracker module
  formats address playback position by pattern/row, not by arbitrary
  time offset, so seeking lands near the requested time rather than
  exactly on it. This is a structural property of the format, not a bug.
- **S3M real-file validation is still pending.** S3M loads through the
  exact same code path already validated for MOD/XM/IT, but no real S3M
  test file has been available yet to confirm it end-to-end.
- **GPU visualizers and RETINA MELT require a working OpenGL 3.3 Core
  driver.** The base player (playback, playlist, CPU visualizers) remains
  fully usable without one; there is not yet a polished in-app message
  explaining *why* RETINA is unavailable if a suitable GPU isn't present.
- **Packaging is not yet public-release-ready.** A working ONEDIR build
  exists, but it has not yet been through a clean-machine validation
  pass, a public license text for two third-party components is not yet
  fully finalized (see `THIRD_PARTY_NOTICES.md`), and no installer or
  single-file (`ONEFILE`) build has been produced.
- **Playlist drag-and-drop reordering is not yet implemented.** Multi-
  selection and bulk removal are; reordering by dragging a selection
  within the list was evaluated for this cut but intentionally deferred —
  `PlaylistManager` is a plain ordered list, not a Qt item model, so
  wiring Qt's native multi-item drag-reorder to it safely (without risking
  playback identity or playlist-order correctness) is a small architecture
  change in its own right, not a bounded polish item.
- **Linux requires one manually-installed system package**: `libxcb-cursor0`
  (see the README's Linux prerequisites) for Qt's `xcb` platform plugin.
  This cannot be resolved via `pip`.
