# ToroidAMP — Current State

> **It really warps the toroid's ass!**

## 1. Purpose

This document records the **current operational state** of ToroidAMP.

It answers:

* Where is the project now?
* What has been established?
* What remains open?
* What is actively being worked on?
* What should happen next?

`CURRENT_STATE.md` is intentionally temporary.

It should remain short enough to provide useful project context in a few minutes.

Completed work that no longer affects the active state should be compressed into `ARCHIVE.md`.

Current architectural truth belongs in `ARCHITECTURE.md`.

---

## 2. Project Status

**Project:** ToroidAMP
**Stage:** Release Gate (v0.669, Windows)
**Current Phase:** RELEASE-GATE-0.669-WINDOWS
  - RELEASE-GATE-0.669-WINDOWS: PASS
**Status:** CLOSED (Next: Metal reviews and publishes)
**Implementation:** PRODUCTION APPLICATION (`toroidamp` v0.669)
**v0.669:** READY_FOR_PUBLICATION (Windows only — not yet RELEASED; Linux parity for post-0.667 content is deferred)

v0.667's release-gate/closeout record below is historical (that validation and staging genuinely happened at 0.667, and its archives under `release/0.667/` remain exactly as validated, untouched by this version bump). Source has since moved on to v0.669 — nine new visualizers, UX-005 (keyboard shortcuts, global media keys, recursive drag & drop, playlist search, track-change OSD), and DSP-001 (micro-fades, gapless/crossfade, loudness normalization + safety limiter) — see CHANGELOG.md `[0.669]`. Windows artifact gate PASS; Linux remains at v0.667 (post-0.667 content is Windows-only for now, deferred to Linux in a future cut). Two real production bugs were found and fixed during this gate: the MetalWar Credits emblem never rendering (`convert_alpha()` needs a display surface ToroidAMP never opens), and DSP-001C's safety limiter running on the pre-volume signal instead of the actual final output (causing an unintended ~1.3% gain reduction on any track peaking at 1.0, regardless of volume). See the RELEASE-GATE-0.669-WINDOWS report for full detail, including a known, pre-existing, intermittent, test-process-only native GL crash (never reproduced in the shipped artifact) affecting a full local `pytest` run.

ToroidAMP v0.667 native Linux ONEDIR packaging has completed full validation on Ubuntu physical hardware (audio playback, GLSL shaders, Wayland Unified Chassis, non-native dialogs, isolated user paths, and zero source dependencies), and that exact validated artifact has been transferred to the Windows closeout machine and staged for release, unmodified.

