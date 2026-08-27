# ToroidAMP — VIS-001: Production Promotion (Deep Field & ToroidAMP Floor)

> **A good visualizer may also be a good ingredient.**
> **Better musical intelligence does not require throwing away better visual composition.**
> **Preserve the barrel roll.**

---

## 1. Executive Summary

Visualizer Lab II completed human evaluation across its three candidates. Following human evaluation:
* **Starfield: Deep Field** has been promoted to ToroidAMP production (`src/toroidamp/visualizers/deep_field.py`).
* **ToroidAMP Floor** has been promoted to production (`src/toroidamp/visualizers/floor.py`) with its donor perspective wireframe grid restored around its validated real `AudioFrame` spectral topology.
* **Matrix Wing Commander** is held in experimental status in `experiments/visualizers/` for future revisit to faithfully recover donor flight kinematics (depth routing, visible trails, barrel rolls).

Both promoted visualizers are registered in the production selector (`VisualizerModule`) and fullscreen mode (`RetinaMeltWindow`) by cleanly appending to the existing visualizer list, preserving session index compatibility for existing users. All 22 automated VIS-001 tests pass, verifying contract compliance, spectral topology differentiation, bounded transient physics, and resize safety.

---

## 2. Lab II Human Verdict

The authoritative human evaluation of Visualizer Lab II established:

### Deep Field
* **HUMAN VERDICT**: **PASS**
* **Production Promotion**: **YES**
* **Additional Finding**: Strong standalone visualizer. Very high future composition value.
* **Human Observation**: The starfield works well independently, but feels especially suitable as a background layer underneath other visual systems.

### ToroidAMP Floor
* **HUMAN VERDICT**: **PASS**
* **Production Promotion**: **YES**
* **Human Observation**: The new musical behavior is successful and visually attractive. However, the donor MetalWar-Installer presentation was visually stronger because the illuminated tiles existed beneath / within a perspective wireframe grid.
* **Required Production Polish**: Restore that visual relationship (perspective wireframe grid + illuminated tile field) without reverting the new real `AudioFrame` musical model.

### Matrix Wing Commander
* **HUMAN VERDICT**: **HOLD / NOT READY FOR PRODUCTION**
* **Production Promotion**: **NO**
* **Specific Failure**: The experimental reinterpretation did not preserve important donor flight choreography (depth-traveling routes, perspective trajectories, visible trails, barrel rolls, cinematic flight feel).
* **Future Work**: First recover donor kinetic language faithfully, then add ToroidAMP musical causality.
* **Status**: Retained in `experiments/visualizers/matrix_wing_commander.py`.

---

## 3. Promotion Rationale

1. **Proven Musical Intelligence**: Both Deep Field and ToroidAMP Floor demonstrated authentic musical causality across disparate synthetic profiles and human listening sessions. Neither visualizer collapses into a naive "RMS = speed" or "volume = brightness" meter.
2. **Robust Performance Budget**: Both visualizers execute comfortably inside the 8ms/frame budget (Deep Field: 0.84–1.25ms; ToroidAMP Floor: 1.54–2.94ms across 300×180 to 1920×1080).
3. **Contract Parity**: Both visualizers cleanly conform to `toroidamp.visualizers.base.Visualizer` with zero Qt imports, no donor repository coupling, and zero experiment dependencies.

---

## 4. Deep Field Production Integration

* **Location**: `src/toroidamp/visualizers/deep_field.py`
* **Class**: `DeepFieldVisualizer(Visualizer)`
* **Selector Name**: `Deep Field` (Index 2 in production selector)
* **Lifecycle**:
  - Dynamically resizes on `resize(w, h)` without leaking state or creating stale offscreen buffers.
  - Sized and rendered independently inside `VisualizerModule` and `RetinaMeltWindow`.
  - Halts rendering operations when the host module is hidden or minimized to system tray.

---

## 5. Deep Field Musical Model

Deep Field preserves its validated Lab II musical mappings:

