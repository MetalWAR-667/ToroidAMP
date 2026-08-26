# ToroidAMP

> ### **It really warps the toroid's ass!**

**ToroidAMP** is a lightweight, open-source, cross-platform desktop audio player built in Python, with real-time audio visualization as a first-class feature.

It takes inspiration from the compact music players of the late 1990s and early 2000s: open some files, build a playlist, press Play, and get on with your life.

Except now there are more toroids.

---

## What is ToroidAMP?

ToroidAMP aims to be a small local music player for **Windows and Linux** focused on three things:

**Play music.
Manage a playlist.
Make the music move.**

No accounts.

No cloud.

No streaming platform.

No recommendation algorithm trying to understand your emotional relationship with progressive metal.

Just local files, a compact player, and visualizers with questionable amounts of geometry.

---

## Planned V1

The first usable version of ToroidAMP targets:

### Playback

* Play / Pause / Stop
* Previous / Next
* Seek
* Volume
* Shuffle
* Repeat
* Automatic playlist progression

### Playlist

* Add and remove tracks
* Reorder tracks
* Drag and drop
* Load playlists
* Save playlists
* M3U/M3U8 support

### Visualization

* Real-time audio-reactive visualizers
* Visualizer embedded in the player
* Fullscreen visualization
* Multiple selectable visualizers
* Visualization that can be disabled when not needed

### Desktop

* Compact interface
* Windows support
* Linux support
* System tray
* Background playback
* Session restoration

---

## Audio Formats

ToroidAMP V1 intends to support common audio formats:

```text
WAV
MP3
OGG / Vorbis
FLAC
```

And because apparently we have standards:

```text
MOD
XM
S3M
IT
```

Classic tracker modules are not an afterthought.

They are part of the plan.

---

## Visualizers

Visualization is not intended to be a decorative feature bolted onto ToroidAMP after playback works.

It is one of the reasons the project exists.

Existing experimental work already includes concepts such as:

* spectrum visualization;
* starfields;
* particles;
* wireframe geometry;
* pseudo-3D transformations;
* beat-reactive effects;
* assorted geometric irresponsibility.

The project will initially reuse and adapt proven visual experiments from **MetalWar-Installer** where appropriate.

Longer term, visualizers should operate behind a small, understandable internal contract so contributors can experiment without needing to understand the entire player.

The ideal contributor workflow is approximately:

```text
I have a terrible visual idea.
          ↓
Create visualizer.
          ↓
Feed it audio data.
          ↓
Why is there a rotating toroid?
          ↓
Merge.
```

---

## Philosophy

ToroidAMP deliberately avoids becoming a full media-management ecosystem.

The project favors:

* local files;
* small components;
* simple workflows;
* explicit responsibilities;
* minimal persistent state;
* replaceable subsystems;
* experimentation without destabilizing playback.

A feature does not belong in ToroidAMP simply because another music player has it.

It should improve playback, usability, portability, visualization, or meaningful extensibility.

---

## Architecture

The intended high-level audio pipeline is:

```text
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
Normalized Audio Data
    │
    ▼
Visualizer
    │
    ▼
Embedded / Fullscreen Render
```

Playback should remain boring and reliable.

Visualization is allowed considerably less supervision.

The exact playback backend, PCM strategy, rendering integration, and visualization contract are currently under technical evaluation.

See:

```text
docs/VISION.md
docs/SCOPE.md
docs/ARCHITECTURE.md
docs/CURRENT_STATE.md
```

for the current project definition.

---

## Technology

Current baseline:

* **Python**
* **Windows + Linux**
* **PySide6 / Qt** — leading UI candidate, pending validation
* **Pygame** — existing playback/visualization technology under evaluation
* **M3U/M3U8** — preferred playlist direction
* lightweight file-based settings/session persistence

Several technical choices remain intentionally open until small prototypes provide evidence.

---

## Project Status

> **Foundation 0 — Project Definition**

ToroidAMP is currently in its initial foundation stage.

Product vision and V1 scope have been defined.

Implementation has **not started yet**.

The next technical phase will audit reusable code from MetalWar-Installer and investigate:

* playback backend;
* tracker playback;
* PCM access;
* audio analysis;
* existing visualizer extraction;
* PySide6 integration;
* embedded and fullscreen visualization.

The project intentionally begins with technical probes before committing to production architecture.

---

## Contributing

ToroidAMP is intended to become an open-source project friendly to experimentation and external contributions.

Contribution guidelines will be added once the initial architecture and development workflow have been validated.

Likely contribution areas include:

* visualizers;
* audio-format support;
* Linux integration;
* Windows integration;
* UI improvements;
* testing;
* documentation.

A formal plugin API is **not** currently part of V1.

First we intend to prove the internal extension boundaries by actually using them.

---

## What ToroidAMP Is Not

ToroidAMP is not currently trying to become:

* Spotify;
* a streaming client;
* a cloud music service;
* a podcast manager;
* an indexed music-library platform;
* a social network;
* an AI recommendation engine;
* an enterprise media solution.

It is a desktop music player.

With toroids.

---

## Repository Structure

Initial documentation structure:

```text
ToroidAMP/
├── README.md
├── LICENSE
│
├── docs/
│   ├── VISION.md
│   ├── SCOPE.md
│   ├── ARCHITECTURE.md
│   ├── CURRENT_STATE.md
│   └── ARCHIVE.md
│
└── src/
```

The production source structure will be introduced as implementation begins.

---

## License

ToroidAMP will be released under an open-source license.

The specific license is currently being selected.

---

## Final Technical Requirement

Any architecture proposed for ToroidAMP must eventually answer one critical engineering question:

> **Can it make an audio-reactive toroid unnecessarily dramatic?**

If not, further investigation may be required.

---

# ToroidAMP

### **It really warps the toroid's ass!**

Local music. Classic modules. Questionable geometry.
