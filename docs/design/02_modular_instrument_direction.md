# ToroidAMP — UI Direction Gate II: Direction D (Modular Instrument)

> **"WINAMP FOOTPRINT. MODULAR CONSTRUCTION. MODERN GAMEFEEL. DEMOSCENE SOUL."**

---

## 1. Executive Summary & Design Thesis

Following direct human evaluation of Directions A, B, and C (*"They are ugly and enormous"*), this investigation defines and prototypes **Direction D: Modular Instrument**.

### Core Problem Solved:
ToroidAMP must not start life as a conventional $800 \times 600\text{ px}$ monolithic application window with rigid sub-panels. Instead, it starts as an ultra-compact standalone player ($420 \times 135\text{ px}$) that expands dynamically by magnetically attaching internal modules (`VisualizerModule`, `PlaylistModule`) when desired.

```text
                  PLAYER CORE (420 x 135 px)
                              │
                  ┌───────────┴───────────┐
                  │ (Bottom Dock)         │ (Right Dock)
                  ▼                       ▼
          VISUALIZER MODULE        PLAYLIST MODULE
          (420 x 240 px)           (260 x 375 px)
```

---

## 2. Lessons from Directions A/B/C

1. **Direction A (Retro Instrument)**: Had good tactile affordance, but combined every control and viewport into one giant $750 \times 480\text{ px}$ static layout.
2. **Direction B (Reactive Minimal)**: Had clean typography, but the borderless hero visualizer forced the entire window to remain large ($680 \times 480\text{ px}$) during casual playback.
3. **Direction C (Demoscene Console)**: Had great character and telemetry, but cluttered the main view with heavy permanent grid frames.
4. **Conclusion**: The player must be **small first**. Modules must be optional, dockable, and detachable.

---

## 3. Compact Player Core Architecture

The core player is engineered to be completely self-sufficient at **$420 \times 135\text{ px}$**:

```text
┌────────────────────────────────────────────────────────┐
│ TOROIDAMP // v0.1 CORE                       [ ─ ][ ✕ ] │
├────────────────────────────────────────────────────────┤
│ ♫ 01. Burn The World Waltz.mp3             02:15/03:20 │
├────────────────────────────────────────────────────────┤
│ ━━━━━━━━━━━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
├────────────────────────────────────────────────────────┤
│ [◄◄] [►] [❚❚] [■] [►►]  VOL [====|]  [ VIS ]  [ PL ]   │
└────────────────────────────────────────────────────────┘
```

* **LCD Header**: Track title marquee, elapsed / total duration.
* **Progress Slider**: Seekable progress with fine micro-scrubbing.
* **Transport**: Tactile bevel buttons with immediate depression.
* **Module Chips**: High-contrast toggles (`VIS`, `PL`) that spawn/dock or collapse modules with a single click.

---

## 4. Module Model & Composition States

Each module supports three distinct operational states:

1. **`CLOSED`**: Completely hidden; zero CPU/GPU overhead; core remains in its compact footprint.
2. **`DOCKED`**: Visually and geometrically attached to the player core. Moving the player core automatically choreographs and moves all docked modules.
3. **`FLOATING`**: Detached into an independent frameless window that can be positioned anywhere on the desktop or across secondary monitors.
4. **`FULLSCREEN`** (*Visualizer only*): Expands seamlessly to fill the monitor, hiding titlebars and showing minimal floating controls on mouse movement.

---

## 5. Docking & Magnetic Snapping Interaction

* **Snapping Threshold**: $30\text{ pixels}$.
* **Bottom Edge (Visualizer)**: When dragged within 30px of the core's bottom edge, the visualizer snaps seamlessly beneath the core ($X = \text{core.left}$, $Y = \text{core.bottom} + 2$).
* **Right Edge (Playlist)**: When dragged within 30px of the core / visualizer stack's right edge, the playlist snaps to the right side ($X = \text{core.right} + 2$, $Y = \text{core.top}$) and dynamically stretches its height to match the stacked height of the docked modules.
* **Undocking Gesture**: Dragging a module by its titlebar instantly breaks magnetic lock and transitions the module to `FLOATING`.

---

## 6. PySide6 Architecture: Custom ModuleShell vs. QDockWidget

| Architectural Aspect | Standard Qt `QDockWidget` | ToroidAMP Custom `ModuleShell` |
| :--- | :--- | :--- |
| **Aesthetic Control** | Heavy IDE styling, clumsy tab bars, visible splitter dividers. | Pure pixel-perfect cyber/instrument chassis (#0d0e15 + neon border). |
| **Window Frame** | Uses OS native frames when floating. | Consistent custom frameless dark styling in both docked and floating modes. |
| **Snapping Behavior** | Rigid drop-zones inside a parent `QMainWindow`. | Fluid desktop magnetic edge proximity snapping. |
| **Complexity** | High overhead for multi-window coordination. | Lightweight (~120 lines), clear event delegation. |
| **Recommendation** | **REJECTED** | **CONFIRMED & RECOMMENDED FOR PRODUCTION**. |

---

## 7. Gamefeel at Small Scale

* **Play Click**: Immediate 1px depression, green phosphor jewel light-up, instant LCD marquee animation start.
* **Module Snap ("Clack")**: Smooth geometric settling within 80 ms when entering proximity, closing visual borders seamlessly.
* **Fullscreen Expansion**: Zero-latency transition directly to the monitor geometry, retaining continuous Pygame surface rendering.

---

## 8. Human Evaluation Checklist

To evaluate the interactive prototype directly, execute:

```powershell
py -3.13 experiments/ui_directions/direction_d_modular.py
```

### Questions for the User:
1. Does the initial player window feel adequately compact and immediate on your desktop?
2. Does clicking `VIS` and `PL` feel natural and responsive?
3. Does detaching/undocking a module and moving it independently feel intuitive?
4. Does the magnetic snapping behavior provide the right "clack" feel when dragging modules close together?
5. Does the visualizer fullscreen transition (pressing `⛶ FULLSCREEN` or `Esc`) work cleanly?

---

## 9. Recommendation for Production Cut 1B

We recommend adopting **Direction D: Modular Instrument** as the production UI foundation for Cut 1B:
* Implement `src/toroidamp/ui/core_window.py` (Compact Core).
* Implement `src/toroidamp/ui/modules/visualizer_module.py` and `playlist_module.py`.
* Implement `src/toroidamp/ui/window_manager.py` (Modular Choreography).
* Wire `PlayerEngine`, real decoders, and `ToroidVisualizer` directly into the modular UI.