| Signal | Target Behavior | Dynamics Model |
|---|---|---|
| `bass` | Depth pressure / forward camera acceleration | Exponential smoothing (`k=2.2`) |
| `mids` | Lateral camera drift & roll tendency | Smoothed angular velocity (`k=1.5`) integrated into persistent camera angle |
| `treble` | Sparkle & fine starfield density (`+0..220` far stars) | Smoothed population target (`k=3.0`) |
| `spectrum[64]` | Warm/cool near-vs-far depth color gradient | Slow spectral bias evolution (`k=0.4`) |
| `beat` | Short forward impulse | Fast exponential decay (`math.exp(-dt * 5.0)`) |
| `strong_beat` | Rare bounded hyperspace compression event | 0.45s sine envelope with 1.4s cooldown gate |
| `rms` | Restrained global luminance envelope | Smoothed master multiplier (`k=2.0`) |
| `silence` | Slow inertial cruise (`BASE_CRUISE = 0.35`) | Never hard-stops or freezes |

---

## 6. Deep Field Composition Potential

* **Composition Value**: **HIGH**
* **Finding**: Deep Field functions exceptionally well as a standalone visualizer, but its clean 3D depth and subtle rotational drift make it an ideal future **BACKGROUND** layer candidate.
* **Separation**: The internal simulation (`_Star` positions, camera angle, depth pressure) is clean and decoupled from presentation assumptions, avoiding premature abstraction while keeping future layering straightforward.

---

## 7. ToroidAMP Floor Production Integration

* **Location**: `src/toroidamp/visualizers/floor.py`
* **Class**: `ToroidAMPFloorVisualizer(Visualizer)`
* **Selector Name**: `ToroidAMP Floor` (Index 3 in production selector)
* **Lifecycle**:
  - Implements full `Visualizer` contract (`resize`, `update`, `render`, `get_name`).
  - Self-contained inside `src/toroidamp/visualizers/`, zero donor or experiment imports.

---

## 8. Donor Wireframe Audit

An audit of `MetalWar-Installer/effects.py:1905` (`RetroGrid`) revealed:
* **Geometry**: Perspective floor grid with nonlinear depth row spacing (`(row * 20) ** 1.1`) converging to a vanishing point on a horizon line (`height // 2 + 50`).
* **Visual Presentation**: Perspective grid lines combined with illuminated quad cells that flashed with neon colors and white outline borders on high life.
* **Donor Limitation**: Illumination was driven purely by flat random cell spawns on a fake `kick` metronome with zero propagation and zero frequency spatial meaning.

---

## 9. Final Floor Visual Composition

The promoted production ToroidAMP Floor unites the donor's perspective wireframe with ToroidAMP's real audio analysis:

```text
┌─────────────────────────────────────────────────────────┐
│                    HORIZON GLOW                         │
├─────────────────────────────────────────────────────────┤
│                  /    |    |    \                       │
│      PERSPECTIVE /   [TILE] [TILE]  \  WIREFRAME        │
│          GRID   /  [TILE]   [TILE]   \  STRUCTURE       │
│                /                       \                │
│               / [REACTIVE TILE FIELD]   \               │
│              /  (Real Spectral Topology) \              │
└─────────────────────────────────────────────────────────┘
```

1. **Wireframe (Structure & Depth)**:
   - Perspective column lines converging to the center vanishing point on the horizon.
   - Nonlinearly spaced horizontal row lines expanding towards the camera.
   - Subtle musical behavior: horizon height and grid brightness gently breathe with bass and beat transients without turning into a strobe.
2. **Reactive Tiles (Musical Expression)**:
   - Discrete quadrilateral cells inside the perspective grid.
   - Low frequencies illuminate central and near-camera structural cells.
   - High frequencies sparkle across outer flank columns.
   - Energetic tiles (`energy > 0.65`) render crisp bright/white border outlines.
   - Memory & propagation: attack/decay state machine gives tiles organic residual glow.

---

## 10. Floor Musical Model

| Signal | Floor Mapping | Temporal Dynamics |
|---|---|---|
| `spectrum[64]` | Maps 64 bins across rows (frequency depth) and columns (frequency spread) | Continuous target accumulation |
| `bass` | Central structural core illumination | Continuous target floor |
| `mids` | Intermediate body structure across mid-band rows | Continuous target floor |
| `treble` | Peripheral flank accents (outer columns) | Continuous target floor with time-phased distribution |
| `beat` | Propagating wave launched from current spectral peak cell | Traveling radial pulse (`_Pulse`) |
| `strong_beat` | Multi-origin full-field traveling wave burst | 3 simultaneous pulses across center and flanks |
| `tile_energy` | Per-cell persistent brightness | Fast rise (`ATTACK_RATE = 14.0`), slow fade (`DECAY_PER_SEC = 0.65`) |
| `silence` | All targets drop to 0, existing energy fades to dormant dim grid | Exponential decay |

