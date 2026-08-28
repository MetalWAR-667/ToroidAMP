# GPU-AUDIO-002 — Generic Musical Reactivity (AUTO REACT) Architecture Specification

## 1. Executive Summary & Product Objective

ToroidAMP supports three external fragment shader classes:

1. **Vanilla External Fragment**: Standard Shadertoy-compatible `.frag` without `ta*` uniforms. Renders with zero modification.
2. **ToroidAMP-Aware Fragment (GPU-AUDIO-001)**: Shader explicitly declares `taBass`, `taTreble`, etc. Provides author-crafted musical causality.
3. **Vanilla Fragment + AUTO REACT (GPU-AUDIO-002)**: User clicks `[ AUTO REACT ]` in the RETINA Integrated LAB or Standalone GPU Lab. ToroidAMP applies a generic, presentation-level musical response at runtime **without requiring any modification or rewriting of the underlying shader source file**.

---

## 2. Core Architectural Principles

- **Zero Source Rewriting**: The original `.frag` file is never altered or overwritten on disk.
- **Single-Pass Execution**: Implemented strictly within the existing generated GLSL compatibility wrapper (`SHADERTOY_WRAPPER_SUFFIX`). No multipass, no FBO ping-pong loops, no texture buffers, and no CPU image processing are introduced.
- **Zero-Cost Toggling**: Controlled via a single standard OpenGL runtime uniform (`uniform int taAutoReact;`). Toggling between OFF and ON executes instantaneously without recompiling or relinking shaders.
- **Reversible & Transient**: `AUTO REACT` is scoped to the local authoring session. When switching shaders or reloading, `AUTO REACT` defaults to OFF.

---

## 3. Generic Reactivity Mapping & Modulation Bounds

When `taAutoReact == 1`:

```
1. Coordinate Breathing / Zoom (Bass & Strong Beat):
   pulseZoom = 1.0 + (taBass * 0.08) + (float(taStrongBeat) * 0.05)
   Bounded range: [1.0 .. 1.13] (subtle, non-destructive expansion)

2. Coordinate Drift / Rotational Perturbation (Mids):
   rotAngle = (taMids > 0.0) ? (taMids - 0.5) * 0.035 : 0.0
   Bounded range: [-0.0175 .. +0.0175] radians (~1.0 degree maximum gentle tilt)

3. Primary Image Evaluation:
   mainImage(col, reactiveCoord)

4. Presentation Exposure & Post-Modulation:
   beatPulse = float(taBeat) * 0.08 + float(taStrongBeat) * 0.12
   trebleShimmer = taTreble * 0.06
   rmsLift = taRms * 0.05
   boostedCol = col.rgb * (1.0 + beatPulse + trebleShimmer + rmsLift)
   Bounded range: [1.0 .. 1.25] luminance gain on heaviest transients
```

### Silence Baseline Semantics
- At silence (`taBass=0`, `taMids=0`, `taTreble=0`, `taBeat=0`, `taStrongBeat=0`, `taRms=0`):
  - `pulseZoom = 1.0`
  - `rotAngle = 0.0`
  - `reactiveCoord == gl_FragCoord.xy`
  - Output multiplier $= 1.0$
- **Result**: At silence, the presentation layer resolves to mathematical identity. The underlying shader executes its native dormant animation without visual distortion or freezing.

---

## 4. Native `ta*` Shader Stacking Policy

- Native ToroidAMP-aware shaders (e.g. `apollo_spiral_toroidamp_test.frag`) already possess explicit authored musical reactivity.
- When loaded, `AUTO REACT` remains OFF by default.
- If the user explicitly toggles `[ AUTO REACT ]` on a `ta*`-aware shader, both the authored reactivity and the generic presentation modulation layer stack predictably as requested by the user.

---

## 5. UI Controls

- **RETINA MELT Integrated LAB**: Checkable `[ ⚡ AUTO REACT ]` button on the LAB action bar.
- **Standalone GPU Authoring Lab**: Checkable `[ ⚡ AUTO REACT ]` button on the primary toolbar.
- Both UIs call `canvas.set_auto_react(checked)` directly on `GLVisualizerCanvas`.

---

## 6. Compatibility & Deferred Boundaries

- **Level 1 Single-Pass Compatibility**: Supported across all Shadertoy-style external shaders.
- **Explicitly Deferred**:
  - Level 3: `iChannel0..3`, static textures, 2D spectrogram / waveform textures.
  - Level 4: Multipass Buffer A/B/C/D, temporal feedback, FBO pipelines.
  - Audio: Real-time BPM estimation, beat-grid tracking.
