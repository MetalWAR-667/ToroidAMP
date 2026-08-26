# ToroidAMP — Vision

> **It really warps the toroid's ass!**

## 1. What is ToroidAMP?

ToroidAMP is a lightweight, open-source, cross-platform desktop audio player built in Python.

Its purpose is deliberately simple:

**Play local music, manage a current playlist, and turn audio into something worth looking at.**

ToroidAMP takes inspiration from the compact desktop music players of the late 1990s and early 2000s: applications that started quickly, stayed out of the way, played files directly, and still had enough personality to be recognizable at a glance.

It is not intended to become a music streaming platform, media library ecosystem, or account-based service.

ToroidAMP is a **player first and a visual playground second**.

Both are first-class parts of the application.

---

## 2. Core Identity

ToroidAMP is built around five ideas.

### 2.1 Local music first

The fundamental interaction should remain straightforward:

**Open files → build a playlist → press Play.**

The application should not require accounts, cloud services, online catalogs, or a database merely to reproduce music.

The user's files remain the source of truth.

### 2.2 Visualization is a core feature

Visualizers are not decorative extras added after the player is finished.

They are part of MetalAMP's identity.

A visualizer should be able to:

* run inside the main interface;
* switch without affecting playback;
* react to meaningful audio information;
* run in fullscreen;
* be disabled when not wanted;
* evolve independently from the playback system.

ToroidAMP should provide room for spectrum displays, waveforms, particles, wireframes, tunnels, plasma, pseudo-3D geometry, feedback effects and whatever questionable geometry seems appropriate.

Toroids are explicitly welcome.

### 2.3 Compact desktop application

ToroidAMP should behave like a traditional desktop music player.

It should be quick to access, comfortable to leave running, and capable of disappearing into the background when the user no longer needs the interface.

The default experience should favor:

* a compact main window;
* immediate playback controls;
* a visible current track;
* an accessible playlist;
* drag-and-drop interaction;
* minimization to the system tray;
* sensible restoration of the previous session.

Complexity should not be exposed unless it provides clear value.

### 2.4 Classic formats are first-class citizens

Modern compressed audio is necessary.

Tracker music is intentional.

ToroidAMP should target common formats such as:

* WAV;
* MP3;
* OGG/Vorbis;
* FLAC.

It should also treat classic tracker modules as legitimate music formats rather than historical curiosities, including at minimum:

* MOD;
* XM;
* S3M;
* IT.

Additional retro or game-music formats may be explored later if they fit the architecture and project identity.

### 2.5 Open by design

ToroidAMP is intended to be open source.

The internal architecture should therefore favor understandable boundaries and small components over clever but opaque machinery.

A contributor interested in visualizers should not need to understand playlist persistence.

A contributor adding an audio decoder should not need to modify the user interface.

A contributor improving Linux integration should not need to alter playback logic.

Extensibility should emerge from clean internal contracts before ToroidAMP attempts to provide a formal plugin system.

---

## 3. User Experience

ToroidAMP should feel immediate.

Starting the application should present the player, not a workflow.

Loading music should require as little ceremony as possible.

During normal use, the user should be able to:

* add individual files or groups of files;
* drag files into the player;
* play, pause and stop;
* move between tracks;
* seek within a track when supported;
* control volume;
* reorder the current playlist;
* load and save playlists;
* choose a visualizer;
* switch the visualizer to fullscreen;
* minimize ToroidAMP and allow playback to continue.

The interface may take inspiration from classic compact players such as Winamp, but ToroidAMP should develop its own visual identity rather than reproduce another application's interface.

---

## 4. Cross-Platform Vision

ToroidAMP targets:

**Windows and Linux.**

The application should maintain a shared Python codebase wherever practical.

Operating-system-specific behavior should be isolated behind explicit platform boundaries rather than leaking into playback, playlist, visualization, or application logic.

Platform integration may differ where necessary, including:

* system tray behavior;
* filesystem locations;
* media keys;
* desktop notifications;
* packaging;
* OS media integration.

Cross-platform support does not require every operating system to behave identically.

It requires the core application to remain portable.

---

## 5. Architectural Philosophy

ToroidAMP should remain small enough to understand.

The project favors:

* simple components;
* explicit responsibilities;
* replaceable subsystems;
* minimal persistent state;
* filesystem-native workflows where appropriate;
* dependency isolation;
* measured abstraction.

Architecture should support actual requirements rather than hypothetical future complexity.

No database, service layer, plugin framework, abstraction hierarchy, or external dependency should be introduced merely because ToroidAMP might need it someday.

At the same time, major subsystems should not be coupled in ways that prevent reasonable future evolution.

In particular, playback, audio analysis, visualization, UI, playlists, settings, and platform integration should be able to evolve without becoming a single monolithic system.

---

## 6. Relationship with MetalWar-Installer

ToroidAMP is an independent project.

MetalWar-Installer acts as an existing source of proven experiments and reusable ideas, particularly in:

* audio playback;
* tracker-module playback;
* playlist behavior;
* audio-reactive visualization;
* particles;
* geometric effects;
* spectrum-related processing.

ToroidAMP should **extract and adapt**, not blindly copy.

Existing code may be reused when appropriate, but it should enter ToroidAMP through the architectural boundaries of the new project.

The Installer remains free to evolve independently.

---

## 7. Visualizer Philosophy

Visual experimentation is deliberately encouraged.

ToroidAMP should make it cheap to try an idea and cheap to throw it away.

A visualizer may be useful, beautiful, nostalgic, excessive, ridiculous, or all four.

What matters is that experimentation inside the visualization system does not destabilize playback or the rest of the application.

Over time, ToroidAMP should aim for a small and understandable visualizer contract through which different effects can consume normalized audio-analysis information.

A future contributor should ideally be able to think:

**“I want to make the music drive this.”**

—not—

**“I need to understand the entire player before drawing a triangle.”**

---

## 8. What ToroidAMP Is Not

ToroidAMP does not aspire to replace Spotify, MusicBee, foobar2000, VLC, or a full media-management suite.

Its identity does not depend on having the largest feature list.

It does not need:

* an online account;
* cloud synchronization;
* a streaming catalog;
* a massive indexed music library;
* social features;
* recommendation algorithms;
* telemetry-driven engagement;
* a complex plugin ecosystem.

Some capabilities outside this vision may eventually be explored, but they should only enter the project when they strengthen ToroidAMP rather than dilute it.

---

## 9. Success Criteria

ToroidAMP succeeds when it becomes a program that is pleasant enough to use as an actual everyday local music player while remaining fun enough to develop as a visual experimentation platform.

A successful ToroidAMP should be:

**small enough to understand;
fast enough to forget it is running;
simple enough to use without instructions;
open enough to modify;
and visually irresponsible enough to deserve its name.**

---

## 10. Project Motto

> **ToroidAMP — It really warps the toroid's ass!**

If a future architectural decision makes audio-reactive toroids unnecessarily difficult, that decision deserves another look.
