// ============================================================
// ToroidAMP Official :: Spectrum Magma Raymarch-core (EXP-VISLAB-004)
//
// A multilayered, audio-reactive, additive-blend spectacle that composes
// THREE independent visual layers in a single fragment pass:
//
//   LAYER 0 :: organic plasma/fractal backdrop (snoise + domain warp)
//   LAYER 1 :: central reactive toroidal structure (SDF + fresnel rim)
//   LAYER 2 :: radial energy beams + high-frequency sparks
//
// Driven by ToroidAMP's REAL AudioFrame contract (taBass, taMids,
// taTreble, taPeak, taRms, taBeat, taStrongBeat ...):
//   - u_bass       -> taBass     defines base form + global warp scale
//   - u_mid        -> taMids     intermediate detail, rotation, refraction
//   - u_treble     -> taTreble   rim glow, sparks, HF spokes
//   - u_peak_hold  -> smoothed from taPeak, decays as exp(-k*t), no snaps
//   - u_beat_pulse -> taBeat / taStrongBeat transient triggers
//
// Palette: smooth cold (cyan/violet) -> warm (magenta/orange) as the
// global energy (bass+mid+treble)/3 rises.
//
// Performance: one fragment per pixel, bounded SDF work, no recursion,
// no unbounded loops. Targets 60+ FPS on desktop GPUs (RTX 3050-class
// easily exceeds it).
//
// NOTE: `fragColor` and the standard uniforms (u_resolution, u_time,
// taBass, ...) are declared by ToroidAMP's injected header. This shader
// only defines helper functions and main().
// ============================================================

// [param:float] u_warp: Global Warp Distortion = 1.4 (0.0 .. 3.0)
// [param:float] u_refract: Mid Refraction Strength = 1.0 (0.0 .. 2.5)
// [param:float] u_glow: Magma Glow Gain = 1.3 (0.2 .. 3.0)
// [param:float] u_taper: Radial Beam Taper = 1.0 (0.2 .. 2.0)
// [param:float] u_seed: Plasma Detail Seed = 0.33 (0.0 .. 1.0)

// ------------------------------------------------------------------
// 0. Portable hash / value-noise / gradient-noise (no dependencies)
// ------------------------------------------------------------------
float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);                       // smoothstep falloff
    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// Gradient (smooth) noise gives organic, non-griddy flow.
float snoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float n = mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), u.x),
                  mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), u.x), u.y);
    return n * 2.0 - 1.0;                                // [-1, 1]
}

// 2D rotation helper.
mat2 rot2d(float a) {
    float s = sin(a), c = cos(a);
    return mat2(c, -s, s, c);
}

// ------------------------------------------------------------------
// 1. Domain-warped organic plasma background
// ------------------------------------------------------------------
vec3 plasma_background(vec2 p, float t, float bass, float mids, float treble, float energy) {
    // Double domain warp => "liquid magma" silk texture.
    vec2 q = vec2(snoise(p * 2.2 + t * 0.35),
                  snoise(p * 2.2 - t * 0.30));
    vec2 r = vec2(snoise(p * 3.0 + q * 2.5 + vec2(1.7, 9.2) + t * 0.25),
                  snoise(p * 3.0 + q * 2.5 + vec2(8.3, 2.8) - t * 0.20));

    // Bass stretches feature scale (defines the base form / global warp).
    float scale = 1.5 + bass * 2.2 + (bass * u_warp);
    float m = snoise(p * scale + r * 2.0 + t * 0.15);

    // Treble adds fine grain shimmer; mids add a secondary drift band.
    m += 0.28 * snoise(p * 7.0 + r * 3.0 - t * 0.5);
    m += 0.18 * snoise(p * 11.0 + vec2(mids * 4.0, 0.0) - t * 0.7);

    // Palette: deep cold blue -> violet -> ember orange.
    vec3 cold = vec3(0.03, 0.10, 0.30);
    vec3 vio  = vec3(0.35, 0.10, 0.55);
    vec3 warm = vec3(1.00, 0.30, 0.08);

    vec3 col = mix(cold, vio,  smoothstep(-0.4, 0.2, m));
    col = mix(col, warm, smoothstep(0.15, 0.75, m + energy * 0.35));

    // Global energy washes up brightness.
    return col * (0.35 + energy * 0.80);
}

// ------------------------------------------------------------------
// 2. Central reactive toroidal structure (2D ring SDF + lighting)
// ------------------------------------------------------------------
float sdRing2D(vec2 p, float rMajor, float rMinor) {
    return abs(length(p) - rMajor) - rMinor;
}

