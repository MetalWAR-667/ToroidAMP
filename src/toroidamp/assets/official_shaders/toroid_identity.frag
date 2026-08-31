// ============================================================
// ToroidAMP Official GPU Visualizer :: Toroid Identity (GPU-OFFICIAL-001)
// Author: Jack (Demoscene Visual Engineer) & Metal (ToroidAMP)
//
// Visual Thesis:
//   "The ToroidAMP master branding artifact lives in a deep cyberspace vacuum.
//    Bass pulses dilate space and pump toroidal shockwaves through the emblem;
//    mids twist space with rotational inertia; treble shears chromatic edge photons;
//    beat transients shatter the geometry into radial holographic energy."
//
// Demonstrates:
//   - Packaged official texture sampling (taTexture0) with aspect-safe framing (contain/cover)
//   - Full AudioFrame normalization contracts (taBass, taMids, taTreble, taBeat, taStrongBeat, taSpectrum)
//   - Exposed runtime authoring parameters (u_warp, u_chroma, u_glow, u_rotation, u_bgIntensity)
//   - Deliberate silence baseline (calm dormant drift, no chaotic noise flashing)
// ============================================================

// [param:float] u_warp: Toroidal Warp Depth = 1.0 (0.0 .. 3.0)
// [param:float] u_chroma: Chromatic Aberration = 1.0 (0.0 .. 4.0)
// [param:float] u_glow: Emissive Neon Halo = 1.2 (0.2 .. 3.5)
// [param:float] u_rotation: Dynamic Inertia Speed = 1.0 (0.0 .. 3.0)
// [param:float] u_bgIntensity: Cyberspace Field = 0.8 (0.0 .. 2.0)

// 2D Rotation Matrix
mat2 rot(float a) {
    float s = sin(a), c = cos(a);
    return mat2(c, -s, s, c);
}

void main() {
    // 1. Aspect-Safe UV Coordinates centered at origin [-aspect..aspect, -1..1]
    vec2 p = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    float r = length(p);
    float a = atan(p.y, p.x);

    // 2. Musical Dynamics & Envelope Modulators
    float bassPunch = taBass * u_warp;
    float midTwist  = taMids * u_rotation;
    float trebleEdge = taTreble * u_chroma;
    float beatImpulse = float(taBeat) * 0.15 + float(taStrongBeat) * 0.35;

    // 3. Toroidal & Shockwave UV Warping
    // Shockwave ring traveling outward from center
    float wavePhase = fract(u_time * 1.2);
    float waveDist  = abs(r - wavePhase * 1.2);
    float shockwave = exp(-waveDist * 18.0) * (bassPunch * 0.4 + beatImpulse * 0.5);

    // Coordinate rotation with musical inertia
    float rotAngle = u_time * 0.15 * u_rotation + midTwist * 0.35 * sin(u_time * 0.5);
    vec2 pRot = rot(rotAngle) * p;

    // Radial Toroidal Pinch & Ripple
    float toroidalFactor = 1.0 + 0.25 * sin(r * 12.0 - u_time * 3.0) * bassPunch;
    vec2 pWarped = pRot * toroidalFactor;
    pWarped += normalize(pRot + 1e-4) * shockwave * 0.2;

    // 4. Logo UV Mapping (Aspect-Safe Contain Framing within [-0.55..0.55])
    float logoScale = 1.15 / (1.0 + bassPunch * 0.15 + beatImpulse * 0.2);
    vec2 logoUV = (pWarped * logoScale) + 0.5;

    // 5. Chromatic Separation Sampling (RGB Split on High Energy)
    vec2 chromaOffset = normalize(pRot + 1e-4) * (0.006 + trebleEdge * 0.025);
    
    vec4 texCenter = texture(taTexture0, logoUV);
    vec4 texR      = texture(taTexture0, logoUV + chromaOffset);
    vec4 texB      = texture(taTexture0, logoUV - chromaOffset);

    // Composite split image with alpha preservation
    vec3 logoColor;
    logoColor.r = texR.r;
    logoColor.g = texCenter.g;
    logoColor.b = texB.b;
    float logoAlpha = max(texCenter.a, max(texR.a, texB.a));

    // Clamp out-of-bounds UVs
    if (logoUV.x < 0.0 || logoUV.x > 1.0 || logoUV.y < 0.0 || logoUV.y > 1.0) {
        logoAlpha = 0.0;
    }

    // 6. Cybernetic Emissive Edge & Hot Core Glow
    float edgeEnergy = length(texR.rgb - texB.rgb) * 3.2 * (0.8 + trebleEdge);
    vec3 neonCyan    = vec3(0.0, 0.95, 1.0);
    vec3 hotPink     = vec3(1.0, 0.05, 0.6);
    vec3 solarAmber  = vec3(1.0, 0.75, 0.1);

    vec3 glowColor = mix(neonCyan, hotPink, 0.5 + 0.5 * sin(u_time + r * 4.0));
    glowColor = mix(glowColor, solarAmber, float(taStrongBeat));

    vec3 emissiveGlow = glowColor * edgeEnergy * u_glow;

    // Volumetric Toroidal Halo around the logo
    float haloDist = abs(r - 0.45 * (1.0 + bassPunch * 0.2));
    float halo = (0.022 / (haloDist + 0.035)) * (0.6 + bassPunch * 1.8 + taRms * 1.0) * u_glow;

    // 7. Procedural Cyberspace Background (Perspective grid + ambient field)
    vec2 bgGrid = fract(p * 6.0 * (1.0 + bassPunch * 0.15) + vec2(0.0, u_time * 0.15)) - 0.5;
    float gridLines = smoothstep(0.08, 0.0, abs(bgGrid.x)) + smoothstep(0.08, 0.0, abs(bgGrid.y));
    float gridGlow = gridLines * 0.75 * (0.6 + taMids * 1.2);

    vec3 bgColor = (vec3(0.015, 0.02, 0.04) + neonCyan * gridGlow * 0.8) * u_bgIntensity;

    // 8. Final Scene Composition
    // Crisp artwork presentation with vibrant emblem response
    vec3 finalColor = mix(bgColor, logoColor * 1.35 + emissiveGlow, logoAlpha);
    finalColor += glowColor * halo * (0.85 - logoAlpha * 0.4);

    // Dynamic Master Bass Kick Flash
    if (taStrongBeat > 0) {
        finalColor += vec3(0.35, 0.15, 0.4) * (1.0 - smoothstep(0.0, 1.0, r));
    }

    // Silence Baseline / Vignette
    float vig = 1.0 - smoothstep(0.7, 1.6, r);
    finalColor *= vig * (0.75 + taRms * 0.5);

    fragColor = vec4(finalColor, 1.0);
}
