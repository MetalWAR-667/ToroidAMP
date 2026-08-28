# GPU-AUDIO-003 — Discovered Parameter Audio Binding (Level C) Experimental Specification

> **Status: CLOSED — HUMAN VALIDATED**
>
> Confirmed in the real Integrated RETINA LAB: the inline AUDIO selector opens, BASS can be
> selected, the parameter binding is visible, audio modulation works, and the shader visibly
> reacts to music. The floating-popup interaction defect (QComboBox, then QPushButton+QMenu —
> both unreliable inside this frameless fullscreen LAB) was fixed by replacing the source picker
> with a non-popup inline selector embedded in the normal QWidget hierarchy (see the "Popup
> Interaction Defect & Fix" section below). The workflow is now promoted to a bundled human-facing
> reference shader — see "Reference Shader & Recommended Mapping" below.

## 1. Executive Summary & Experimental Question

GPU-AUDIO-003 explores Level C parameter reactivity:
> Can ToroidAMP inspect an arbitrary external fragment shader (`.frag`), discover its exposed numeric uniform parameters (both annotated `[param:...]` and unannotated `uniform float u_...`), and allow the user to manually bind real-time musical analysis bands to modulate those parameters?

### Product Hierarchy
- **Level A — Vanilla Fragment**: Unmodified shader, zero reactivity.
- **Level B — AUTO REACT (GPU-AUDIO-002)**: Generic single-pass presentation-level coordinate/exposure modulation.
- **Level C — Discovered Parameter Audio Binding (GPU-AUDIO-003)**: Dynamic uniform discovery with user-configured audio modulation per parameter.
- **Level D — Native `ta*` Authoring (GPU-AUDIO-001)**: Fully authored musical causality inside the GLSL source.

---

## 2. Parameter Discovery & System Exclusions

### A. Discovery Heuristic
- **Annotated Parameters**: Parsed from `// [param:float|bool|color]` comments.
- **Unannotated Uniforms**: Parsed from `uniform float <name>;`.
- **System Uniform Exclusion**: The following system and audio uniforms are strictly excluded from discovery and can never appear as user-bindable parameters:
  - Shadertoy: `iResolution`, `iTime`, `iTimeDelta`, `iFrame`, `iMouse`, `iDate`, `iSampleRate`, `iChannelTime`, `iChannelResolution`.
  - ToroidAMP Core: `u_resolution`, `u_time`, `u_timeDelta`, `u_frame`, `taTexture0`, `taAutoReact`.
  - ToroidAMP Audio: `taRms`, `taPeak`, `taBass`, `taMids`, `taTreble`, `taBeat`, `taStrongBeat`, `taSpectrum`, `taWaveform`, `taBpm`, `taBeatPhase`, `taBarPhase`.

---

## 3. Base Value & Modulation Model

### A. Singular Base Value Ownership
- The base value is owned directly by the existing typed parameter rack (`GLVisualizerCanvas.current_params[name]`).
- Adjusting the parameter slider updates the base value in real-time.
- Audio modulation dynamically modulates around the current base value.

### B. Modulation Formula
$$\text{final\_value} = \text{base\_value} + (\text{audio\_source\_value} \times \text{amount})$$

- **Supported Audio Sources**: `NONE`, `BASS`, `MIDS`, `TREBLE`, `BEAT`, `STRONG BEAT`, `RMS`, `PEAK`.
- **Modulation Amount**: $[-2.00 .. +2.00]$ (supporting both positive and inverted modulation).
- **Default**: `NONE` (0.0 modulation).

### C. Silence Baseline
- At silence, all audio sources fall to $0.0$.
- $\text{final\_value} = \text{base\_value} + (0.0 \times \text{amount}) = \text{base\_value}$.
- No shader freezing or distortion occurs.

---

## 4. Hot Reload & State Isolation

- **Hot Reload (`R`)**: When recompiling a modified shader, existing audio bindings are retained for all surviving parameter names of compatible type (`float`). Removed parameters have their bindings safely pruned.
- **Shader Switching**: Loading a new shader clears previous local bindings.
- **Source Protection**: Zero modifications or writes are made to the shader source file on disk.

---

## 5. Const-Promotion Feasibility Audit (Lightweight Reconnaissance)

### Question: Can `const float FOO = 1.0;` declarations in external shaders be safely promoted to bindable uniforms?
1. **Detection Feasibility**: Regex detection (`const\s+float\s+([a-zA-Z_]\w*)\s*=\s*([0-9.-]+);`) can find top-level constant definitions.
2. **Failure Cases & Risks**:
   - Array sizing expressions: `vec3 items[MAX_COUNT];` requires compile-time constant.
   - Loop bounds: `for(int i=0; i<NUM_LOOPS; i++)` unrolling fails in GLSL ES / strict drivers if modified to dynamic uniform.
   - Const expressions & initializers: `const float B = A * 2.0;` fails if `A` becomes a uniform.
   - Structure definitions and function defaults.
3. **Recommendation**: Keep Level C strictly focused on `uniform float` declarations for now. Const promotion is deferred to a future dedicated experiment (GPU-AUDIO-004) if Level C proves compelling.

---

## 6. Popup Interaction Defect & Fix

Two floating-popup source-selector implementations were tried and both failed real human validation inside the frameless, fullscreen Integrated RETINA LAB:

1. **`QComboBox`**: visible, received focus, but the dropdown itself did not become usable.
2. **`QPushButton` + `QMenu`**: the button received click/focus and changed visual state, but the menu never visibly opened — `AUDIO` stayed at `NONE`.

This was not a `QComboBox`-specific bug — both attempts share the same underlying cause: **floating popup interaction is not sufficiently reliable inside this frameless fullscreen surface.** The fix replaces the source picker with a **non-popup inline selector**: clicking `AUDIO: <source>` expands a small grid of checkable buttons directly inside the same parameter card (normal `QWidget` children of the existing `QScrollArea` content — no `Qt.Popup`, no top-level window, no native menu). Exactly one source selector may be expanded at a time across the LAB; selecting a source collapses it immediately. This is now the **one interaction model** for AUDIO source selection in both the Integrated LAB (`src/toroidamp/ui/fullscreen.py`) and the Standalone GPU Lab (`experiments/gpu_visualizers/lab_app.py`).

---

## 7. Reference Shader & Recommended Mapping

The deterministic regression fixture (`user_shaders/test_discovered_params.frag`) remains exactly that — a minimal, test-only fixture that several automated tests depend on by name. It was **not** replaced or turned into production content.

A separate, human-facing bundled reference shader was added instead:

```text
src/toroidamp/assets/official_shaders/audio_reactive_reference.frag
```

alongside the existing bundled reference shaders (`minimal_reference.frag`, `cyber_bloom.frag`, `toroid_identity.frag`), following the same `// [param:float] name: Label = default (min .. max)` annotation convention. It exposes five float parameters, each with a single, clearly legible visual effect:

| Parameter | Default | Range | Visual effect |
|---|---|---|---|
| `u_zoom` | 1.0 | 0.3 .. 3.0 | Scales the sampled coordinate space — clear zoom/breathing |
| `u_speed` | 1.0 | 0.0 .. 4.0 | Scales the time term driving every animated element — at 0.0 the field freezes, confirming it's the sole motion driver |
| `u_glow` | 1.5 | 0.2 .. 4.0 | Scales core + edge glow terms only — pure luminous intensity, no shape/motion change |
| `u_twist` | 1.0 | 0.0 .. 3.0 | Bends the angular coordinate proportional to radius — winds the petal pattern into a spiral; 0.0 = perfectly radial |
| `u_detail` | 6.0 | 2.0 .. 16.0 | Sets petal/spoke frequency — low = few broad lobes, high = a dense fan of thin spokes |

**The shader's own GLSL source contains zero `ta*` audio-uniform references** — no `taBass`, `taBeat`, or any other musical-analysis uniform. It is deliberately musically neutral: its parameters only become audio-reactive once a human assigns an AUDIO source through the LAB's inline selector. This is what makes it a genuine demonstration of *discovered-parameter* binding rather than *native authoring*.

### Validated Workflow

```text
load shader
   -> discovered float parameter (u_zoom / u_speed / u_glow / u_twist / u_detail)
   -> BASE (typed parameter rack, existing slider)
   -> AUDIO source (inline selector — NONE/BASS/MIDS/TREBLE/BEAT/STRONG BEAT/RMS/PEAK)
   -> AMOUNT (-2.00 .. +2.00)
   -> live modulation: final_value = base_value + (audio_source_value * amount)
```

### Recommended Demonstration Mapping

Verified visually against the reference shader (amounts chosen to read clearly without overdriving):

```text
u_zoom  <- BASS         amount +0.60   (breathing scale pulse on kick)
u_glow  <- BEAT         amount +1.20   (luminous flash on transient)
u_twist <- MIDS         amount +1.00   (spiral deformation tracking vocal/lead presence)
```

`u_speed` and `u_detail` are intentionally left unbound in the recommended mapping — both read clearly under **manual** BASE adjustment (speed=0 visibly freezes the field; detail sweeps from a few lobes to a dense fan), which is itself part of demonstrating that BASE, AUDIO, and AMOUNT are three independent, composable controls.

### Three Distinct Reactivity Paths

GPU-AUDIO-003 sits alongside two other, structurally different reactivity mechanisms — worth stating explicitly since all three coexist in the same LAB:

1. **Native `ta*` authoring** (GPU-AUDIO-001) — the shader author writes `taBass`/`taBeat`/etc. directly into the GLSL source. Musical causality is fixed at authoring time. Demonstrated by `minimal_reference.frag` and `cyber_bloom.frag`.
2. **Discovered parameter binding — Level C** (GPU-AUDIO-003, this document) — the shader exposes plain `uniform float` parameters with no knowledge of audio at all; a human assigns `source + amount` per parameter at runtime through the LAB. Demonstrated by `audio_reactive_reference.frag`.
3. **AUTO REACT — Level B** (GPU-AUDIO-002) — a generic, shader-agnostic presentation-layer modulation (coordinate/exposure) applied uniformly regardless of what the shader exposes; no per-parameter binding at all.

These are independent: AUTO REACT OFF with a parameter's AUDIO source set to `NONE` leaves that parameter driven purely by its BASE slider; only parameters with an explicitly assigned source respond to music.

---

## 8. Regression Verification

Confirmed after promoting the reference shader:
- All prior GPU-AUDIO-003 tests remain green (system-uniform exclusion, binding get/set, silence identity, modulation computation, base-value adjustment, LAB card construction, inline-selector click/select/collapse, single-selector-open-at-a-time, toggle-collapse, hot-reload preservation, critical human-path regression, obsolete-popup-code guards).
- `audio_reactive_reference.frag` compiles and its metadata discovers exactly the five intended float parameters, with no `SYSTEM_UNIFORMS` leakage.
- The reference shader's raw GLSL code (excluding documentation comments) contains no `ta*` uniform reference, confirmed by a dedicated test.
- Audio binding + silence-return-to-base verified against the reference shader specifically, not only the regression fixture.
- `user_shaders/test_discovered_params.frag` is untouched and still the fixture the pre-existing tests load by name.
