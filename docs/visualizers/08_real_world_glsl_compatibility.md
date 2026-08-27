# ToroidAMP — EXP-VISLAB-002: Real-World External GLSL Compatibility Gate

> **"Does our Level-1 Shadertoy-style compatibility model survive contact with real shaders we did not author? And what actual friction does Metal encounter when using the Lab as a shader playground?"**

---

## 1. Executive Summary & Compatibility Verdict

```text
================================================================================
           REAL-WORLD EXTERNAL GLSL COMPATIBILITY GATE VERDICT
================================================================================
                       LEVEL-1 COMPATIBILITY: PASS
================================================================================
```

* **Tested Real-World Shader Files** (placed in local `user_shaders/` by Metal):
  1. `apollo_spiral.frag`: Complex Apollonian 3D fractal raymarcher with `tanh()` tonemapping, depth-based channel pow colorization, and matrix rotation swizzling.
  2. `happy_glow_cruise.frag`: 3D Menger fractal volumetric glow raymarcher with preprocessor macros and tangent-modulated camera trajectories.
  3. `Rig_Rekt.frag`: Raymarched recursive box tunnel with multiple noise frequency octaves and exponential attenuation.
* **Compatibility Result**: **100% (3/3) compiled and rendered UNMODIFIED** under the Level-1 single-pass wrapper (`void mainImage(out vec4, in vec2)` + `iResolution` + `iTime`).
* **Fullscreen (1920×1080)**: All three shaders scaled to native Full HD without shader restart, context drops, or resolution distortion.
* **Audio Adaptation Experiment**: Created `user_shaders/apollo_spiral_toroidamp_test.frag` demonstrating authentic demoscene musical causality (`taBass` $\to$ fractal scale dilation, `taMids` $\to$ rotational twist velocity, `taTreble` $\to$ chromatic split, `taBeat` $\to$ step displacement).

---

## 2. Compatibility Matrix

| Candidate Shader | Interface | External Resources | Compilation | Visual Render | Target Level | Notes / Idioms |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **`apollo_spiral.frag`** | `mainImage(out, in)` | None | **PASS** | **PASS** | **Level 1** | Uses `mat2(cos(...))` swizzle, comma loops, `tanh()` tonemapping. Ran unmodified. |
| **`happy_glow_cruise.frag`** | `mainImage(out, in)` | None | **PASS** | **PASS** | **Level 1** | Heavy nested macros, `tanh()` tonemapping. Ran unmodified. |
| **`Rig_Rekt.frag`** | `mainImage(out, in)` | None | **PASS** | **PASS** | **Level 1** | Nested loops, `vec3 p = iResolution;` aliasing. Ran unmodified. |
| **`test_user_spiral.frag`** | `mainImage(out, in)` | None | **PASS** | **PASS** | **Level 1** | Level 1 with `// [param:float]` annotations. Ran unmodified. |

*Host adaptation required*: **None**. The Level-1 wrapper architecture established in EXP-GL-001 / VISLAB-001 handled all real-world GLSL idioms out-of-the-box.

---

## 3. GLSL Dialect & Compiler Observations

The probe subjected ToroidAMP's OpenGL 3.3 Core Profile pipeline to authentic demoscene GLSL coding patterns:

1. **Matrix Rotation Trigonometric Swizzles (`mat2(cos(a + vec4(0,33,11,0)))`)**:
   * *Observation*: Common compact rotation trick in demoscene shaders. Compiles cleanly on standard OpenGL 3.3 compilers without warning.
2. **Aggressive Comma Expressions in `for` loops (`for(p=...; ...; p.xy*=..., s=...)`)**:
   * *Observation*: Valid GLSL 3.30 syntax; parsed and executed accurately by the host shader pipeline.
3. **Hyperbolic Tangent Tonemapping (`tanh(...)`)**:
   * *Observation*: Fully supported in GLSL 330 core. Eliminates harsh clamping in HDR raymarchers.
4. **Resolution Assignment Aliasing (`vec3 p = iResolution; u = (u - p.xy*0.5)/p.y;`)**:
   * *Observation*: Relies on `iResolution` being `vec3` (width, height, pixel_aspect). Our wrapper's `uniform vec3 iResolution;` satisfied this assumption completely.

---

## 4. Musical Causality & Adaptation Experiment

To validate how easily external shaders can be upgraded into reactive ToroidAMP visualizers, Jack adapted `apollo_spiral.frag` into `user_shaders/apollo_spiral_toroidamp_test.frag`:

```text
Original External Shader ──► Add AudioFrame Mappings ──► Declare Authoring Sliders
```

### Causality Mappings Implemented:
* **`taBass` $\to$ Apollonian Fractal Scale**: Expands the recursive inversion sphere ($2.0 + 0.4 \times \text{bass} \times u\_bassScale$), causing the fractal lattice to breathe with kicks.
* **`taMids` $\to$ Z-Axis Twist & Flow**: Accelerates coordinate rotational velocity ($0.05 t + 0.8 \times \text{mids}$), warping the geometry during dense musical passages.
* **`taTreble` $\to$ Chromatic Dispersion**: Modulates the exponent vector `vec4(1.0, 2.0 + taTreble*2.0, 12.0 - taBass*4.0, 0.0)` to split glowing cyan/magenta halos on hi-hats.
* **`taBeat` $\to$ Step Displacement**: Injects transient noise perturbation during beat transients.
* **`taStrongBeat` $\to$ Hyper-Illumination**: Momentarily boosts central core brightness by $2\times$.

---

## 5. Actual Authoring Friction & Evidence for Foundation II

During real-world testing with local shaders, the following actual authoring friction was recorded:

1. **Parameter Preset Persistence (Friction)**:
   * *Observation*: When tuning parameters (`u_bassScale`, `u_iterCount`, `u_glow`), switching compositions or reloading resets active slider positions unless re-entered manually.
   * *Foundation II Recommendation*: Implement lightweight JSON session presets (`Save Preset` / `Load Preset`).
2. **Color Palette Controls (Friction)**:
   * *Observation*: Adapting shaders often requires adjusting base and accent hues. Hardcoding `vec3(1.0, 0.2, 0.7)` in GLSL required code edits.
   * *Foundation II Recommendation*: Add `// [param:color]` annotation mapped to a Qt color picker button.
3. **Toggle Flags (Friction)**:
   * *Observation*: Enabling/disabling noise octaves or wireframe overlays is cumbersome with `float` sliders.
   * *Foundation II Recommendation*: Add `// [param:bool]` annotation mapped to a `QCheckBox`.
4. **No Higher-Level Channel Support (Boundary Validation)**:
   * *Observation*: Single-pass procedural shaders represent a massive fraction of visualizers, but shaders requiring noise LUT textures (`iChannel0`) are currently unsupported.
   * *Foundation II Recommendation*: Keep Level 1/2 as baseline; design Level 3 (`iChannel` static textures / noise LUTs) as an explicit next milestone.

---

## 6. Git Safety & Testing
* **Git Safety**: All external and adapted test shaders remain inside `user_shaders/` and are ignored by Git. No third-party code entered repository tracking.
* **Automated Tests**: Added [`tests/test_exp_vislab_002.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_exp_vislab_002.py) verifying classification, macro wrapper generation, channel detection heuristics, and audio injection. 18 experimental tests passing in 0.005s.
* **Operational Status**: `CURRENT_STATE_UPDATE: NOT_REQUIRED`. No production files modified; no git commits.