**Validated Invariant**: Same approximate BPM + different spectral distribution produces structurally different tile topologies (e.g. metal vs. electronic).

---

## 11. Selector / Session Compatibility

### Production Visualizer Ordering
ToroidAMP maintains an authoritative visualizer registry:

| Index | Visualizer Class | Module Button Name | Description |
|:---:|:---|:---|:---|
| **0** | `ToroidVisualizer` | `MODE: 3D TOROID` | Original 3D parametric wireframe torus |
| **1** | `WaveformRibbonVisualizer` | `MODE: WAVEFORM RIBBON` | Flowing neon oscilloscope ribbon |
| **2** | `DeepFieldVisualizer` | `MODE: DEEP FIELD` | **PROMOTED**: 3D inertial starfield tunnel |
| **3** | `ToroidAMPFloorVisualizer` | `MODE: TOROIDAMP FLOOR` | **PROMOTED**: Perspective wireframe reactive floor |

### Session Compatibility
* New visualizers are **strictly appended** after existing entries.
* Existing persisted session files with `selected_visualizer_idx: 0` or `1` retain their exact visualizer assignment.
* Selecting new visualizers (index 2 or 3) persists atomically into `session.json` and restores safely upon restart.

---

## 12. Resize Validation

Both visualizers were validated across all required viewport geometries:
* `300×180` (Minimum module size)
* `420×240` (Default module size)
* `800×450` (Expanded module size)
* `1280×720` (HD windowed)
* `1920×1080` (RETINA MELT fullscreen)

**Results**:
* No unhandled exceptions or NaN coordinate projections.
* Viewport center and aspect scaling dynamically update without stale buffers.
* No runaway memory allocations or surface leakages.

---

## 13. Performance

Benchmarked on Windows with Python 3.14 + Pygame-ce (metal profile, 200 frames, 20-frame warmup dropped):

| Resolution | Deep Field (Avg / P95) | ToroidAMP Floor (Avg / P95) | Budget Margin |
|:---|:---:|:---:|:---:|
| **300×180** | 0.84 ms / 0.91 ms | 1.54 ms / 1.92 ms | Comfortably under 8.0 ms (60 FPS) |
| **420×240** | 0.85 ms / 0.92 ms | 1.61 ms / 2.00 ms | Comfortably under 8.0 ms (60 FPS) |
| **800×450** | 0.92 ms / 0.99 ms | 1.89 ms / 2.28 ms | Comfortably under 8.0 ms (60 FPS) |
| **1280×720** | 1.04 ms / 1.12 ms | 2.36 ms / 2.76 ms | Comfortably under 8.0 ms (60 FPS) |
| **1920×1080** | 1.25 ms / 1.34 ms | 2.94 ms / 3.37 ms | Comfortably under 8.0 ms (60 FPS) |

---

## 14. Silence Behavior

* **Silence is a Musical State**:
  - **Deep Field**: Retains a calm, slow forward inertial cruise (`BASE_CRUISE = 0.35`). Stars drift gently; the scene never freezes or goes black.
  - **ToroidAMP Floor**: Active tile energy decays exponentially into a dim, dormant wireframe structure. No artificial pulsing or random activity occurs during track pauses or silence.

---

## 15. Matrix Wing Commander Hold

* **Status**: **HOLD / NOT READY FOR PRODUCTION**
* **Reason**: Experimental reinterpretation lost critical donor flight kinematics.
* **Requirements for Future Revisit**:
  1. Faithfully recover 3D depth flight paths (ships moving into background depth $z$).
  2. Perspective trajectory and waypoint banking.
  3. Visible motion trails.
  4. Scripted flight maneuvers including barrel rolls.
  5. Apply ToroidAMP musical causality to the recovered kinetic language.
* **Repository Rule**: Remains intact in `experiments/visualizers/matrix_wing_commander.py` including the mandatory demoscene comment:
  ```python
  # Why?
  # Because we could.
  ```

---

