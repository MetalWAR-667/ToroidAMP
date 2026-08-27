# ToroidAMP — EXP-VISLAB-001: GPU Visualizer Authoring Lab (Foundation I)

> **"Can Metal + Jack iterate on GLSL visualizers quickly, visually, and safely without constant code-edit / restart / RETINA MELT cycles?"**

---

## 1. Executive Summary & Authoring Verdict

```text
================================================================================
                    GPU VISUALIZER AUTHORING LAB I VERDICT
================================================================================
                                AUTHORING: PASS
================================================================================
```

* **Core Achievement**: Established the first interactive GPU Visualizer Authoring Lab (`experiments/gpu_visualizers/lab_app.py`) for ToroidAMP.
* **Friction Elimination**: Moving a parameter slider updates the rendered GLSL uniform in the next frame without recompilation or process restart.
* **Three Strict Shader Territories**:
  1. `src/toroidamp/assets/official_shaders/`: Distributed with production ToroidAMP packages (Git tracked).
  2. `experiments/gpu_visualizers/shaders/`: Internal R&D and authoring experiments (Git tracked).
  3. `user_shaders/`: Private local experimentation, third-party experiments (Git ignored via `/user_shaders/`).
* **Audio Synthesis & Telemetry**: Full integration of deterministic synthetic audio profiles (`electronic`, `metal`, `ambient`, `orchestral`, `silence`) with manual impulse triggers (`[ BEAT ]`, `[ STRONG BEAT ]`) and live RMS/band/spectrum telemetry.
* **Failure Isolation**: Syntax or linking errors in user GLSL files are reported via compiler diagnostics while keeping the Lab process, audio state, and previous valid program completely operational.

---

## 2. Three Shader Storage Territories & Git Safety

To protect open-source repository hygiene and prevent inadvertent bundling of third-party shaders:

```text
C:\ToroidAMP\ToroidAMP\
├── src/toroidamp/assets/official_shaders/  <- [OFFICIAL SHADERS] Tracked in Git. Shipped in package.
├── experiments/gpu_visualizers/shaders/    <- [EXPERIMENTAL SHADERS] Tracked in Git. R&D only.
└── user_shaders/                          <- [USER / THIRD-PARTY] IGNORED in Git via /user_shaders/.
```

### Git Safety Policy:
* Root `.gitignore` explicitly ignores `/user_shaders/`.
* Any auxiliary files (`.frag`, `.glsl`, `.txt`, textures, LUTs, authoring notes) placed in `user_shaders/` are invisible to `git status`.
* External shaders loaded via the Lab file dialog are **never** automatically copied into repository paths.

---

## 3. Authoring Lab Architecture & Workspace

Located in `experiments/gpu_visualizers/`:

```text
experiments/gpu_visualizers/
├── shader_compiler.py        # Compiler, parameter metadata extractor, and Shadertoy wrapper
├── lab_app.py                # Standalone PySide6 GPU Visualizer Authoring Lab
├── benchmark.py              # Automated frame timing engine
└── shaders/
    ├── shader_a_plasma.frag    # Cyber Plasma with u_speed, u_warp, u_glow, u_colorShift
    ├── shader_b_raymarch.frag  # 3D Hyper Torus with u_twist, u_radius, u_glowPower, u_ripple
    └── shader_c_shadertoy.frag # Polar Tunnel with u_spokes, u_tunnelSpeed, u_coreScale
```

### UI Workspace Layout:
1. **Top Header**: Composition buttons (`[ 1. CYBER PLASMA ]`, `[ 2. HYPER TORUS ]`, `[ 3. SHADERTOY TUNNEL ]`), `[ 📁 LOAD SHADER... ]`, `[ ⟳ RELOAD (R) ]`, `[ ⚠ BREAK SHADER ]`, and `[ ⛶ FULLSCREEN (F11) ]`.
2. **Left Canvas (Stretch 3)**: High-DPI hardware-accelerated OpenGL 3.3 Core Profile preview canvas.
3. **Right Sidebar (Width 320px)**:
   * **Audio Source Selector**: Switch between synthetic profiles (`electronic`, `metal`, etc.) with live spectrum bar and band meters.
   * **Transient Injections**: Instant `[ ⚡ BEAT ]` and `[ 💥 STRONG BEAT ]` buttons (hotkeys: `SPACE` / `ENTER`).
   * **Exposed Parameters Panel**: Dynamic sliders parsed from shader annotations, plus `[ ↺ RESET ]` button.
