// ============================================================
// ToroidAMP Official Reference :: Audio-Reactive Discovery Demo (GPU-AUDIO-003)
// Author: ToroidAMP Team
// License: MIT
//
// Purpose:
//   Human-facing LAB reference shader demonstrating ToroidAMP's
//   DISCOVERED-PARAMETER audio binding workflow (Level C). This shader
//   is deliberately musically NEUTRAL — it contains no taBass/taMids/
//   taBeat/etc. references at all. Its exposed float uniforms only
//   become audio-reactive when a human assigns an AUDIO source to
//   them through the LAB's inline selector (base + audio*amount).
//
//   This is intentionally different from cyber_bloom.frag /
//   minimal_reference.frag, which demonstrate NATIVE ta* authoring
//   (musical causality baked directly into the GLSL by the author).
//   Three distinct ToroidAMP reactivity paths exist:
//     1. Native ta* authoring      — this shader's siblings
//     2. Discovered parameter bind — THIS shader (GPU-AUDIO-003)
//     3. AUTO REACT                — generic presentation-layer only
//
// Workflow:
//   LOAD IN LAB -> ASSIGN AUDIO SOURCES TO u_zoom/u_speed/u_glow/... -> LISTEN
//
// Recommended demonstration mapping (verify visually, tune to taste):
//   u_zoom  <- BASS   amount +0.60   (breathing scale pulse on kick)
//   u_glow  <- BEAT   amount +1.20   (luminous flash on transient)
//   u_twist <- MIDS   amount +1.00   (spiral deformation with vocal/lead presence)
// ============================================================

// [param:float] u_zoom: Zoom = 1.0 (0.3 .. 3.0)
// [param:float] u_speed: Speed = 1.0 (0.0 .. 4.0)
// [param:float] u_glow: Glow = 1.5 (0.2 .. 4.0)
// [param:float] u_twist: Twist = 1.0 (0.0 .. 3.0)
// [param:float] u_detail: Detail = 6.0 (2.0 .. 16.0)

void main() {
    // Aspect-safe UV coordinates centered at (0, 0) — u_zoom directly
    // scales the sampled coordinate space (smaller p = more magnified).
    vec2 p = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    p /= max(0.05, u_zoom);

    float r = length(p);
    float a = atan(p.y, p.x);

    // u_speed scales the rate of every time-driven term below — at 0.0
    // the whole field freezes, confirming it (and only it) drives motion.
    float t = u_time * u_speed;

    // u_twist bends the angular coordinate proportionally to radius,
    // winding the petal field into a spiral. At 0.0 the petals stay
    // perfectly radial/straight.
    float twistedAngle = a + r * u_twist * 3.0 + t * 0.25;

    // u_detail sets the petal/spoke frequency — low values read as a
    // few broad lobes, high values read as a dense fan of thin spokes.
    float petals = cos(twistedAngle * u_detail);

    // Independent breathing rings, driven by radius and time only.
    float rings = sin(r * 18.0 - t * 3.0);

    float pattern = petals * rings;

    vec3 cyan = vec3(0.0, 0.95, 1.0);
    vec3 pink = vec3(1.0, 0.05, 0.6);
    vec3 col = mix(cyan, pink, 0.5 + 0.5 * pattern);

    // u_glow scales both the center core glow and the pattern's edge
    // glow — a pure luminous-intensity control with no shape/motion effect.
    float core = (0.035 * u_glow) / (r + 0.03);
    col += cyan * core;

    float edge = 1.0 - smoothstep(0.0, 0.08, abs(pattern));
    col += pink * edge * (0.3 * u_glow);

    // Soft vignette so the frame reads as a contained emblem, not a
    // full-bleed field — matches RETINA MELT's centered-emblem aesthetic.
    col *= (1.0 - smoothstep(0.6, 1.3, r));

    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
