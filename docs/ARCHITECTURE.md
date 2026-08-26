# ToroidAMP — Architecture

> **Architecture should enable experimentation without turning the player into the experiment.**

## 1. Purpose

This document describes the **current architectural truth** of ToroidAMP.

It records established system boundaries, responsibilities, constraints, and technical decisions that remain relevant to the implementation.

It is not a development diary.

Historical decisions, completed cuts, rejected experiments, and superseded approaches belong in `ARCHIVE.md`.

Operational work, active questions, blockers, and the immediate next cut belong in `CURRENT_STATE.md`.

This document should only state a technical choice as established when that choice has actually been made.

Unresolved architectural questions are explicitly marked **OPEN**.

---

## 2. Architectural Goals

ToroidAMP should remain:

* small enough to understand;
* modular enough to extend;
* portable between Windows and Linux;
* lightweight during normal playback;
* capable of rich real-time visualization;
* usable without external services;
* friendly to open-source contribution.

The architecture should prioritize clear subsystem boundaries over speculative abstraction.

ToroidAMP should not introduce infrastructure merely because a larger media player might eventually need it.

---

## 3. Technology Baseline

### Language

**Python**

Python is the primary implementation language for ToroidAMP.

Reasons include:

* rapid iteration;
* existing reusable MetalWar-Installer code;
* mature desktop and audio ecosystem;
* Windows and Linux support;
* low contribution barrier;
* suitability for experimental visualization work.

Native libraries may be used behind Python bindings where technically justified.

### Target Platforms

**Windows and Linux**

The application should share the same core codebase across both platforms.

Platform-specific behavior must be isolated rather than distributed throughout the application.

---

## 4. High-Level Architecture

ToroidAMP is organized conceptually around the following major subsystems:

```text
┌───────────────────────────────────────────────┐
│                    UI                         │
│                                               │
│ Player / Playlist / Visualizer / Settings    │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│              Application Layer                │
│                                               │
│ Playback coordination / Session / Commands   │
└─────────────┬─────────────────┬───────────────┘
              │                 │
              ▼                 ▼
┌─────────────────────┐  ┌─────────────────────┐
│   Playback System   │  │   Playlist System   │
└──────────┬──────────┘  └─────────────────────┘
           │
           ▼
┌─────────────────────┐
│   Audio Analysis    │
│                     │
│ PCM / FFT / Levels  │
│ Bands / Beat Data   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Visualization System│
└─────────────────────┘


Additional boundaries:

┌─────────────────────┐
│   Settings/Session  │
└─────────────────────┘

┌─────────────────────┐
│ Platform Integration│
│ Windows / Linux     │
└─────────────────────┘
```

These represent responsibilities rather than mandatory Python class hierarchies.

---

## 5. Core Dependency Principle

The central dependency direction is:

```text
Audio Source
     │
     ▼
Playback
     │
     ▼
Audio Analysis
     │
     ▼
Normalized Audio Data
     │
     ▼
Visualizer
```

The visualizer must not control playback.

The playback system must not contain visualizer-specific behavior.

The UI coordinates user interaction but should not become the owner of audio decoding or analysis logic.

This separation is fundamental to ToroidAMP.

---

## 6. Playback System

The Playback System is responsible for music reproduction.

Its responsibilities include:

* loading supported files;
* starting playback;
* pausing;
* stopping;
* seeking where supported;
* reporting playback state;
* reporting playback position;
* reporting duration where available;
* controlling playback volume;
* detecting track completion;
* exposing the audio information required by the analysis layer.

The Playback System should hide backend-specific implementation details from the rest of the application.

Conceptually:

```text
Application
     │
     ▼
Playback API
     │
     ▼
Audio Backend
```

The application should not need to know whether a track is being decoded through one library or another.

### Playback Backend

**Status: OPEN**

MetalWar-Installer currently demonstrates working playback through Pygame, including conventional audio and tracker modules.

This existing implementation is evidence and a useful prototype, but it does not automatically define ToroidAMP's final backend.

The selected backend must be evaluated against:

* Windows support;
* Linux support;
* MP3/WAV/OGG/FLAC support;
* MOD/XM/S3M/IT support;
* seeking;
* playback-position reporting;
* reliable PCM access;
* suitability for real-time visualization;
* packaging complexity;
* licensing;
* maintenance status.

PCM/audio-analysis access is particularly important because visualization is a core ToroidAMP requirement.

---

## 7. Decoder Strategy

ToroidAMP should allow format-specific decoding details to remain behind the Playback System.

A likely conceptual boundary is:

```text
                Playback
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
 Conventional Audio      Tracker Modules
 MP3/OGG/WAV/FLAC        MOD/XM/S3M/IT
        │                     │
        └──────────┬──────────┘
                   ▼
                  PCM
```

Whether this requires multiple decoder implementations or can be provided cleanly by a single backend remains:

**Status: OPEN**

Tracker-specific libraries such as `libopenmpt` are candidates, not yet architectural commitments.

---

## 8. Audio Analysis

Audio Analysis transforms playback audio into normalized information useful to visualizers.

Visualizers should not independently perform their own decoding or inspect backend internals.

The analysis system may expose information such as:

```text
AudioFrame
├── waveform
├── rms
├── peak
├── spectrum
├── bass
├── mids
├── treble
├── beat
└── strong_beat
```

This structure is conceptual.

Its final representation and exact fields remain:

**Status: OPEN**

### Analysis Principle

The analysis layer owns signal interpretation.

The visualizer owns visual interpretation.

For example:

```text
Analysis:
"bass = 0.82"

Visualizer:
"make toroid angry"
```

The visualizer should not need to know how `0.82` was calculated.

---

## 9. Visualization System

Visualization is a first-class ToroidAMP subsystem.

A visualizer should receive:

* a render target or rendering context;
* normalized audio-analysis data;
* timing information;
* its own configuration/state where necessary.

Conceptually:

```python
class Visualizer:
    def start(self):
        ...

    def update(self, audio_frame, delta_time):
        ...

    def render(self, target):
        ...

    def stop(self):
        ...
```

This is **illustrative only** and is not yet the final public API.

### Visualizer Isolation

A visualizer must not:

* load or decode the currently playing file;
* control the playlist;
* change playback state;
* depend directly on a specific audio backend;
* require knowledge of the main UI implementation.

A broken visualizer should ideally fail without terminating playback.

---

## 10. Existing Visualizer Reuse

MetalWar-Installer contains existing Pygame-based visual work including:

* audio-reactive starfields;
* geometric transformations;
* particles;
* pseudo-3D/wireframe effects;
* spectrum-related behavior;
* beat-reactive effects.

This code should be treated as **source material for extraction**.

The migration process should be:

```text
Existing Effect
      │
      ▼
Identify dependencies
      │
      ▼
Remove Installer-specific coupling
      │
      ▼
Adapt to ToroidAMP audio data
      │
      ▼
ToroidAMP Visualizer
```

Existing code should not be rewritten merely to satisfy aesthetic architectural preferences.

Likewise, it should not be copied wholesale if doing so imports unrelated Installer responsibilities.

---

## 11. Visualization Rendering Technology

Existing visualizers use Pygame rendering.

The intended desktop UI is expected to use a richer desktop GUI toolkit.

How these systems will coexist is an important architectural decision.

Potential approaches include:

* embedding or transferring a Pygame-rendered surface into the UI;
* using Pygame only for visualization while another toolkit owns the application window;
* porting selected visualizers to another rendering system;
* using an OpenGL-capable rendering surface;
* adopting another rendering strategy if testing demonstrates a clear advantage.

**Status: OPEN**

This decision should be made through a small technical experiment rather than speculation.

---

## 12. User Interface

ToroidAMP requires a desktop GUI suitable for:

* compact layouts;
* playlist interaction;
* dialogs;
* drag and drop;
* system tray integration;
* fullscreen visualization;
* Windows and Linux support.

### UI Toolkit

**PySide6 / Qt is the current leading candidate.**

**Status: PROVISIONAL**

It should be validated against:

* integration with the chosen visualization renderer;
* system tray behavior;
* packaging;
* Linux behavior;
* fullscreen rendering;
* licensing requirements.

