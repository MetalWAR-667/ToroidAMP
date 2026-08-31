# ToroidAMP — Scope

> **It really warps the toroid's ass!**

## 1. Purpose

This document defines the functional boundaries of ToroidAMP.

Its purpose is to protect the project from uncontrolled expansion while leaving deliberate room for experimentation, particularly in audio visualization.

ToroidAMP should become a **small, usable desktop audio player first**.

Everything beyond that must justify its complexity.

The initial development target is a compact V1 that can be used as a real local music player on Windows and Linux and that establishes visualization as a first-class subsystem.

---

## 2. V1 Goal

ToroidAMP V1 should allow a user to:

**launch the application → load music → manage a current playlist → play it → visualize it → minimize the player and continue listening.**

V1 does not need to compete with mature media players.

It needs to establish a reliable foundation that is pleasant to use and easy to extend.

---

## 3. V1 — Required Features

### 3.1 Audio Playback

V1 must provide:

* Play.
* Pause.
* Stop.
* Previous track.
* Next track.
* Volume control.
* Playback-position display.
* Seek control where supported by the active audio backend and format.
* Automatic progression to the next playlist item.
* Basic repeat behavior.
* Basic shuffle behavior.

Playback must continue while the main application window is minimized.

---

### 3.2 Supported Audio Formats

V1 targets common local audio formats:

* WAV.
* MP3.
* OGG/Vorbis.
* FLAC.

V1 also targets classic tracker-module formats:

* MOD.
* XM.
* S3M.
* IT.

The exact decoder/backend strategy remains an architectural decision and is not defined by this scope document.

Support means reliable playback through ToroidAMP's normal playback workflow.

Format-specific capabilities such as seeking or metadata may vary where technically necessary.

---

## 4. Current Playlist

ToroidAMP V1 uses a **current-playlist model**, not a music-library model.

The user must be able to:

* add individual files;
* add multiple files;
* remove entries;
* clear the playlist;
* reorder entries;
* select a track for immediate playback;
* load a saved playlist;
* save the current playlist.

M3U/M3U8 should be the preferred playlist interchange format unless implementation work reveals a concrete reason to choose otherwise.

The playlist should remain simple and filesystem-oriented.

---

## 5. Drag and Drop

V1 should support drag and drop as a primary convenience feature.

At minimum:

* dragging supported audio files into ToroidAMP adds them to the current playlist;
* dragging multiple files is supported.

Directory dropping may be included if it can be implemented without introducing disproportionate complexity.

---

## 6. Main Interface

ToroidAMP should provide a compact desktop interface inspired by the immediacy of classic standalone audio players.

The V1 interface should expose:

* current track;
* playback state;
* playback position;
* track duration when available;
* playback controls;
* volume;
* playlist access;
* visualizer access;
* fullscreen visualization.

The interface should remain usable without requiring large screen space.

A compact/minimal mode is desirable for V1 but may be deferred if the standard interface is already sufficiently small.

ToroidAMP may take inspiration from classic players but should not reproduce another application's interface or artwork.

---

## 7. Visualization

Visualization is **required for V1**.

A V1 without working audio-reactive visualization is not considered feature complete.

The visualizer must:

* operate inside the ToroidAMP interface;
* support fullscreen presentation;
* react to audio-derived information;
* remain isolated from playback control;
* be switchable without interrupting playback;
* be disableable when visualization is not desired.

V1 should ship with multiple visualizers.

Existing visualization work from MetalWar-Installer should be evaluated as the primary source for the initial set rather than recreated without reason.

Potential reusable effects include:

* spectrum-based visualization;
* starfields;
* particles;
* geometric transformations;
* wireframe/pseudo-3D effects;
* audio-reactive shapes.

The exact initial visualizer list will be determined after the MetalWar-Installer visual-effects audit.

At least one audio-reactive toroid is strongly encouraged.

For obvious reasons.

---

## 8. Audio Analysis

ToroidAMP V1 must provide enough audio-analysis information to support its visualizers.

Potential analysis data includes:

* waveform/sample information;
* amplitude/intensity;
* peak;
* RMS;
* frequency spectrum;
* frequency bands;
* beat information.

The precise analysis contract belongs to architecture and will be defined after the playback/backend investigation.

V1 does not require professional audio-analysis accuracy.

Analysis exists primarily to drive responsive visualization.

---

## 9. Background Operation

ToroidAMP is intended to remain running while the user performs other work.

V1 should therefore provide:

* minimize behavior;
* system tray integration;
* continued playback while hidden/minimized;
* restoration from the tray;
* an explicit way to terminate the application.

A preference such as **Close to tray** may be provided.

ToroidAMP should not consume unnecessary rendering resources while visualization is hidden or disabled.

