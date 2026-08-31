// ============================================================
// ToroidAMP - Shader C: Shadertoy-Style Polar Tunnel (EXP-VISLAB-001)
// Level-1 single-pass mainImage() with exposed authoring parameters.
// ============================================================

// [param:float] u_spokes: Spoke Count = 8.0 (2.0 .. 16.0)
// [param:float] u_tunnelSpeed: Tunnel Speed = 4.0 (0.5 .. 10.0)
// [param:float] u_coreScale: Glow Core Size = 1.0 (0.1 .. 3.0)

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // Polar coordinates
    float r = length(uv);
    float a = atan(uv.y, uv.x);
    
    // Audio-reactive spectral tunnel modulated by parameters
    float bassWarp = taBass * 0.5;
    float tunnelDepth = 0.5 / (r + 0.05);
    
    float ringPattern = sin(tunnelDepth * 10.0 - iTime * u_tunnelSpeed + taMids * 3.0);
    float spokePattern = cos(a * u_spokes + iTime * 2.0 + bassWarp);
    
    // Color mapping
    vec3 col = vec3(0.0);
    float pattern = ringPattern * spokePattern;
    
    if (pattern > 0.0) {
        col.r = 0.5 + 0.5 * sin(iTime + tunnelDepth);
        col.g = 0.5 + 0.5 * sin(iTime + tunnelDepth + 2.0);
        col.b = 0.5 + 0.5 * sin(iTime + tunnelDepth + 4.0);
        col *= pattern;
    }
    
    // Center glowing core modulated by bass & beat & parameter
    float coreGlow = (0.03 * u_coreScale) / (r + 0.01) * (0.4 + taBass * 1.5);
    vec3 coreColor = (taStrongBeat > 0) ? vec3(1.0, 0.9, 0.3) : vec3(0.0, 0.8, 1.0);
    col += coreColor * coreGlow;
    
    fragColor = vec4(col, 1.0);
}