ToroidAMP v0.667 native Windows ONEDIR packaging (PyInstaller) has completed full validation on this dev machine: frozen isolated launch, 5/5 clean TTS launch/close cycles via `sounddevice` (no pygame.mixer dependency), all four conventional audio formats (WAV/MP3/OGG/FLAC) plus a representative tracker MOD file (confirming `libxmp.dll` resolves in the frozen bundle), Windows independent-top-level Playlist/Visualizer docking (pixel-exact via UI Automation), MINI↔NORMAL transitions, RETINA MELT enter/exit, isolated user-writable state (`%LOCALAPPDATA%\ToroidAMP\`), and a clean `git status`. One real packaging defect was found and fixed: a stale editable-install `dist-info` (0.666) was baking an incorrect version into the frozen artifact via `copy_metadata()`; fixed by refreshing the editable install (`pip install -e . --no-deps --force-reinstall`) before rebuilding — no tracked source files changed. Full interactive UI verification (file dialogs, GLSL Lab, CPU/GPU visualizer switching) was only partially achievable via UI Automation in this session (no human eyes/ears available); see the RELEASE-GATE-0.667-WINDOWS report for the exact boundary of what was verified programmatically vs. what still benefits from Metal's direct confirmation.








---

## 3. Current Product Definition

ToroidAMP is a lightweight, open-source, cross-platform desktop audio player written primarily in Python.

Its identity is based on:

* local-file playback;
* a compact desktop interface;
* a current-playlist workflow;
* Windows and Linux support;
* classic tracker-module support;
* audio-reactive visualization as a first-class feature;
* fullscreen visualization;
* background/tray operation;
* contributor-friendly internal boundaries.

ToroidAMP is intentionally **not** being designed as a music-library platform or streaming service.

---

## 4. V1 Target

The current V1 target is:

```text id="t8sd8e"
Launch
   ↓
Load music
   ↓
Build / load playlist
   ↓
Play music
   ↓
Visualize audio
   ↓
Optional fullscreen
   ↓
Minimize to background
   ↓
Continue playback
```

Target audio formats:

```text id="dvx93u"
Conventional
├── WAV
├── MP3
├── OGG/Vorbis
└── FLAC

Tracker
├── MOD
├── XM
├── S3M
└── IT
```

---

## 5. Foundation Documents

Current project documentation:

```text id="2v4fkv"
docs/
├── VISION.md
├── SCOPE.md
├── ARCHITECTURE.md
├── CURRENT_STATE.md
└── ARCHIVE.md
```

Current status:

* `VISION.md` — CREATED.
* `SCOPE.md` — CREATED.
* `ARCHITECTURE.md` — CREATED.
* `CURRENT_STATE.md` — CREATED.
* `ARCHIVE.md` — PENDING INITIALIZATION.

Public-facing `README.md` remains pending.

---

## 6. Established Decisions

The following decisions are currently considered established:

### Product

* Project name: **ToroidAMP**.
* Project will be open source.
* Primary language: **Python**.
* Target platforms: **Windows and Linux**.
* Local music files are the primary content source.
* Visualization is a core product feature.
* Fullscreen visualization is required for V1.
* Tracker-module playback is required for V1.
* Current-playlist workflow is preferred over music-library management.
* Playback must continue while the main window is minimized or hidden.
* System-tray operation is part of the V1 target.

### Persistence

* No database is currently required.
* Lightweight configuration/session persistence is preferred.
* JSON or equivalent structured storage is the current direction.
* M3U/M3U8 is the preferred playlist direction pending implementation validation.

### Architecture

* Playback and visualization must remain independent.
* Visualizers should consume normalized audio-analysis data rather than decode audio themselves.
* Platform-specific behavior must remain isolated.
* A formal third-party plugin system is not required for V1.
* Extensibility should first emerge from proven internal contracts.

---

## 7. Existing Technical Assets

ToroidAMP is a new project but does not begin without prior experimental work.

The existing **MetalWar-Installer** repository contains candidate source material for extraction and adaptation.

Known relevant areas include:

### Audio

Existing Python/Pygame playback code already demonstrates:

* music playback;
* playlist handling;
* next/previous navigation;
* volume control;
* MP3/OGG playback;
* MOD/XM/S3M/IT playback.

### Visualization

Existing visual work includes:

* starfields;
* particles;
* geometric transformations;
* pseudo-3D/wireframe rendering;
* spectrum-related behavior;
* beat-reactive effects.

This code is considered a **donor implementation**, not ToroidAMP architecture.

No existing component is automatically accepted unchanged.

---

## 8. Current Architectural Direction

Current conceptual flow:

```text id="zz1gt8"
Audio File
    │
    ▼
Playback / Decoder
    │
    ▼
PCM
    │
    ├──────────────► Audio Output
    │
    ▼
Audio Analysis
    │
    ▼
Normalized AudioFrame
    │
    ▼
Visualizer
    │
    ▼
Embedded / Fullscreen Render
```

UI, playlist, session persistence, and platform integration surround this pipeline without owning its internal responsibilities.

---

## 9. Provisional Decisions

The following directions are promising but are **not yet closed architectural decisions**:

### UI

**PySide6 / Qt**

Current leading candidate for the desktop interface.

Needs validation with:

* visualization embedding;
* fullscreen;
* system tray;
* Windows packaging;
* Linux packaging.

### Existing Rendering

**Pygame**

Existing visualizers are Pygame-based.

Pygame may remain part of the visualization implementation if integration with the production UI proves practical.

This must be tested rather than assumed.

### Tracker Playback

Existing Pygame playback already demonstrates tracker-module support.

A dedicated solution such as `libopenmpt` may provide better control and PCM access.

No final decision has been made.

---

## 10. Open Decision Gates

The following decisions currently block or influence implementation architecture.

## 10. Established & Closed Decision Gates

### AUDIO-001 — Conventional Playback Backend
* **Decision**: `sounddevice` + `soundfile` / `miniaudio` streaming output callback.
* **Status:** CLOSED (Validated with WAV, MP3, OGG, FLAC).

### AUDIO-002 — Tracker Module Decoder Engine
* **Decision**: Native `libxmp` ctypes decoder rendering tracker files to normalized float32 PCM. RC-069-002B (see `docs/release/RC_069_002B_tracker_libxmp.md`): the originally-planned `libmodplug` backend was found to have never actually been available anywhere in this project's toolchain and was replaced with `libxmp`, which pygame-ce (an existing required dependency) already bundles as a real, present Windows DLL.
* **Status:** CLOSED (Validated with real MOD, XM, IT files; S3M architecturally supported by libxmp but untested — no real S3M fixture was available).

### AUDIO-003 — PCM Access & Analysis Handoff
* **Decision**: Thread-safe circular snapshot buffer (`AnalysisHandoff`) isolating audio callback from UI/analysis.
* **Status:** CLOSED (~17us push overhead, ~0.8us snapshot overhead).

### ANALYSIS-001 — AudioFrame Contract
* **Decision**: Normalized `AudioFrame` (`rms`, `peak`, `bass`, `mids`, `treble`, `spectrum`, `waveform`, `beat`, `strong_beat`).
* **Status:** CLOSED (Report in `02_audio_pipeline_tracker_pcm.md`).

### ANALYSIS-002 — Beat Detection
* **Decision**: Dynamic sliding-window energy variance detector with bass transient thresholding.
* **Status:** CLOSED (Transient-reactive, explicit BPM excluded from V1).

### VIS-001 — Existing Visualizer Audit
* **Decision**: Extract `Starfield`, `Toroid 3D` (`GeometricTransformer3D`), `RetroGrid`, and adapt `SpectrumAnalyzer`.
* **Status:** CLOSED (Report in `01_technical_reconnaissance.md`).

### VIS-002 — Rendering Integration
* **Decision**: Pygame offscreen surface transfer to PySide6 `QImage` / `QPixmap`.
* **Status:** CLOSED (~1.27ms transfer overhead at 800x600).

### UI-001 — PySide6 Validation
* **Decision**: PySide6 confirmed as desktop GUI framework.
* **Status:** CLOSED.

### RUNTIME-001 — Concurrency / Scheduling
* **Decision**: High-priority audio callback decoupled from UI render loop via thread-safe PCM snapshotting.
* **Status:** CLOSED.

### PACKAGE-001 — Distribution
* **Decision**: PyInstaller / Nuitka desktop packaging.
* **Status:** DEFERRED.

---

## 11. Current Risks

### Cross-Platform Library Loading
`libxmp` and PortAudio must be resolved reliably on both Windows and Linux via automatic wheel fallback or `ctypes.util.find_library`.

---

## 12. Current Work

**Production Cut 2 — Desktop Lifecycle & Session Persistence**
STATUS: CLOSED

Implemented production desktop lifecycle:
* System tray presence (`ToroidTrayIcon`) with quick transport and status.
* Clear close-to-tray vs. explicit shutdown semantics.
* Atomic JSON session persistence (`SessionManager`) at standard OS config paths.
* Safe playback startup policy (restores queue, index, volume without surprise autoplay).
* Off-screen screen geometry clamping and recovery.
* Zero-overhead visualizer suspension when hidden to tray.

---

## 13. Next Cut

### Production Cut 3 — Visualizer Expansion & Demoscene Effects
STATUS: ACTIVE

Completed promotion & polish:
* **VIS-001**: Deep Field & ToroidAMP Floor promoted to production. (CLOSED)
* **VIS-002**: Production Visual Polish, RETINA Controls & Jack Final Perceptual Tuning. (CLOSED)
* **EXP-GL-001**: GPU Visualizer Foundation Probe. (CLOSED - GO)
* **EXP-VISLAB-001**: GPU Visualizer Authoring Lab Foundation. (CLOSED - GO)
* **EXP-VISLAB-002**: Real-World External GLSL Compatibility Gate. (CLOSED - PASS)
* **GPU-OFFICIAL-001**: First Official GPU Visualizer — Toroid Identity. (CLOSED - PASS)
* **GPU-PROD-001**: RETINA MELT GPU Host Integration + Live Tune Controls. (CLOSED - PASS)
* **EXP-VISLAB-003**: GPU Visualizer Authoring Lab Foundation II (Controls + Presets). (CLOSED - PASS)
* **GPU-PROD-002**: RETINA MELT Integrated Shader Lab (Real-Audio GPU Authoring Surface). (IMPLEMENTED — FINAL HUMAN MICRO-GATE PENDING)
  - Full authoring surface integrated directly into RETINA MELT via `[ ⚗ LAB ]` HUD button and `L` shortcut.
  - Three distinct interaction depths: HUD (listening), TUNE (adjusting), LAB (authoring).
  - Strict mutual exclusivity: `TUNE XOR LAB` with unified underlying parameter model.
  - Scoped dark cyberpunk stylesheet for `QColorDialog` (`_open_styled_color_dialog`), guaranteeing high-contrast cyan/amber text on dark slate backgrounds without affecting native dialogs.
  - Authoritative visualizer switch contract: navigating away via `MODE` button or `M` shortcut immediately dismisses the visualizer-specific `LAB` workbench (and stale `TUNE` panels).
  - Local Level-1 GLSL shader loading from `user_shaders/` with clear `MODE: LOCAL — <NAME>` provenance.
  - Full Foundation II typed parameter rack (float sliders, bool toggles, color pickers) and preset save/load.
  - Hot reload (`R`) keeps active workbench open and isolates compile failures without interrupting music playback.
  - Official visualizer registration expanded: Toroid Identity + Cyber Bloom.
  - Session persistence boundary: official visualizer parameters persist across restarts; local shaders remain temporary non-destructive overrides.
* **GLSL-EVERYWHERE**: Official NORMAL Integration & Linux RETINA Stabilization. (IMPLEMENTED — Windows-validated; Linux manual validation pending)
  - Official GPU visualizers (Toroid Identity, Cyber Bloom, Audio Reactive Reference) now render directly in NORMAL mode on the same production `GLVisualizerCanvas` RETINA MELT and the Lab use — no second GLSL renderer, no placeholder. Arbitrary user shaders remain excluded from NORMAL (RETINA MELT + Lab only).
  - Root-caused and fixed the Linux RETINA MELT user-shader black-output bug: `_load_local_shader_dialog` loaded before showing the GPU canvas, hitting `load_shader_file()`'s deferred-compile branch on platforms where a hidden `QOpenGLWidget` isn't realized yet; reordered to match the already-correct official-visualizer path.
  - Production startup now requests an explicit OpenGL 3.3 Core Profile surface format, closing a divergence from the Lab's own entry point.
  - Documented the shared production shader contract (Lab/RETINA/NORMAL all compile through the same `classify_and_wrap_source()` + `GLVisualizerCanvas.load_shader_file()` path) in `docs/visualizers/10_retina_gpu_integration.md`.
* **LINUX-AUDIO-001**: Linux Audio Reliability & HP Baseline Validation. (CLOSED — bare-metal-validated on Ubuntu/HP: `device=pipewire`, `negotiated_blocksize=0`, clean music playback, official GLSL visualizers working. Linux TTS remains broken, tracked separately.)
  - Root-caused Linux bare-metal playback stuttering to a fixed 512-frame `blocksize` plus reliance on PortAudio's ALSA `default` device, which routes through an extra userspace buffering chain sitting below PipeWire's own graph (invisible to `pw-top`'s XRUN accounting). Now negotiates blocksize (`blocksize=0`) and prefers a device named `pipewire` when present, via a capability check (`sounddevice.query_devices()` by name) — no HP-specific device IDs, no distro branching.
  - Also vectorized the real-time audio callback's fade-envelope computation, removing a per-sample Python loop that ran even when the envelope was constant.
  - Root-caused and fixed the Linux TTS startup-voice failure (`ReferenceError: weakly-referenced object no longer exists` from a pyttsx3/eSpeak ctypes callback): the synthesis engine was explicitly deleted immediately after `runAndWait()`, racing a trailing native callback. Now kept alive for its natural lifetime. (Note: a *separate*, still-open Linux TTS audibility issue was found during PLAYBACK-STATE-001's HP validation — WAV synthesizes but isn't heard on Ubuntu/Wayland; tracked as a future item, not yet root-caused.)
* **PLAYBACK-STATE-001**: Playback State & Interaction Stabilization. (CLOSED — bare-metal-validated on both Windows and Ubuntu: STOP semantics correct, timeline/seek responsive and correct, official GLSL visualizers functional.)
  - Root-caused the Windows STOP-auto-advance bug: a fade-out stop completes asynchronously in the audio callback by setting the same `STOPPED` state natural end-of-track uses; the playlist auto-advance check couldn't tell them apart. Added an explicit one-shot natural-EOF flag (`PlayerEngine.consume_natural_eof()`) that only genuine decoder exhaustion sets — STOP/pause/seek never do.
  - Root-caused seek-near-EOF spurious advance and Ubuntu timeline sluggishness/audio interruption to the same underlying defect: `seek()` called the decoder synchronously from the UI thread, racing the audio callback's unsynchronized `read_frames()` on the same decoder handle. Seeking while PLAYING now defers to the audio callback (the decoder's sole owner while active), naturally coalescing rapid drags.
  - Fixed the MINI volume popup's speaker-button toggle: Qt's own popup auto-dismiss (any outside click, including the toggle button's own second click) fires before the button's click handler runs, so the handler always saw "already hidden" and reopened it. Fixed with a short debounce.
* **UBUNTU-WAYLAND-001**: Ubuntu / Wayland Integration & Lifecycle Stabilization. (IMPLEMENTED — Windows-validated; Ubuntu re-validation pending)
  - Root-caused Linux TTS audible silence (distinct from the earlier eSpeak weakref crash, already fixed): `pygame.init()` elsewhere (CPU visualizer support) silently pre-initializes `pygame.mixer` with unknown defaults before the voice line ever plays, so VoiceService's own conditional mixer setup never actually applied. Now reconfigures the mixer explicitly every time.
  - Root-caused Wayland frameless-drag failure: the existing drag implementation used absolute global-position `move()`, which Wayland's compositor security model doesn't permit. Now uses `QWindow.startSystemMove()` on Wayland specifically; X11/Windows keep the existing move()-based drag with MINI edge-snapping intact.
  - Declared `QApplication.setDesktopFileName("toroidamp")` for portable desktop-identity association; documented (not faked) that a GNOME/Wayland-style dock icon still requires a packaged, installed `.desktop` file — out of this cut's scope.
  - Root-caused and fixed a `QOpenGLTexturePrivate::destroy() called without a current context` shutdown warning: both `GLVisualizerCanvas` instances are child widgets, so closing their parent windows never delivered `closeEvent()` (and its GPU cleanup) to them. `WindowManager.shutdown()` now releases both canvases' GPU resources explicitly and deterministically while their contexts are still current.
  - Startup busy-cursor report: audited, no cursor-override code found anywhere in the codebase and no obvious startup-blocking cause identified; not reproducible without physical Ubuntu access this session. Classified NOT_REPRODUCED / ENVIRONMENT_LIMITATION, left untouched.
* **UBUNTU-WAYLAND-002**: Desktop Composition & Dialog Reliability. (IMPLEMENTED — Windows-validated; Ubuntu manual re-validation pending)
  - Root-caused intermittent (works-then-silent-across-relaunches) startup TTS: nothing previously called `pygame.mixer.quit()`, so the mixer's PipeWire connection was only ever released implicitly on abrupt process exit — a fast relaunch could initialize against a not-yet-reclaimed connection. Now explicitly quits the mixer once each announcement is done with it; the mixer init/play/quit cycle is also serialized process-wide (a module-level lock), and logging no longer claims success when a channel reports idle immediately after `play()`.
  - Root-caused Playlist/Visualizer centering on Wayland (instead of docking right-of/below NORMAL): both are `Qt.Window` toplevel surfaces, and the base Wayland/xdg-shell protocol has no request for a client to set a toplevel's absolute position — only interactive move (drag), already used via `startSystemMove()`. The existing docking math (`realign_docked_modules()`) was already correct and needed no change; this is a genuine, undocumented-until-now protocol limitation with no portable Qt-level fix, so it's documented in place rather than worked around.
  - Fixed the GLSL Lab's LOAD dialog appearing behind the Lab window on Wayland: forces Qt's own non-native file dialog specifically on Wayland (all three Lab file dialogs), avoiding a dependency on the `org.freedesktop.portal.FileChooser` DBus service whose parent-window handoff isn't reliably wired up in this environment. Windows and Linux/X11 keep the native dialog.
  - Portal app-ID registration warning and file-dialog navigation slowness: not independently reproducible outside a real Wayland compositor (this cut's work was done on Windows). Classified DESKTOP_INTEGRATION / PENDING_MANUAL_VALIDATION — the Lab dialog fix above removes the portal round-trip for Lab file dialogs specifically, which should also address the observed slowness there, but this needs confirmation on real Ubuntu hardware. `setDesktopFileName("toroidamp")` was left untouched.
  - A native Windows crash (`comtypes` COM cross-thread garbage-collection access violation) surfaced while testing the TTS fix, traced to a pre-existing test-hygiene gap: `tests/test_fix_001.py::test_voice_service_isolation` fired a real, unmocked TTS engine on a background thread and never joined it, letting that thread's COM object's lifetime spill into later, unrelated tests in the same process. Fixed by joining the thread before the test returns; no production code was implicated.
* **RELEASE-BLOCKERS-001**: Ubuntu TTS, User GLSL & Wayland Unified Chassis. (CLOSED — physically validated on Ubuntu/Intel/Wayland + Windows)
  - **LINUX-GLSL-001**: Intel/Mesa User Shader Black-Render Fix (CLOSED — normalized uninitialized local variables and Shadertoy inout vec4 parameters).
  - **LINUX-DIALOG-001**: Canonical Non-Native Dialog Options on Wayland (CLOSED — unified platform_file_dialog_options() across all 9 dialog call sites).
  - **LINUX-CHASSIS-001**: Wayland Unified Chassis Auxiliary Module Resize & Layout Stabilization (CLOSED — interactive edge-resizing on embedded modules with zero geometry drift across transitions).
  - **LINUX-TTS-001**: Startup Voice Identity Announcement on Linux (CLOSED — DEFERRED_ON_LINUX). Native TTS via pyttsx3/eSpeak on Linux operates asynchronously in C/ctypes without synchronizing WAV file generation before event pump termination, resulting in intermittent silence and native ctypes lifecycle races. Automatic startup voice is cleanly deferred on Linux for v0.667 while remaining fully enabled and supported on Windows (SAPI5). Core synthesis and manual VoiceService APIs remain available.

---

## 14. Documentation Lifecycle

At the end of every significant development cut:
1. Evaluate whether operational project state changed;
2. Update `CURRENT_STATE.md` only when necessary;
3. Move completed historical context to `ARCHIVE.md` when it no longer belongs here;
4. Update `ARCHITECTURE.md` when architectural truth changes;
5. Update `SCOPE.md` only through explicit scope decisions.

---

## 15. Current Snapshot

```text
TOROIDAMP

Foundation 0 — Project Definition               CLOSED
Foundation I — Technical Reconnaissance           CLOSED
Foundation II — Audio & Tracker Prototype         CLOSED
Production Cut 1A — Core Extraction & Skills      CLOSED
UI Direction Gate D.1 — Mini & Experience Scale   CLOSED
Production Cut 1B — Primary Player Implementation CLOSED
Production Cut 2 — Desktop Lifecycle & Session    CLOSED
FIX-001 — Startup Lifecycle & Voice Identity      CLOSED
Production Cut 3 — Visualizer Expansion           CLOSED
  - VIS-001: Deep Field & Floor Promotion         CLOSED
  - VIS-002: Production Visual Polish & RETINA    CLOSED
v0.666 — NORMAL UX & Interaction Polish           CLOSED
RELEASE-BLOCKERS-001 — Linux Stabilization Gate    CLOSED
  - LINUX-GLSL-001: Intel/Mesa Shader Fix         CLOSED
  - LINUX-DIALOG-001: Wayland Non-Native Dialogs  CLOSED
  - LINUX-CHASSIS-001: Wayland Module Resizing    CLOSED
  - LINUX-TTS-001: Linux Startup Voice Deferral   CLOSED (DEFERRED_ON_LINUX)
RELEASE-POLISH-0.667 — Presentation & Readiness   CLOSED
RELEASE-GATE-0.667 — Release Artifact Validation   CLOSED
  - RELEASE-GATE-0.667-LINUX: Native Linux ONEDIR PASS
  - RELEASE-GATE-0.667-WINDOWS: Native Windows ONEDIR PASS
RELEASE-CLOSEOUT-0.667 — Final Assembly & Publication   CLOSED
  - Windows archive/checksum: STAGED
  - Linux archive/checksum: STAGED
  - v0.667: READY_FOR_PUBLICATION
Visualizer Roster Expansion, UX-005, DSP-001 (v0.669)   CLOSED
RELEASE-GATE-0.669-WINDOWS — Native Windows ONEDIR      PASS
  - Windows archive/checksum: STAGED (release/0.669/)
  - Linux: DEFERRED (remains at v0.667)
  - v0.669: READY_FOR_PUBLICATION (Windows only)

Next: Metal reviews the RELEASE-GATE-0.669-WINDOWS report, commits pending fixes/docs, tags v0.669, publishes the GitHub Release.
```