The UI toolkit does not own the playback architecture.

---

## 13. Playlist System

ToroidAMP uses a current-playlist model.

The Playlist System is responsible for:

* ordered track entries;
* adding tracks;
* removing tracks;
* reordering;
* clearing;
* loading playlists;
* saving playlists;
* current-track selection.

Playlist state should remain independent from the playback backend.

Conceptually:

```text
Playlist
   │
   │ selected path
   ▼
Playback
```

The playlist tells playback **what** should play.

Playback determines **how** it plays.

### Playlist Format

M3U/M3U8 is the preferred initial direction.

**Status: PROVISIONAL**

No proprietary ToroidAMP playlist format should be introduced without a concrete requirement.

---

## 14. Filesystem and Paths

Filesystem operations should use portable Python facilities such as `pathlib` wherever practical.

Application code should not assume:

```text
C:\
```

or any other operating-system-specific root/path syntax.

Platform-specific application-data locations belong to the Platform Integration layer.

Music files themselves remain external user resources.

ToroidAMP should not copy user music into application-managed storage merely to reproduce it.

---

## 15. Settings and Session State

ToroidAMP requires lightweight persistence for user preferences and session restoration.

Expected state includes:

* volume;
* current/last playlist;
* current track;
* playback position where supported;
* shuffle/repeat state;
* selected visualizer;
* visualizer preferences;
* window geometry;
* tray behavior.

### Persistence Technology

The initial preferred approach is:

**JSON or equivalent lightweight structured configuration.**

No database is currently required.

A database should only be introduced if future requirements demonstrate a concrete need for indexed persistent data that simpler storage cannot reasonably provide.

---

## 16. Platform Integration

Operating-system-specific behavior should live behind an explicit platform boundary.

Conceptually:

```text
PlatformService
├── WindowsPlatform
└── LinuxPlatform
```

Potential responsibilities include:

* system tray integration;
* OS application-data paths;
* media keys;
* desktop notifications;
* native media-session integration;
* startup behavior;
* file associations.

Not all platform features need to be implemented immediately.

The important architectural constraint is that OS-specific code does not spread through unrelated subsystems.

---

## 17. Background Behavior

Playback must be independent from main-window visibility.

Conceptually:

```text
Main Window
     │
     ├── visible
     ├── minimized
     └── hidden in tray

Playback
     │
     └── continues
```

Visualization may reduce or stop rendering while not visible.

Audio playback must not depend on visualization frame rate.

---

## 18. Concurrency and Timing

Audio playback, analysis, visualization, and UI updates operate at different timing requirements.

ToroidAMP should avoid coupling them through one uncontrolled application loop.

Potential mechanisms include:

* backend-managed audio threads;
* UI timers;
* worker threads;
* bounded audio-analysis buffers.

The exact concurrency model remains:

**Status: OPEN**

The design should prioritize:

* uninterrupted playback;
* responsive UI;
* bounded memory use;
* visualization that may drop frames without affecting audio.

Audio correctness has priority over visualizer frame delivery.

---

## 19. Failure Isolation

ToroidAMP should degrade gracefully.

Examples:

```text
Visualizer failure
→ playback continues

Metadata failure
→ display filename

Unsupported file
→ report error and continue

Missing optional integration
→ player remains usable
```

Optional features should not unnecessarily become startup requirements.

---

## 20. Extensibility

ToroidAMP is intended to be contributor-friendly.

However:

**V1 does not require a formal plugin framework.**

Instead, V1 should establish clean internal contracts through actual implementation.

Particularly important extension boundaries are expected to be:

```text
Visualizer
Audio Decoder
Platform Integration
```

If these boundaries prove stable through internal use, they may later become public extension APIs.

No dynamic plugin loader should be created solely in anticipation of possible contributors.

---

## 21. Proposed Source Organization

The exact package structure may evolve, but the current conceptual organization is:

