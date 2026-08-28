# GPU-AUDIO-001 — External Fragment Shader Musical Reactivity Foundation Specification

## 1. Executive Summary & Core Principle

GPU-AUDIO-001 formalizes and documents ToroidAMP's canonical external fragment shader musical uniform contract.

### The Authoritative Principle
> **ToroidAMP provides the musical data.**
> **The shader decides how to interpret it.**
> 
> "Auto-reactivity" in ToroidAMP strictly means **Automatic Uniform Binding**, NOT arbitrary automatic coordinate warps, brightness flashes, or artificial scene deformations.

---

## 2. Canonical ToroidAMP Audio Uniform Contract

Any external or local GLSL fragment shader (`.frag` / `.glsl`) loaded via RETINA MELT Shader Lab or Standalone GPU Lab can declare any subset of the following uniforms:

| Uniform Name | GLSL Type | Range / Semantics | Musical Description |
| :--- | :--- | :--- | :--- |
| `taBass` | `float` | `0.0 .. 1.0` | Sub & bass band energy (20 – 250 Hz) |
| `taMids` | `float` | `0.0 .. 1.0` | Midrange harmonic band energy (250 – 4000 Hz) |
| `taTreble` | `float` | `0.0 .. 1.0` | High-frequency shimmer band energy (4000 – 20000 Hz) |
| `taBeat` | `int` or `float` | `0` or `1` (`0.0` or `1.0`) | Dynamic general musical beat transient trigger |
| `taStrongBeat` | `int` or `float` | `0` or `1` (`0.0` or `1.0`) | Heavy low-end kick / transient trigger |
| `taRms` | `float` | `0.0 .. 1.0` | Normalized RMS overall energy envelope |
| `taPeak` | `float` | `0.0 .. 1.0` | Instantaneous peak sample magnitude |
| `taSpectrum` | `float[64]` | `0.0 .. 1.0` | 64-bin normalized log-spaced spectral amplitudes |
| `taWaveform` | `float[128]` | `-1.0 .. 1.0` | 128 normalized time-domain PCM waveform samples |
| `taBpm` | `float` | Reference BPM | Approximate track tempo (default `130.0`) |
| `taBeatPhase` | `float` | `0.0 .. 1.0` | Continuous cyclic quarter-note phase ramp |
| `taBarPhase` | `float` | `0.0 .. 1.0` | Continuous cyclic 4-bar measure phase ramp |

---

## 3. Opt-in and Optional Uniform Semantics

1. **Zero Required Uniforms**: Every audio uniform is 100% optional.
2. **Vanilla Compatibility**: Standard Shadertoy-style shaders (e.g. `mainImage` with only `iResolution` / `iTime`) declare zero `ta*` uniforms, compile without modification, and render identically without any unintended visual distortion.
3. **Selective Opt-In**: A shader can declare only `taBass`, or `taBass` and `taTreble`, or all uniforms.
4. **Harmless Unused Uniforms**: Declared uniforms that are optimized out by the GPU compiler or omitted by the author do not cause compile errors or runtime warnings.

---

## 4. Pipeline & Value Transport

```
Decoded Playback PCM (or Lab Synthetic Profile)
              ↓
  AnalysisHandoff (AudioFrame)
              ↓
  GLVisualizerCanvas.update_audio_frame(frame)
              ↓
  GLVisualizerCanvas.paintGL()
              ↓
  Introspected Uniform Upload (glUniform1f / glUniform1i / glUniform1fv)
              ↓
  GPU Fragment Shader execution
```

### Silence Baseline Semantics
- At silence / pause / stop:
  - Amplitude uniforms (`taBass`, `taMids`, `taTreble`, `taRms`, `taPeak`) fall to `0.0`.
  - Triggers (`taBeat`, `taStrongBeat`) fall to `0`.
  - Spectrum and Waveform buffers fall to all zeros.
- **Shader Animation Remains Alive**: `iTime`, `u_time`, and `iFrame` continue to increment continuously. Shaders enter their authored dormant/calm state rather than freezing.

---

## 5. Shader Authoring Guide & Minimal Example

### Minimal Reactive Shadertoy-Style Shader
```glsl
// Optional authoring parameters
// [param:float] u_speed: Evolution Speed = 1.0 (0.1 .. 3.0)
// [param:float] u_bassWarp: Bass Amplitude = 1.5 (0.0 .. 4.0)

uniform float taBass;
uniform float taTreble;
uniform int taBeat;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / min(iResolution.x, iResolution.y);
    float r = length(uv);
    
    // Musical causality
    float pulse = 1.0 + taBass * 0.3 * u_bassWarp;
    float ring = sin(r * 18.0 * pulse - iTime * 2.0 * u_speed);
    
    vec3 col = mix(vec3(0.0, 0.9, 1.0), vec3(1.0, 0.0, 0.5), 0.5 + 0.5 * ring);
    
    // Beat transient flash
    if (taBeat > 0) {
        col += vec3(0.25, 0.1, 0.3);
    }
    
    fragColor = vec4(col, 1.0);
}
```

---

## 6. Future Extension Boundaries (Deferred)

- **Level 3 (iChannel0..3, texture buffers, 2D spectrogram textures)**: Strictly deferred.
- **Level 4 (Multipass Buffer A/B/C/D, temporal feedback, FBO pipelines)**: Strictly deferred.
- Current scope is strictly Level 1 single-pass fragment execution with typed parameters and AudioFrame uniform binding.
