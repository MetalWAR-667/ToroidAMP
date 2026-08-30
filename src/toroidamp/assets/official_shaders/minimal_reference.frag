// ============================================================
// ToroidAMP Official Reference :: Minimal Procedural (GPU-OFFICIAL-001)
// Author: ToroidAMP Team
// License: MIT
//
// Purpose:
//   Minimal, standalone, zero-texture reference shader for contributors.
//   Demonstrates native ToroidAMP GLSL uniform contracts and parameter annotations.
//
// Workflow:
//   COPY -> MODIFY -> TEST IN GPU LAB -> CONTRIBUTE
// ============================================================

// [param:float] u_rotSpeed: Rotation Speed = 1.0 (0.1 .. 4.0)
// [param:float] u_ringCount: Ring Multiplier = 6.0 (2.0 .. 12.0)
// [param:float] u_colorCycle: Palette Offset = 0.0 (0.0 .. 6.28)

void main() {
    // Aspect-Safe UV coordinates centered at (0, 0)
    vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    float r = length(uv);
    float a = atan(uv.y, uv.x);

    // 1. Audio Modulation
    float speed = (0.5 + taMids * 1.5) * u_rotSpeed;
    float t = u_time * speed;

    // 2. Geometric Rings & Spokes
    float rings = sin(r * u_ringCount * 4.0 - t * 3.0 + taBass * 2.0);
    float spokes = cos(a * 8.0 + t + taTreble * 1.5);
    float pattern = rings * spokes;

    // 3. Emissive Palette
    vec3 cyan = vec3(0.0, 0.95, 1.0);
    vec3 pink = vec3(1.0, 0.05, 0.6);
    vec3 col = mix(cyan, pink, 0.5 + 0.5 * sin(pattern * 3.14 + u_colorCycle));

    // 4. Center Core Glow & Silence Baseline
    float core = 0.02 / (r + 0.02) * (0.4 + taBass * 1.5);
    if (taStrongBeat > 0) {
        col += vec3(0.4, 0.2, 0.5);
    }
    col += cyan * core;

    // Vignette
    col *= (1.0 - smoothstep(0.5, 1.4, r)) * (0.3 + taRms * 0.9);

    fragColor = vec4(col, 1.0);
}