## 16. Future Composable Visualizer Direction

* **Status**: **DEFERRED / NOT ACTIVE WORK**
* **Vision**: In the future, ToroidAMP may allow users to add/remove visual components to construct layered visual scenes rather than selecting only monolithic visualizers.
* **Conceptual Layer Hierarchy**:
  - `BACKGROUND`: Deep Field, Matrix Rain, Plasma
  - `STRUCTURE`: Wireframe Grid, Reactive Tiles
  - `FOREGROUND`: Spectrum, Waveform Ribbon, 3D Toroid
  - `EVENT`: X-Wing formations, particle bursts
  - `TYPOGRAPHY`: Lyrics, scrollers, ToroBot barks
  - `POST-FX`: CRT scanlines, bloom, chromatic aberration, glitch
* **Policy**: No layer architecture, manager, or composition UI is to be implemented until sufficient standalone production systems exist.

---

## 17. Tests

Automated test suite `tests/test_vis_001.py` provides 22 dedicated test cases:
* **Deep Field**: registration, live `AudioFrame` consumption, silence drift, beat decay, strong beat bounding, resize safety, isolation from donor/experiment paths.
* **ToroidAMP Floor**: registration, spectral spatial topology mapping, same-BPM spectral differentiation, tile energy decay, wireframe structure, ordinary vs. strong beat distinction, silence dormancy, resize safety, isolation from donor/experiment paths.
* **Selector & Session**: authoritative visualizer ordering (0..3), cycling through all modes, fullscreen palette sync, session index compatibility.
* **Lifecycle**: background/hidden render suspension, RETINA MELT index synchronization.

---

## 18. Human Validation Procedure

To validate VIS-001 in production with live audio:

### Scenario 1 — Deep Field Live Validation
1. Launch ToroidAMP: `python -m toroidamp`
2. Load a variety of tracks (orchestral, metal, electronic, ambient).
3. Switch visualizer mode to `MODE: DEEP FIELD`.
4. Verify:
   - Bass swells push the camera forward smoothly.
   - Mids cause subtle lateral drifting.
   - Treble sparkles add fine detail in far stars.
   - Pausing audio eases the starfield into a slow, calm inertial drift.
   - Resize the VIS module and toggle fullscreen (`⛶ MELT` / ESC) to verify scaling.

### Scenario 2 — ToroidAMP Floor Live Validation
1. Switch visualizer mode to `MODE: TOROIDAMP FLOOR`.
2. Play metal vs. electronic tracks with comparable tempo.
3. Verify:
   - Perspective wireframe provides clear depth and structure.
   - Illuminated tiles fill perspective cells with organic attack/decay glow.
   - Energetic beats trigger propagating wave pulses across the grid.
   - Heavy bass illuminates central core; treble creates peripheral flank accents.
   - Metal and electronic tracks produce visibly distinct tile patterns despite similar BPM.
   - Pausing playback causes tiles to fade smoothly to dormant dim wireframe.

### Scenario 3 — Mode Cycling & Session Persistence
1. Cycle through all modes using the `MODE` button: `3D TOROID` → `WAVEFORM RIBBON` → `DEEP FIELD` → `TOROIDAMP FLOOR` → `3D TOROID`.
2. Select `TOROIDAMP FLOOR` or `DEEP FIELD`, close the application (`✕`).
3. Re-launch the application; confirm the selected mode is restored correctly.

---

## 19. Known Limitations

* **Single Monolithic Render Target**: Visualizers currently render to an offscreen CPU `pygame.Surface` before Qt pixmap transfer. While performant for software rendering (1.2–3.0ms), layered compositing remains deferred.
* **CPU Polygon Fill Scaling**: ToroidAMP Floor's render cost scales with viewport area due to filled polygon rasterization (~2.94ms at 1080p). It operates well within 60 FPS but is a natural future candidate for GPU/shader rendering.

---

## 20. Recommended Next Work

1. **Revisit Matrix Wing Commander**: Recover donor 3D flight paths, depth perspective, and barrel rolls before re-evaluating for production.
2. **Investigate Spectrum Ring / Radial Visualizer**: Author the next candidate exploring circular spectrum envelopes and magma texture physics.
3. **Subtle UI Chassis Breathing**: Implement low-budget audio-reactive lighting on the main chassis window.
