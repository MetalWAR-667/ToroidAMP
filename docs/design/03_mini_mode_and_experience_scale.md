# ToroidAMP — UI Direction Gate D.1: Mini Mode & Experience Scale Report

> **"MINI: 'I am here if you need me.' | NORMAL: 'Let's listen to music.' | RETINA MELT: 'TE VOY A DERRETIR LA RETINA.'"**

---

## 1. Executive Summary & Design Thesis

UI Direction Gate D.1 refines Direction D (Modular Instrument) by formalizing ToroidAMP's **Three Experience Scales**:
1. **MINI ($380 \times 36\text{ px}$)**: A tiny, always-visible control strip that stays on top and snaps to screen edges.
2. **NORMAL ($420 \times 135\text{ px} + \text{Modules}$)**: The compact modular core player with dockable Visualizer (bottom) and Playlist (right).
3. **RETINA MELT (Fullscreen)**: Unrestricted visualizer spectacle with auto-hiding floating controls and prior-scale memory.

### Core Working Principle:
> **Minimization should reduce presence, not remove control.**

---

## 2. The Three Experience Scales

```text
                 ┌────────────────────────────────────────────────────────┐
                 │                          MINI                          │
                 │   [◄◄] [►] [►►]  ♫ 01. Burn The World   02:15  ▲  ⛶    │
                 │                    (380 x 36 px)                       │
                 └───────────────────────────┬────────────────────────────┘
                                             │
                              ▲ NORMAL       │ ▼ MINI
                                             ▼
                 ┌────────────────────────────────────────────────────────┐
                 │                         NORMAL                         │
                 │  TOROIDAMP // v0.1 CORE                       ▼  ⛶  ✕  │
                 │  ♫ 01. Burn The World Waltz.mp3            02:15/03:20 │
                 │  ━━━━━━━━━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
                 │  [◄◄] [►] [❚❚] [■] [►►]  VOL [===|]    [ VIS ]  [ PL ] │
                 │                    (420 x 135 px)                      │
                 └───────────────────────────┬────────────────────────────┘
                                             │
                         ⛶ RETINA MELT       │ ESC / EXIT
                                             ▼
                 ┌────────────────────────────────────────────────────────┐
                 │                      RETINA MELT                       │
                 │                                                        │
                 │                   3D TOROID / RIBBON                   │
                 │                 (FULLSCREEN TAKEOVER)                  │
                 │                                                        │
                 │          ┌──────────────────────────────────┐          │
                 │          │ [◄◄] [►] [►►]  ♫ Track   02:15 ✕ │          │
                 │          └──────────────────────────────────┘          │
                 └────────────────────────────────────────────────────────┘
```

---

## 3. MINI Mode Specifications

* **Footprint**: **$380 \times 36\text{ px}$**.
* **Retained Controls**:
  * Micro transport buttons: Previous (`◄◄`), Play/Pause (`►` / `❚❚`), Next (`►►`).
  * Truncated track title marquee (`♫ 01. Burn The World Waltz.mp3`).
  * Elapsed playback time (`02:15`).
  * Compact volume status indicator (`🔊`).
  * Expand to NORMAL button (`▲ NORMAL`).
  * Direct to RETINA MELT button (`⛶`).
* **Always-On-Top**: Enabled automatically in MINI mode (`Qt.WindowStaysOnTopHint = True`), disabled in NORMAL mode.
* **Screen Edge Snapping**: Moving MINI within $25\text{ pixels}$ of the top, bottom, left, or right screen borders snaps the bar flush to the monitor edge.

---

## 4. Scale Transitions & State Memory

### Transition Behaviors:
1. **NORMAL $\to$ MINI**:
   * Saves active visibility of docked modules (`VisualizerModule`, `PlaylistModule`).
   * Hides modules and resizes chassis to $380 \times 36\text{ px}$ in place.
   * Enables Always-on-Top.
2. **MINI $\to$ NORMAL**:
   * Resizes chassis to $420 \times 135\text{ px}$.
   * Disables Always-on-Top.
   * Automatically restores previously opened modules (`VisualizerModule`, `PlaylistModule`) in their docked positions.
3. **Entry to RETINA MELT (from MINI or NORMAL)**:
   * Records `prior_scale = "mini"` or `prior_scale = "normal"`.
   * Hides the player chassis and launches fullscreen offscreen Pygame rendering at native display resolution.
4. **Exit from RETINA MELT (ESC or Exit button)**:
   * Closes fullscreen window.
   * Restores the player directly to its recorded `prior_scale` (MINI remains MINI; NORMAL remains NORMAL).

---

## 5. Fullscreen Overlay Controls (RETINA MELT)

* Floating pill HUD ($540 \times 48\text{ px}$) positioned at bottom center.
* Contains: Transport controls (`◄◄`, `►`/`❚❚`, `►►`), track title, elapsed time, and `✕ EXIT (ESC)` button.
* **Auto-Hide Behavior**: HUD is visible when mouse moves; automatically fades/hides after **2.5 seconds** of inactivity.

---

## 6. PySide6 Window Architecture Evaluation

* **Single Unified Chassis**: Implemented `UnifiedChassisPlayer` using `QStackedWidget` containing both MINI and NORMAL widgets.
* **Why this works best**:
  * Prevents window flicker and avoids destroying/recreating Qt windows.
  * Preserves window position and internal state smoothly during scale changes.
  * Completely eliminates orphaned floating windows when collapsing to MINI.

---

## 7. Mockup Validation & Execution

The prototype has been implemented and tested:

```powershell
py -3.13 experiments/ui_directions/direction_d1_mini.py
```

### Automated Headless Test Results:
* NORMAL Mode (420x135 px): **PASS**
* Module Docking (VIS + PL): **PASS**
* Transition to MINI (380x36 px + hide modules): **PASS**
* Return to NORMAL (Restore modules): **PASS**
* Entry to RETINA MELT from NORMAL: **PASS**
* Exit from RETINA MELT back to NORMAL: **PASS**
* Entry to RETINA MELT from MINI: **PASS**
* Exit from RETINA MELT back to MINI: **PASS**
* Frame Tick & Visualizer Offscreen Rendering: **PASS**

---

## 8. Recommendation for Production Cut 1B

Direction D.1 completely resolves the footprint and experience questions:
1. Implement `src/toroidamp/ui/chassis.py` supporting MINI and NORMAL modes.
2. Implement `src/toroidamp/ui/modules/` for `VisualizerModule` and `PlaylistModule`.
3. Implement `src/toroidamp/ui/fullscreen.py` for RETINA MELT.
4. Wire production `PlayerEngine`, `AnalysisHandoff`, and `ToroidVisualizer`.
