

## GLITCH-MODE FOR REAGGETON NON FRIENDS... AS ME!

Dembow Pattern Easter Egg — Futuro RhythmAnalyzer capaz de estimar BPM, beat phase, bar phase y persistencia de patrones rítmicos. Si detecta durante suficiente tiempo un patrón dembow-like con alta confianza, activar un easter egg visual progresivo: glitches, RGB split, tearing/feedback y variables absurdas de diagnóstico (RITMO_INFERNAL, PACIENCIA, SEND_HELP, etc.). El análisis debe detectar características rítmicas, no géneros musicales. La lógica humorística pertenece a un EasterEggController, no al analyzer.

Dependency natural: futura Rhythm Analysis Foundation +, para hacerlo gloriosamente cafre, Multipass/Feedback. 😈

dembow_confidence > 0.90
        +
pattern_stability > X seconds
        ↓
    EASTER EGG
        ↓
GLITCH MODE: 

RITMO_INFERNAL = TRUE
PACIENCIA = 17%
ESCAPE_ROUTE = NOT_FOUND
PATTERN_VARIANCE = 0.003
SEND_HELP = TRUE

---

## VISUAL SKINS?... ALMOST ONE

ToroidAMP va a necesitar una skin oficial “Night City Audio Terminal” sólo para estar a la altura del software que ya lleva dentro. XD

Y además ahora sí tendría sentido plantearlo más adelante como un sistema de skins reales, no sólo cambiar cuatro colores:

chasis;
tipografía;
marcos;
HUD;
TUNE/LAB;
paleta reactiva;
quizá presets visuales por skin.

Porque el motor visual ya está bastante por encima del “reproductor con tema oscuro”.

---

## GPU Visualizer — Future Audio Texture Inputs

### Spectrum Texture
Expose the real-time FFT spectrum to GLSL as a GPU texture instead of limiting
audio-reactive shaders to scalar `ta*` uniforms.

Potential uses:
- arbitrary frequency-bin sampling;
- frequency-dependent geometry deformation;
- spectral landscapes;
- equalizer-like procedural structures;
- shader-defined band analysis.

### Waveform Texture
Expose the current PCM waveform / analysis window as a GPU texture.

Potential uses:
- oscilloscopes entirely implemented in GLSL;
- waveform-driven displacement;
- radial waveform geometry;
- temporal interference patterns;
- direct sample-domain visualization.

### iChannel Audio Integration
Explore integration of ToroidAMP audio textures with the future Shadertoy-style
`iChannel0..3` system.

Possible model:

    iChannel0 → static/user texture
    iChannel1 → spectrum texture
    iChannel2 → waveform texture
    iChannel3 → optional future source

Exact channel assignment must NOT be hardcoded yet.

Goal:
Allow advanced external shaders to combine image textures, procedural rendering,
FFT spectrum and waveform data through a familiar Shadertoy-compatible input
model.

Status: FUTURE / DEFERRED

Dependencies:
- GPU-AUDIO-001 scalar Audio Uniform Contract
- future Level 3 iChannel architecture

Explicitly separate from:
- Level 4 multipass / Buffer A/B/C/D
- temporal feedback / ping-pong FBOs