```text
src/
└── toroidamp/
    ├── app.py
    │
    ├── playback/
    │   ├── player.py
    │   └── backends/
    │
    ├── analysis/
    │   ├── audio_frame.py
    │   ├── spectrum.py
    │   └── beat.py
    │
    ├── playlist/
    │   ├── playlist.py
    │   └── m3u.py
    │
    ├── visualizers/
    │   ├── base.py
    │   ├── starfield.py
    │   ├── geometric.py
    │   └── ...
    │
    ├── ui/
    │   ├── main_window.py
    │   ├── playlist_view.py
    │   └── visualizer_view.py
    │
    ├── platform/
    │   ├── base.py
    │   ├── windows.py
    │   └── linux.py
    │
    └── settings/
        └── settings.py
```

This structure is **provisional**.

Directories should only be introduced when implementation requires them.

---

## 22. Dependency Policy

Every external dependency should have a concrete responsibility.

Before adopting a dependency, evaluate:

* platform support;
* license compatibility;
* project maintenance;
* binary/package size;
* packaging complexity;
* API stability;
* whether the dependency solves a real ToroidAMP requirement.

Dependencies should not be avoided dogmatically.

They should also not accumulate casually.

---

## 23. Architectural Decisions Status

### Established & Closed Decisions (Foundation I & II Evidence)

* **AUDIO-001 — Conventional Playback Backend**: **CLOSED -> `sounddevice` + `soundfile`/`miniaudio` stream callback**. Delivers continuous float32 PCM blocks with zero audio thread latency.
* **AUDIO-002 — Tracker Decoder Engine**: **CLOSED -> Native `libmodplug` ctypes Decoder (CONFIRMED)**; `libopenmpt` remains a PROVISIONAL / ALTERNATIVE engine. Decodes MOD, XM, IT, S3M directly into the normalized float32 PCM pipeline.
* **AUDIO-003 — PCM Access & Analysis Handoff**: **CLOSED -> Circular Snapshot Buffer (`AnalysisHandoff`)**. Ultra-fast thread decoupling (~17us push, ~0.8us snapshot).
* **ANALYSIS-001 — AudioFrame Contract**: **CLOSED -> Normalized `AudioFrame`**. Exposes `rms`, `peak`, `bass`, `mids`, `treble`, `spectrum` (64 log bins), `waveform` (128 points), `beat`, and `strong_beat`.
* **ANALYSIS-002 — Beat Detection**: **CLOSED -> Dynamic Energy Variance Transient Detector**. Fast, robust thresholding; explicit BPM excluded from V1.
* **VIS-001 — Rendering Strategy**: **CLOSED -> Offscreen Pygame -> PySide6 QImage/QPixmap Transfer**. Sub-2ms transfer overhead, supporting windowed and fullscreen display.
* **UI-001 — Desktop Toolkit**: **CLOSED -> PySide6**.
* **RUNTIME-001 — Concurrency Model**: **CLOSED -> Isolated audio callback + UI timer analysis consumer**. Audio output never waits on UI or visualizer rendering.

### Deferred Decisions

* **PACKAGE-001 — Distribution Strategy (DEFERRED)**: PyInstaller / Nuitka desktop packaging.



---

## 24. Architectural Non-Goals

ToroidAMP architecture should not currently optimize for:

* distributed systems;
* cloud services;
* remote playback;
* multi-user state;
* large indexed libraries;
* database-backed domain models;
* arbitrary scripting;
* enterprise plugin ecosystems;
* network synchronization.

If future scope changes, architecture can evolve in response.

---

## 25. Architecture Update Rule

`ARCHITECTURE.md` contains **current truth**, not accumulated history.

When an architectural decision changes:

1. update this document to describe the new architecture;
2. remove or replace superseded architectural truth;
3. record historically relevant context in `ARCHIVE.md`;
4. update `CURRENT_STATE.md` only if the change affects active operational state.

Architecture should therefore remain readable without requiring the reader to reconstruct which paragraphs are obsolete.

---

## 26. Prime Constraint

ToroidAMP exists both as a useful music player and as a safe environment for visual experimentation.

Therefore:

> **Playback must remain boring enough to be reliable.
> Visualization may be as ridiculous as necessary.**

And if the architecture cannot accommodate an audio-reactive toroid without compromising playback, the architecture should be reconsidered.
