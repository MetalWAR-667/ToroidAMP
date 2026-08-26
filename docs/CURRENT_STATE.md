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
**Stage:** Foundation
**Current Phase:** Foundation 0 — Project Definition
**Status:** ACTIVE
**Implementation:** NOT STARTED

ToroidAMP is currently being defined before the first implementation cut.

No production code has yet been created in the ToroidAMP repository.

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

### AUDIO-001 — Playback Backend

Determine the production playback backend.

Required evaluation:

* common audio formats;
* tracker modules;
* Windows/Linux;
* seek;
* playback position;
* PCM access;
* packaging;
* licensing.

**Status:** OPEN

### AUDIO-002 — PCM / Analysis Path

Determine how ToroidAMP obtains reliable real-time audio data for visualization.

**Status:** OPEN

### ANALYSIS-001 — Visualizer Audio Contract

Define the minimum normalized data passed to visualizers.

Potential fields:

```text id="onr94a"
waveform
rms
peak
spectrum
bass
mids
treble
beat
strong_beat
```

**Status:** OPEN

### VIS-001 — Existing Visualizer Audit

Inventory the reusable visualization code in MetalWar-Installer.

Determine:

* available visualizers;
* dependencies;
* Installer-specific coupling;
* audio inputs;
* rendering assumptions;
* extraction difficulty;
* reuse priority.

**Status:** OPEN

### VIS-002 — Rendering Integration

Determine how the visualization renderer integrates with the desktop UI.

**Status:** OPEN

### UI-001 — PySide6 Validation

Confirm or reject PySide6 as ToroidAMP's production desktop toolkit.

**Status:** OPEN

### RUNTIME-001 — Scheduling

Determine the minimum concurrency/timing model required to prevent visualization or UI work from affecting playback.

**Status:** OPEN

### PACKAGE-001 — Distribution

Determine packaging strategy for Windows and Linux.

This does not currently block early development.

**Status:** DEFERRED

---

## 11. Current Risks

### Visualization / Playback Coupling

The primary technical risk is choosing a playback backend that reproduces supported formats correctly but makes real-time PCM access unnecessarily difficult.

Because visualization is fundamental to ToroidAMP, PCM/analysis access must influence the playback-backend decision.

### Pygame / Qt Integration

Existing visualizers are valuable, but their current Pygame rendering model may not integrate cleanly enough with the chosen desktop toolkit.

This requires a prototype.

### Tracker Support

Existing playback demonstrates tracker compatibility, but production requirements may expose limitations involving:

* seeking;
* metadata;
* PCM extraction;
* consistent behavior across platforms.

### Scope Expansion

ToroidAMP's experimental nature makes visual-feature expansion cheap and attractive.

Core player requirements should be stabilized before optional visual experiments begin dominating development.

---

## 12. Current Work

**ACTIVE: Foundation 0 — Project Definition**

Current objectives:

* establish product identity;
* establish V1 scope;
* establish initial architecture boundaries;
* define documentation lifecycle;
* prepare the repository for first implementation work.

No implementation should begin until Foundation 0 is closed.

---

## 13. Remaining Foundation 0 Work

Foundation 0 currently requires:

* initialize `ARCHIVE.md`;
* create public-facing `README.md`;
* create/select project license;
* create repository;
* establish initial source skeleton only when implementation begins;
* perform initial commit.

After these items are complete:

**Foundation 0 → CLOSED**

---

## 14. Next Cut

### Foundation I — Technical Reconnaissance

The first technical cut should investigate existing assets and close the minimum decisions required before building the player.

Primary work:

```text id="4sgp0b"
MetalWar-Installer
        │
        ├── Audit audio implementation
        │
        └── Audit visualizers
                 │
                 ▼
        Identify reusable assets
                 │
                 ▼
        Playback / PCM experiment
                 │
                 ▼
        UI / Visualizer integration experiment
```

Expected outcomes:

* inventory of reusable visualizers;
* inventory of reusable playback code;
* playback-backend recommendation;
* PCM acquisition strategy;
* initial audio-analysis contract;
* PySide6 decision;
* visualization-rendering decision.

Foundation I should prioritize **small executable probes over production architecture**.

---

## 15. Implementation Gate

Production implementation should begin only after Foundation I has answered at minimum:

```text id="hzzk2r"
How do we play the supported formats?

How do we obtain audio data?

How does a visualizer consume that data?

How do we render it inside the UI?
```

Once those four questions have practical answers, ToroidAMP can proceed to its first implementation slice.

---

## 16. Documentation Lifecycle

At the end of every significant development cut:

1. evaluate whether operational project state changed;
2. update `CURRENT_STATE.md` only when necessary;
3. move completed historical context to `ARCHIVE.md` when it no longer belongs here;
4. update `ARCHITECTURE.md` when architectural truth changes;
5. update `SCOPE.md` only through explicit scope decisions.

If a cut does not materially change operational state:

```text id="vgv1ho"
CURRENT_STATE_UPDATE: NOT_REQUIRED
```

`CURRENT_STATE.md` should never become a chronological development log.

---

## 17. Current Snapshot

```text id="kj5yju"
TOROIDAMP

Foundation 0 — Project Definition
STATUS: ACTIVE

Vision             CLOSED
Scope              CLOSED
Architecture       INITIALIZED
Current State      INITIALIZED
Archive            PENDING
README             PENDING
License            PENDING
Repository         PENDING

Implementation     NOT STARTED

NEXT:
Complete Foundation 0
→ Foundation I — Technical Reconnaissance
```

---

## 18. Current Principle

> **Do not build the player until we know how the toroid gets its data.**
