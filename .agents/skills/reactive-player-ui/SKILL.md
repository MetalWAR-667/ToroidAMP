---
name: reactive-player-ui
description: >-
  Design and implementation principles for building ToroidAMP's instrument-like,
  tactile, compact, and modular desktop UI operating across three experience scales (MINI, NORMAL, RETINA MELT).
---

# ToroidAMP — Reactive Player UI Specialist Skill

This skill guides the design and implementation of ToroidAMP's desktop user interface.

---

## 1. When to Use
* Designing and implementing PySide6 desktop player components across the 3 experience scales (`MINI`, `NORMAL`, `RETINA MELT`).
* Implementing micro-interactions, tactile button feedback, and magnetic module snapping.
* Connecting subtle `AudioFrame` musical reactivity to UI widgets.
* Managing transitions between `MINI` strip, `NORMAL` modular chassis, and `RETINA MELT` fullscreen.

## 2. When NOT to Use
* Writing audio decoding pipelines (use `audio-pipeline`).
* Implementing math algorithms inside visualizer classes (use `visualizer-authoring`).

---

## 3. Core Working Principle: The Three Experience Scales

ToroidAMP operates across **three deliberate experience scales**:

```text
MINI (380 x 36 px)
"I am here if you need me."
- Tiny, quiet, always-visible control strip.
- Stays on top, snaps to screen edges.
- Zero distraction while working.

NORMAL (420 x 135 px + Modules)
"Let's listen to music."
- Compact modular player core.
- Dockable/floating Visualizer and Playlist modules.
- Tactile, interactive demoscene instrument.

RETINA MELT (Fullscreen)
"TE VOY A DERRETIR LA RETINA."
- Fullscreen visualizer takeover with auto-hiding controls.
- Unrestricted visual spectacle and maximum juice budget.
- Returns cleanly to the exact prior scale (MINI or NORMAL).
```

### Golden Rules:
1. **LIFECYCLE SEPARATION (MINI != MINIMIZE != CLOSE)**:
   * **MINI** ($380 \times 36\text{ px}$) is an application experience scale visible on the desktop.
   * **MINIMIZE (`─`)** hides ToroidAMP to the system tray while audio continues playing in the background.
   * **CLOSE (`✕`)** is authoritative application shutdown (saves session, releases audio hardware, terminates process).
2. **VISUAL INTENSITY SCALES WITH FOOTPRINT**:
   * MINI is subtle, calm, and low-juice (zero visualizer rendering overhead).
   * NORMAL provides balanced tactile gamefeel.
   * RETINA MELT unleashes maximum procedural visual chaos.
3. **PRIOR-SCALE MEMORY**:
   * Exiting fullscreen or restoring from tray must remember whether the user came from MINI or NORMAL and restore that exact scale.
4. **MODULE STATE PRESERVATION**:
   * Collapsing NORMAL $\to$ MINI hides active modules; returning MINI $\to$ NORMAL seamlessly restores the active modules.


---

## 4. Revised Juice Budget by Experience Scale

| Experience Scale / Action | Juice Budget | Allowed Expression |
| :--- | :---: | :--- |
| **MINI Mode Controls** | **VERY LOW** | Immediate 1px icon shift, no distracting animations. |
| **MINI Screen Edge Snap** | **LOW** | Clean ~25px proximity snap flush to screen borders. |
| **NORMAL Transport Controls** | **LOW** | Sharp 2px depression, crisp state icon shift, instant settle. |
| **NORMAL Module Dock / Snap** | **MEDIUM** | Magnetic edge attraction preview, ~80ms spring settle snap ("clack"). |
| **NORMAL Track Change** | **LOW / MEDIUM** | Instant LCD marquee text update, subtle progress reset. |
| **RETINA MELT Controls** | **LOW** | Floating HUD auto-appears on mouse movement, fades after 2.5s idle. |
| **RETINA MELT Visualizer** | **UNRESTRICTED** | Maximum geometric deformation (`fckvar`), plasma shifts, ghosting. |

---

## 5. UI Architecture: Single-Window Chassis + ModuleShell

* **Unified Player Chassis**: A single frameless `QWidget` hosting a `QStackedWidget` containing both MINI and NORMAL layouts. Resizing the chassis ($380 \times 36 \leftrightarrow 420 \times 135$) guarantees spatial continuity without creating orphaned windows.
* **Module Shells**: `VisualizerModule` and `PlaylistModule` exist in three states: **CLOSED**, **DOCKED**, or **FLOATING**.
* **Retina Melt Fullscreen**: Dedicated frameless fullscreen window managing high-resolution offscreen Pygame rendering and auto-hiding HUD overlays.