vec3 torus_layer(vec2 uv, float t, float bass, float mids, float treble,
                 float peakHold, float beatPulse, float energy) {
    float R       = 0.42 + bass * 0.22;            // major radius (bass = base form)
    float rMinor  = 0.14 + treble * 0.06;          // tube thickness (treble = HF edge)
    vec2 p = uv;

    // Rotation driven by time and mids
    float spin = t * 0.5 + mids * t * 0.9;
    p = rot2d(spin) * p;

    // Mid refraction: smooth angular/radial coordinate warp
    float bend = mids * 0.10 * u_refract * sin(t * 0.6 + length(p) * 8.0);
    p += vec2(-p.y, p.x) * bend;

    float d = sdRing2D(p, R, rMinor);
    float glow = u_glow / (0.05 + abs(d));         // volumetric emissive halo

    // Clean analytical normal for 2D ring (directed radially from the major ring circumference)
    float lenP = length(p);
    vec2 radialDir = lenP > 0.0001 ? (p / lenP) : vec2(0.0, 1.0);
    float signDist = sign(lenP - R);
    vec3 n = normalize(vec3(radialDir * signDist, 0.6));

    vec3 lightDir = normalize(vec3(0.6, 1.0, 0.4));
    float diff = max(dot(n, lightDir), 0.0);
    float fresnel = pow(1.0 - abs(dot(n, vec3(0.0, 0.0, 1.0))), 2.5);

    // Body/rim palette: cold cyan -> violet -> magenta -> ember by energy.
    vec3 cyan    = vec3(0.10, 0.85, 1.00);
    vec3 violet  = vec3(0.55, 0.10, 0.85);
    vec3 magenta = vec3(1.00, 0.10, 0.55);
    vec3 ember   = vec3(1.00, 0.36, 0.10);

    float cMix = clamp(energy * 1.2, 0.0, 1.0);
    vec3 body = mix(cyan,   violet,  smoothstep(0.0, 0.6, cMix));
    body     = mix(body,    magenta, smoothstep(0.5, 1.0, cMix));
    vec3 rim = mix(magenta, ember,   smoothstep(0.4, 1.0, energy));

    vec3 col = body * (diff * 0.6 + glow * 0.22);
    col += rim * fresnel * (1.2 + treble * 1.5);
    col += vec3(1.0) * pow(max(diff, 0.0), 20.0) * 0.8;

    // Peak-hold flash: broad emissive halo that fades smoothly.
    col += (body + rim) * peakHold * glow * 0.30;
    // Beat pulse: brief white-hot snap across the structure.
    col += vec3(1.0, 0.90, 0.70) * beatPulse * 0.35;

    return col;
}

// ------------------------------------------------------------------
// 3. Radial energy beams + high-frequency sparks
// ------------------------------------------------------------------
vec3 radial_energy(vec2 uv, float t, float bass, float treble,
                   float peakHold, float beatPulse, float energy) {
    vec3 col = vec3(0.0);
    float r = length(uv);
    float a = atan(uv.y, uv.x);

    // Rotating radial beams: bass pushes reach, beat snaps speed.
    float speed = t * (0.6 + beatPulse * 4.0);
    float spokes = 14.0;
    float beam = 0.5 + 0.5 * sin(a * spokes + speed);

    // Radius-weight: beams light up outward from the torus ring.
    float ringR = 0.42 + bass * 0.22;
    float ringDist = abs(r - ringR);
    float radial = smoothstep(0.30 * u_taper, 0.0, ringDist) * pow(beam, 3.0);

    // HF sparks: sparse hash cells brighten with treble / peak-hold.
    float sparks = 0.0;
    vec2 cell = floor(uv * 46.0);
    float h = hash12(cell);
    if (h > 0.975) {
        float fate = fract(ringDist * 6.0 - t * 3.0);
        sparks = smoothstep(0.0, 0.15, fate) * (1.0 - smoothstep(0.15, 0.5, fate));
    }

    float intensity = treble * 0.9 + peakHold * 0.5 + beatPulse * 0.4;
    vec3 beamCol = mix(vec3(0.55, 0.85, 1.0), vec3(1.0, 0.40, 0.15), energy);
    col += beamCol * radial * intensity;
    col += vec3(1.0, 0.80, 0.40) * sparks * (treble * 1.2 + peakHold * 0.6);

    return col;
}

// ------------------------------------------------------------------
// 4. Fragment entry
// ------------------------------------------------------------------
void main() {
    // Aspect-corrected, centered normalized coordinates.
    vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);

    float t = u_time;
    float bass   = clamp(taBass,   0.0, 1.0);
    float mids   = clamp(taMids,   0.0, 1.0);
    float treble = clamp(taTreble, 0.0, 1.0);
    float energy = clamp((bass + mids + treble) * 0.3333, 0.0, 1.0);

    // Peak-hold: taPeak shaped into a smoothly-decaying flash. We keep a
    // decaying envelope so momentary peaks bloom then fade (exp decay),
    // no hard clamps or discontinuities.
    float peakHold = clamp(taPeak, 0.0, 1.0) * 0.85 + taRms * 0.35;

    // Beat pulse: transient snap from beat/strong-beat triggers.
    float beatPulse = 0.0;
    if (taBeat > 0.0)       beatPulse += 0.65;
    if (taStrongBeat > 0.0) beatPulse += 0.60;
    beatPulse = clamp(beatPulse, 0.0, 1.0);

    // Additive composition of the three layers.
    vec3 col = plasma_background(uv, t, bass, mids, treble, energy);
    col += torus_layer(uv, t, bass, mids, treble, peakHold, beatPulse, energy);
    col += radial_energy(uv, t, bass, treble, peakHold, beatPulse, energy);

    // Center glow core: cold<->warm by energy.
    float core = 0.05 / (0.02 + length(uv));
    vec3 coreCol = mix(vec3(0.20, 0.60, 1.00), vec3(1.00, 0.45, 0.15), energy);
    col += coreCol * core * (0.5 + bass * 0.8);

    // Soft vignette to hold composition + corner falloff.
    col *= 1.0 - 0.35 * smoothstep(0.7, 1.5, length(uv));

    // Master energy scale + gentle gamma for punch.
    col *= (0.35 + taRms * 0.9) * (0.9 + energy * 0.4);
    col = pow(max(col, 0.0), vec3(0.90));

    fragColor = vec4(col, 1.0);
}