---

## 10. Session Persistence

ToroidAMP should remember enough state to avoid unnecessary setup on every launch.

V1 may persist:

* volume;
* current playlist or last playlist;
* current track;
* playback position where practical;
* shuffle/repeat state;
* selected visualizer;
* visualizer preferences;
* window position/size;
* tray/close behavior.

Persistent state should remain lightweight.

A simple configuration format such as JSON is preferred unless actual requirements demonstrate the need for something more complex.

No database is required by the V1 scope.

---

## 11. Metadata

V1 should display useful metadata when readily available, such as:

* track title;
* artist;
* album;
* duration;
* filename.

Tracker modules may expose different metadata from conventional audio formats.

ToroidAMP should tolerate incomplete or absent metadata gracefully and fall back to sensible filesystem information.

V1 does not require metadata editing.

---

## 12. Platform Support

V1 targets:

* Windows.
* Linux.

A shared codebase should be maintained wherever practical.

Platform-specific implementation is acceptable for:

* system tray behavior;
* filesystem integration;
* media keys;
* notifications;
* OS media controls;
* packaging.

A Windows build may become operational before the Linux build during development, but Linux support is part of the V1 target rather than an unspecified future port.

---

## 13. Distribution

ToroidAMP should be usable without requiring the end user to manually install or configure a Python development environment.

V1 should therefore target packaged desktop distributions for supported operating systems.

Exact packaging technology remains an implementation decision.

Source execution for developers remains supported.

---

## 14. Open-Source Contribution

ToroidAMP is intended to be open source.

V1 should establish clean enough subsystem boundaries that future contributors can work on areas such as:

* visualizers;
* audio formats;
* UI;
* platform integration;
* documentation;

without requiring intimate knowledge of the entire application.

A formal third-party plugin framework is **not required for V1**.

The initial goal is to prove stable internal contracts first.

If those contracts later provide a natural foundation for plugins, a public extension system may be designed from evidence rather than speculation.

---

## 15. Explicitly Out of Scope for V1

The following are not V1 requirements:

* streaming services;
* Spotify/YouTube integration;
* internet radio;
* podcasts;
* cloud synchronization;
* user accounts;
* social features;
* recommendation systems;
* online music discovery;
* indexed music-library management;
* music-library databases;
* metadata editing;
* lyrics retrieval;
* album-art downloading;
* advanced DSP;
* professional equalization;
* audio conversion;
* CD ripping;
* CD burning;
* mobile versions;
* web versions;
* remote control;
* network playback;
* formal third-party plugin marketplace.

These features are not necessarily forbidden forever.

They simply have no claim on V1 development time.

---

## 16. Future Exploration

After V1 is stable, ToroidAMP may explore features that strengthen its existing identity.

Possible areas include:

* additional visualizers;
* user-created visualizers;
* formal visualizer API;
* visualizer presets;
* configurable visualizer parameters;
* transitions between visualizers;
* automatic visualizer rotation;
* richer fullscreen modes;
* media-key integration;
* native OS media-session integration;
* additional tracker and retro formats;
* SID;
* NSF;
* SPC;
* VGM;
* richer tracker metadata;
* optional equalization;
* skins/themes;
* compact/miniplayer modes;
* additional playlist formats.

These are **possibilities, not roadmap commitments**.

They enter active scope only through an explicit future decision.

---

## 17. Scope Expansion Rule

A proposed feature should normally enter active development only if at least one of the following is true:

1. It materially improves basic local music playback.
2. It materially improves everyday usability.
3. It strengthens ToroidAMP's visualization identity.
4. It improves portability or reliability.
5. It creates a clean extension point supported by an actual use case.

Features that mainly transform ToroidAMP into a media-management platform should face a deliberately high barrier.

---

## 18. V1 Completion Definition

ToroidAMP V1 can be considered functionally complete when a packaged application can reliably perform the following workflow:

**Launch ToroidAMP.**

**Add MP3/OGG/WAV/FLAC or MOD/XM/S3M/IT files.**

**Create and manipulate a playlist.**

**Save and reload that playlist.**

**Play, pause, stop, seek where supported, change volume, and navigate tracks.**

**Display audio-reactive visualization inside the player.**

**Switch that visualization to fullscreen.**

**Minimize ToroidAMP while playback continues.**

**Restore the application and continue the session.**

**Exit cleanly.**

At that point, additional work belongs primarily to stabilization, polish, packaging, documentation, or a subsequent scope.

---

## 19. V1 Principle

ToroidAMP V1 does not need every feature a modern music player can provide.

It needs to do a small number of things well:

> **Play the file.
> Manage the playlist.
> Stay out of the way.
> Warp the toroid.**
