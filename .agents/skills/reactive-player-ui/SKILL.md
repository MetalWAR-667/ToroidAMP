---
name: reactive-player-ui
description: >-
  Design and implementation principles for building ToroidAMP's instrument-like,
  tactile, and musically reactive desktop UI using PySide6.
---

# ToroidAMP — Reactive Player UI Specialist Skill

This skill guides the design and implementation of ToroidAMP's desktop user interface.

---

## 1. When to Use
* Designing and implementing PySide6 desktop player components.
* Implementing micro-interactions, tactile button feedback, and layout transitions.
* Connecting subtle `AudioFrame` musical reactivity to UI widgets.
* Implementing Compact, Expanded, and Fullscreen player modes.

## 2. When NOT to Use
* Writing audio decoding pipelines (use `audio-pipeline`).
* Implementing math algorithms inside visualizer classes (use `visualizer-authoring`).

---

## 3. UI Design Philosophy: The Instrument, Not the Widget

ToroidAMP is designed as a **musical instrument**, not a bureaucratic form or standard OS utility window.
* **Immediate Response**: Every click, hover, and drag must deliver immediate visual feedback (<50 ms).
* **Tactile Continuity**: Expanding the playlist or toggling visualizers should feel like spatial unfolding of one unified chassis, not opening disjointed popups.
* **Demoscene Heritage without Cosplay**: Draw inspiration from classic hardware players, tracker interfaces, and neon vector aesthetics without imitating 1998 bitmap artifacts.
* **Reactive Does Not Mean Distracting**: While visualizers can be visually unhinged, transport controls must remain readable, stable, and ergonomic.

---

## 4. The Juice Budget

Use animation and reactivity selectively according to the project's Juice Budget:

| Component / Action | Juice Budget | Allowed Expression |
| :--- | :---: | :--- |
| **Transport Controls** (Play/Pause/Stop) | **LOW** | Sharp state click, subtle border glow, instant settle. |
| **Button Hover / Focus** | **LOW** | 100ms smooth tint shift, no distracting wobbles. |
| **Track Change** | **MEDIUM** | Crisp text slide/fade, subtle track-number flash. |
| **Playlist Expansion** | **MEDIUM** | Smooth spatial accordion unfold with spring settling. |
| **Continuous Musical UI Response** | **LOW / SUBTLE** | Subtle breathing border on peak energy, soft VU level meters. |
| **Fullscreen Transition** | **HIGH** | Seamless visualizer expansion, HUD controls auto-fade on idle. |
| **Toroid Visualizer** | **UNRESTRICTED** | Maximum geometric chaos, warp, and plasma rotation. |

---

## 5. Three Coherent UI Modes

1. **COMPACT MODE**:
   * Minimal desktop footprint (~360×120 px).
   * Essential transport buttons, current track marquee, volume, and mini-visualizer / VU meter.
   * Perfect for background listening while working.
2. **EXPANDED MODE**:
   * Standard desktop player footprint (~680×520 px).
   * Full embedded visualizer display, interactive playlist queue, track metadata, and audio telemetry.
3. **FULLSCREEN MODE**:
   * Visualizer occupies entire monitor display.
   * Minimalist floating transport HUD that fades out after 2.5s of mouse inactivity.

---

## 6. Accessibility & Usability Guardrails
* **Contrast**: Text and indicators must maintain at least 4.5:1 contrast against dark backgrounds.
* **State Clarity**: Play/Pause/Stop state must be unmistakably clear from icon shape and distinct color, not just animation.
* **Keyboard Navigation**: Space (Play/Pause), Left/Right (Seek), Up/Down (Volume), F (Fullscreen).
* **High-DPI**: All widgets must scale properly across high-resolution displays without blurry rendering.
