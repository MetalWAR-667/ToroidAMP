# ToroidAMP — RETINA MELT Integrated Shader Lab

> **"HUD is for listening. Tune is for adjusting. Lab is for fucking around with light. And when the controls disappear, RETINA MELT must still feel like a visualizer, not an IDE."**

---

## 1. Executive Summary

**GPU-PROD-002** integrates the proven single-pass GLSL authoring workflow into production **RETINA MELT** as an optional, high-leverage authoring surface. 

This cut does **NOT** replace the standalone GPU Visualizer Lab (`experiments/gpu_visualizers/lab_app.py`). Rather, it establishes two complementary environments:

| Environment | Primary Role | Audio Source | Scope / Target |
| :--- | :--- | :--- | :--- |
| **Standalone GPU Lab** | Isolated technical workbench | Synthetic profiles & generators | Deliberate breakage, profiling, syntax experiments |
| **RETINA Integrated Lab** | Fullscreen visual judgment & live authoring | Real `AudioFrame` from `PlayerEngine` | Live tuning, local shaders, preset exploration |

---

## 2. Interaction Model & State Machine

RETINA MELT now provides three distinct interaction depths:

```
[ RETINA MELT FULLSCREEN VIEWPORT ]
  │
  ├── Depth 1: HUD (Playback Transport, Seeking, Volume, Mode Switch)
  │
  ├── Depth 2: TUNE Panel (Simple, non-technical parameter adjustment)
  │
  └── Depth 3: LAB Panel (Authoring surface: identity, load, reload, presets, diagnostics)
```

### State Machine Rules:
1. **`TUNE XOR LAB` (Strict Mutual Exclusivity)**:
   - Clicking `[ ⚗ LAB ]` opens the Lab overlay and automatically closes the `[ ⚙ TUNE ]` panel.
   - Clicking `[ ⚙ TUNE ]` opens the Tune panel and automatically closes the `[ ⚗ LAB ]` panel.
2. **Unified Parameter State**:
   - Both panels mutate and read from `GLVisualizerCanvas.current_params`.
   - Modifying a slider in TUNE immediately synchronizes with LAB and vice versa.
3. **Explicit HUD Pinning & Auto-Hide**:
   - **Left Click** on the canvas: Sets state to `HUD_PINNED`, keeps HUD and active overlay permanently visible, and suspends the auto-hide timer.
   - **Right Click** on the canvas: Sets state to `HUD_HIDDEN`, immediately hiding the HUD and closing both TUNE and LAB panels.
   - **Transient Movement**: Sets state to `HUD_VISIBLE` with a 2.5s timer. The timer is automatically suspended while either TUNE or LAB is open.
4. **Keyboard Navigation**:
   - `L`: Toggles the Integrated LAB panel.
   - `T`: Toggles the TUNE panel.
   - `R`: Hot-reloads the active shader from disk (when in LAB or when a local shader is active).
   - `Space`: Toggles playback pause/play.
   - `M`: Cycles production visualizer modes.
   - `Escape` / `F`: Hierarchical dismiss (`LAB` $\rightarrow$ `TUNE` $\rightarrow$ Exit Fullscreen).

---

## 3. Integrated LAB Surface Architecture

The Integrated LAB panel (`#retina_lab`, width: 340px) is an anchored overlay docked above the HUD:

1. **Header & Mode Identity**:
   - Displays whether the active visualizer is `OFFICIAL` (e.g. `MODE: OFFICIAL — TOROID IDENTITY`) or `LOCAL` (e.g. `MODE: LOCAL — MY_SHADER`).
2. **Command Actions Bar**:
   - `[ 📁 LOAD... ]`: Opens a file dialog pointing to `user_shaders/` to load external `.frag` / `.glsl` shaders.
   - `[ ⟳ RELOAD (R) ]`: Re-reads and recompiles the active shader source from disk without pausing audio playback.
   - `[ ↺ RESET ]`: Restores all parameters to declared shader defaults.
3. **Preset Actions Bar**:
   - `[ ⇱ SAVE PRESET ]`: Exports current typed parameter values to a clean JSON preset file.
   - `[ ⇲ LOAD PRESET ]`: Loads and applies a JSON preset file with type validation and boundary clamping.
4. **Scrollable Typed Parameter Rack**:
   - `float` $\rightarrow$ Horizontal `QSlider` ($0..1000$ internal range) with real-time numeric readouts.
   - `bool` $\rightarrow$ Cyberpunk-styled `QCheckBox`.
   - `color` $\rightarrow$ Color swatch `QPushButton` opening `QColorDialog` and passing canonical `#RRGGBB` hex strings.
5. **Diagnostics & Error Isolation View**:
   - Displays compiler and linker diagnostics in-place.
   - If reload or load fails, the previous valid program is retained, audio playback continues uninterrupted, and the GLSL compile log is displayed in red.

---

## 4. Local Shader Security & Provenance Policy

- **`user_shaders/` Boundary**:
  - Located at project root and strictly gitignored.
  - User shaders are treated as private, local experimental code.
  - Loading an external shader does not touch Git, rewrite official shaders, or persist over official visualizer slots in `session.json`.
- **Session Persistence**:
  - Official visualizer parameters (`toroid_identity`, `cyber_bloom`) persist across sessions.
  - Local shaders are non-destructive session overrides.

---

## 5. Architectural Verification & Scope Status

- **Tested Requirements**:
  - All 24 operational and lifecycle gates are covered by [`tests/test_gpu_prod_002.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_gpu_prod_002.py).
- **Deferred Out-of-Scope Capabilities**:
  - **Level 3 Compatibility**: Multiple arbitrary `iChannel` texture units, audio buffer sampling, and cubemaps.
  - **Level 4 Architecture**: Multipass pipelines, offscreen FBO ping-ponging, temporal accumulation buffers.
  - **Embedded Code Editor**: In-app syntax text editor (hot reload via external editor is the design target).