4. **Bottom HUD**: Compiler status & error console, active shader classification, frame timing, and resolution.

---

## 4. Parameter Declaration & Uniform Binding Contract

### Parameter Annotation Syntax
Authoring parameters are declared directly in `.frag` / `.glsl` source using clean metadata comments:

```glsl
// [param:float] uniform_name: Display Label = default_val (min_val .. max_val)
```

Example from `shader_b_raymarch.frag`:
```glsl
// [param:float] u_twist: Mesh Twist = 1.0 (0.0 .. 3.0)
// [param:float] u_radius: Base Radius = 1.6 (0.8 .. 3.0)
// [param:float] u_glowPower: Volumetric Halo = 1.0 (0.1 .. 3.0)
// [param:float] u_ripple: Surface Ripple = 1.0 (0.0 .. 4.0)
```

### Automatic Uniform Fallback:
Any unannotated `uniform float taParamName;` is automatically detected with a default span of `0.0 .. 5.0`.

### Lifecycle:
* **Zero Recompilation**: Adjusting a slider calls `canvas.set_param_value(name, val)` which immediately passes the uniform on the next `paintGL()` call.
* **Isolation**: Switching compositions drops old parameter sliders and populates the new shader's parameter set.
* **Reset**: Pressing `[ ↺ RESET ]` restores all parameters to their declared defaults.

---

## 5. Audio Integration: Real & Synthetic Profiles

The Lab supports both live `AudioFrame` streams and deterministic synthetic profiles:

| Profile | Musical Character | Causality & Transients |
| :--- | :--- | :--- |
| **Electronic** | 120 BPM regular four-on-the-floor, build/drop energy arcs | Heavy bass transients on kicks, punchy spectrum |
| **Metal** | Dense midrange, fast 120 BPM kick, sustained high RMS | Fast transient attacks, high frequency jitter |
| **Ambient** | Slow evolving sub-bass, low RMS, sparse beats | Soft drifting movements, gradual color cycles |
| **Orchestral** | Wide dynamic swells (52s cycle), rich midrange | Sparse, dramatic transient impulses |
| **Silence** | Flat zero baseline (`rms=0.0`, `beat=False`) | Validates idle/silence visualizer behavior |

---

## 6. Fullscreen & Reload Workflow

* **Fullscreen Preview (`F11` / `F`)**: Switches the Lab window to full display takeover without recreating context or resetting uniform sliders. Pressing `ESC` or `F11` returns to the authoring UI with all tuned parameter values preserved.
* **External Reload (`R`)**: When an author edits `.frag` code in an external text editor (VS Code, Sublime, etc.), pressing `[ ⟳ RELOAD ]` recompiles the shader immediately.

---

## 7. Performance & Timing Clarification

### Host Submission vs. GPU Completion (Audit Correction):
* In EXP-GL-001, values around `0.018 ms` (~54,000 FPS) represented **CPU-side frame submission time** (`paintGL()` dispatch).
* True GPU pipeline execution at $1920 \times 1080$ Full HD is bounded by GPU rasterization and driver synchronization (~0.5–2.0 ms on modern discrete GPUs, yielding 500–2000 FPS headroom, far surpassing the 60 FPS / 16.6 ms vsync target).
* The Lab status bar explicitly displays **CPU Paint Time (ms)** to ensure accurate technical communication.

---

## 8. Limitations & Recommendations for Foundation II

1. **Parameter Types**: Foundation I deliberately restricts parameters to `float`. Foundation II can evaluate `bool` toggles and `vec3` color pickers.
2. **Preset Export**: Foundation I stores parameter values in active memory. Foundation II should introduce lightweight JSON preset save/load.
3. **No Composition Engine Yet**: Single shader preview is strictly maintained; multi-pass FBO feedback and bloom compositor will be explored in subsequent cuts.
