// ============================================================
// ToroidAMP Official Reference :: Cyber Bloom (EXP-VISLAB-003)
// Author: Jack (Demoscene Visual Engineer) & ToroidAMP Team
// License: MIT
//
// Purpose:
//   Canonical Foundation II reference shader demonstrating all
//   supported typed authoring parameters (float, bool, color)
//   and reactive AudioFrame uniform contracts.
//
// Authoring Parameters:
//   - float: u_speed, u_warpDepth, u_glowIntensity
//   - bool:  u_enableDistortion, u_invertColors
//   - color: u_primaryColor, u_accentColor
//
// Musical Causality:
//   - taBass:   Pumps outer bloom petals and dilates center geometry
//   - taMids:   Drives rotational velocity and angular twisting
//   - taTreble: Modulates fine boundary interference ripples
//   - taBeat:   Injects transient flash energy and core shockwaves
//
// Silence Baseline:
//   - Elegant, calm dormant breathing cycle with zero flashing.
// ============================================================

// [param:float] u_speed: Evolution Speed = 1.0 (0.1 .. 4.0)
// [param:float] u_warpDepth: Toroidal Warp Depth = 1.2 (0.0 .. 3.0)
// [param:float] u_glowIntensity: Core Glow Multiplier = 1.5 (0.2 .. 4.0)
// [param:bool] u_enableDistortion: Enable Harmonic Distortion = true
// [param:bool] u_invertColors: Invert Palette Chromatics = false
// [param:color] u_primaryColor: Primary Neon = #00E5FF
// [param:color] u_accentColor: Accent Neon = #FF0077

mat2 rot2d(float a) {
    float s = sin(a), c = cos(a);
    return mat2(c, -s, s, c);
}

void main() {
    // 1. Aspect-Safe Normalized Coordinates centered at origin
    vec2 p = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    float r = length(p);
    float a = atan(p.y, p.x);

    // 2. Musical Envelope Modulations
    float bassPunch = taBass * 0.8;
    float midEnergy = taMids * 0.6;
    float trebleShimmer = taTreble * 0.5;
    float beatPulse = float(taBeat) * 0.2 + float(taStrongBeat) * 0.4;

    // 3. Dynamic Rotation & Angular Harmonic Bloom
    float t = u_time * u_speed;
    float rotAngle = t * 0.2 + midEnergy * sin(t * 0.5);
    vec2 pRot = rot2d(rotAngle) * p;

    // Multi-petal harmonic bloom
    float petals = sin(a * 6.0 + t * 0.5) * (0.15 + bassPunch * 0.2);
    if (u_enableDistortion) {
        petals += sin(a * 12.0 - t * 1.5) * (0.08 * u_warpDepth + trebleShimmer * 0.1);
    }

    float bloomDist = abs(r - 0.35 - petals);

    // Shockwave ripple radiating outward
    float ripple = sin(r * 24.0 - t * 3.0 + bassPunch * 4.0) * (0.05 + trebleShimmer * 0.1);
    if (u_enableDistortion) {
        bloomDist += ripple * u_warpDepth;
    }

    // 4. Color Synthesis & Palette Blending
    vec3 c1 = u_primaryColor;
    vec3 c2 = u_accentColor;
    if (u_invertColors) {
        c1 = vec3(1.0) - c1;
        c2 = vec3(1.0) - c2;
    }

    float colorMix = clamp(sin(a * 3.0 + t * 0.8) * 0.5 + 0.5 + bassPunch * 0.3, 0.0, 1.0);
    vec3 baseColor = mix(c1, c2, colorMix);

    // 5. Emissive Glow & Center Toroid Core
    float ringGlow = (0.015 * u_glowIntensity) / (bloomDist + 0.012);
    float coreGlow = (0.03 * u_glowIntensity) / (r + 0.03) * (0.5 + bassPunch + beatPulse);

    vec3 finalColor = baseColor * ringGlow + c1 * coreGlow;

    // Transient beat burst
    if (beatPulse > 0.0) {
        finalColor += mix(c2, vec3(1.0), 0.5) * beatPulse * 0.5;
    }

    // 6. Cyberspace Background Field & Silence Baseline
    float bgGrid = sin(pRot.x * 20.0) * sin(pRot.y * 20.0);
    float bgField = smoothstep(0.7, 1.0, bgGrid) * (0.04 + taRms * 0.15);
    finalColor += c2 * bgField;

    // Smooth subtle vignette
    finalColor *= (1.0 - smoothstep(0.6, 1.4, r));

    fragColor = vec4(finalColor, 1.0);
}

