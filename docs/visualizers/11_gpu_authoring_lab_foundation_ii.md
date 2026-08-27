# ToroidAMP — EXP-VISLAB-003: GPU Visualizer Authoring Lab Foundation II (Controls + Presets)

---

## 1. Executive Summary & Purpose

```text
================================================================================
         GPU VISUALIZER AUTHORING LAB — FOUNDATION II (EXP-VISLAB-003)
================================================================================
STATUS        : FOUNDATION COMPLETE (PASS)
AGENT         : Jack (Demoscene Visual Engineer)
AUTHORING RULE: SHADER  -> Declares what can be tuned (metadata annotations)
                COMPILER-> Extracts metadata & injects typed uniform declarations
                LAB / RM-> Generates typed interactive controls (Sliders, Checkboxes, Color Pickers)
                GPU HOST-> Uploads typed uniforms (glUniform1f, glUniform1i, glUniform3f)
                PRESETS -> Serializes / deserializes known-good tuning snapshots to JSON
================================================================================
```

EXP-VISLAB-003 completes the single-pass authoring workflow for ToroidAMP's GPU visualizer pipeline. It extends the metadata model beyond numeric floats to support **booleans** (`bool`), **hex colors** (`color`), and **portable JSON presets**.

---

## 2. Parameter Declaration Syntax

All parameters are declared as structured comments in the fragment shader source:

```glsl
// Float: min, max, default
// [param:float] u_speed: Evolution Speed = 1.0 (0.1 .. 4.0)
// [param:float] u_warpDepth: Toroidal Warp Depth = 1.2 (0.0 .. 3.0)

// Bool: true/false default
// [param:bool] u_enableDistortion: Enable Harmonic Distortion = true
// [param:bool] u_invertColors: Invert Palette Chromatics = false

// Color: #RRGGBB or #RGB hex default
// [param:color] u_primaryColor: Primary Neon = #00E5FF
// [param:color] u_accentColor: Accent Neon = #FF0077
```

### Compiler & Uniform Injection Contract

| Type | Metadata Declaration | Generated GLSL Uniform | GPU Upload Method | UI Control Widget |
| :--- | :--- | :--- | :--- | :--- |
| `float` | `// [param:float] u_name: Label = 1.0 (0.0..5.0)` | `uniform float u_name;` | `glUniform1f(loc, val)` | `QSlider` + numeric label |
| `bool` | `// [param:bool] u_name: Label = true` | `uniform bool u_name;` | `glUniform1i(loc, 1 or 0)` | `QCheckBox` |
| `color` | `// [param:color] u_name: Label = #00E5FF` | `uniform vec3 u_name;` | `glUniform3f(loc, r, g, b)` | Color swatch `QPushButton` + `QColorDialog` |

---

## 3. JSON Preset Format Specification

Presets are stored as human-readable JSON files:

```json
{
  "format": "toroidamp_shader_preset",
  "version": 1,
  "shader": "cyber_bloom",
  "parameters": {
    "u_speed": 1.4,
    "u_warpDepth": 1.8,
    "u_glowIntensity": 2.2,
    "u_enableDistortion": true,
    "u_invertColors": false,
    "u_primaryColor": "#00E5FF",
    "u_accentColor": "#FF0077"
  }
}
```

### Preset Validation & Forward Tolerance
* **Shader Identity**: If a preset was authored for a different shader, a warning diagnostic is reported in the telemetry panel while compatible parameters are applied.
* **Obsolete Parameters**: Parameters present in the preset but no longer in the shader are ignored without crashing.
* **Missing Parameters**: New parameters declared by the shader but absent from the preset safely retain their declared default values.
* **Clamping**: Numeric float values are strictly clamped to the shader's `[min_value .. max_value]` span.

---

## 4. Canonical Foundation II Example: `Cyber Bloom` (`cyber_bloom.frag`)

Authored directly in [`src/toroidamp/assets/official_shaders/cyber_bloom.frag`](file:///C:/ToroidAMP/ToroidAMP/src/toroidamp/assets/official_shaders/cyber_bloom.frag) as an official reference shader:

* **Audio Uniform Causality**:
  * `taBass`: Drives harmonic radial petal dilation and core torus expansion.
  * `taMids`: Drives rotational coordinate inertia and dynamic wave twist.
  * `taTreble`: Modulates fine interference ripple frequencies.
  * `taBeat` & `taStrongBeat`: Injects transient strobe bursts and shockwave ripples.
* **Silence Baseline**:
  * When audio is paused/silent, `Cyber Bloom` breathes calmly in an elegant dormant rotational drift with zero strobe flashing.

---

## 5. Automated Validation & Test Suite

All 202 tests pass cleanly across the entire codebase ($<3.1\text{ s}$):
* [`tests/test_exp_vislab_003.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_exp_vislab_003.py) (8 tests):
  * `test_typed_metadata_parsing`: Validates float, bool, and color regex parser.
  * `test_color_hex_normalization`: Validates `#RRGGBB` $\rightarrow$ `vec3(0..1)` math.
  * `test_glsl_typed_uniform_declaration_injection`: Validates shader compiler header generation.
  * `test_canvas_typed_param_value_and_reset`: Validates uniform caching and `reset_params()`.
  * `test_preset_serialization_and_deserialization`: Validates full preset save/load roundtrip.
  * `test_preset_forward_tolerance`: Validates handling of unknown/missing keys.
  * `test_canonical_cyber_bloom_reference_shader`: Compiles and tests `cyber_bloom.frag`.
  * `test_user_shaders_git_isolation`: Asserts `user_shaders/` is in `.gitignore`.

---

## 6. Manual Human Validation Protocol (For Metal)

Run the GPU Visualizer Lab:

```powershell
py -3.13 experiments\gpu_visualizers\lab_app.py
```

1. **TEST 1 — TYPED CONTROLS**: Click `★ CYBER BLOOM` -> toggle checkboxes (`Enable Harmonic Distortion`, `Invert Palette Chromatics`), drag float sliders, and click color buttons to pick neon tints -> verify immediate visual update.
2. **TEST 2 — RESET**: Click `↺ RESET` -> verify all controls and uniforms return to declared defaults.
3. **TEST 3 — SAVE & LOAD PRESET**: Tune a wild color/speed combination -> click `⇱ SAVE PRESET` -> change all sliders -> click `⇲ LOAD PRESET` -> verify the exact composition returns instantly.
4. **TEST 4 — AUDIO DYNAMICS**: Change audio profiles (`ELECTRONIC`, `METAL`, `ORCHESTRAL`, `SILENCE`) and click `⚡ BEAT` / `💥 STRONG BEAT` -> verify distinct musical dynamics.
5. **TEST 5 — HOT RELOAD & FAILURE ISOLATION**: Press `R` (hot reload) -> verify parameters survive. Click `⚠ BREAK` -> verify error diagnostic is shown while the previous valid frame stays on screen.
6. **TEST 6 — USER SHADERS & LEVEL-1 COMPATIBILITY**: Click `📁 LOAD SHADER...` and open an unannotated Level-1 Shadertoy `.frag` from `user_shaders/` -> verify it runs seamlessly.

---

## 7. Deferred Level 3 & Level 4 Architectural Boundaries

Explicitly deferred to dedicated future cuts:
* **Level 3**: Multi-channel inputs (`iChannel0..3`), custom static LUT textures, dynamic audio spectrum/waveform textures.
* **Level 4**: Multi-pass FBO pipelines (`Buffer A/B/C/D`), temporal feedback loops, ping-pong framebuffers.
* **Composition Engine**: Multi-shader chaining and keyframe timeline automation.
