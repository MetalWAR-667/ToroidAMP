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
**Stage:** Core Implementation & Desktop Lifecycle
**Current Phase:** FIX-001 — Startup, Lifecycle & Voice Identity
**Status:** CLOSED (Next: Production Cut 3 — Visualizer Expansion & Effects)
**Implementation:** PRODUCTION APPLICATION WITH REFINED LIFECYCLE & VOICE (`toroidamp`)

ToroidAMP lifecycle semantics are now strictly separated: MINI (visible compact scale), MINIMIZE (hide to tray with active audio), and CLOSE/X (immediate full shutdown).
On startup, ToroidAMP initializes with no loaded music track, sanitizes its restored playlist against the filesystem, and announces its identity motto via VoiceService.








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
Production Cut 3 — Visualizer Expansion           ACTIVE
  - VIS-001: Deep Field & Floor Promotion         CLOSED
  - VIS-002: Production Visual Polish & RETINA    CLOSED
v0.666 — NORMAL UX & Interaction Polish           CLOSED
  (bounded side-cut: consoleless packaged build, breathing border,
   volume-independent reactivity, playlist multi-select, Linux taskbar
   grouping, version single-source-of-truth; not visualizer/RETINA work)

Next: return to Production Cut 3 — GPU-PROD-002 final human micro-gate.
```






