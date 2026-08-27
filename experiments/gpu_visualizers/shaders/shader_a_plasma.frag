// ============================================================
// ToroidAMP - Shader A: Cyber Plasma Field (EXP-VISLAB-001)
// Non-trivial warped procedural field with exposed authoring parameters.
// ============================================================

// [param:float] u_speed: Evolution Speed = 1.0 (0.1 .. 4.0)
// [param:float] u_warp: Coordinate Warp = 3.0 (0.5 .. 8.0)
// [param:float] u_glow: Amber Halo Intensity = 1.0 (0.0 .. 3.0)
// [param:float] u_colorShift: Cyber Palette Shift = 0.0 (0.0 .. 3.14)

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    
    // Musical causality modulators + authoring parameters
    float speed = (0.8 + taMids * 1.5) * u_speed;
    float t = u_time * speed;
    
    // Coordinate warping
    vec2 p = uv * (u_warp + taBass * 2.0);
    for (int i = 1; i < 4; i++) {
        p.x += 0.3 / float(i) * sin(float(i) * 3.0 * p.y + t + taTreble * 1.2);
        p.y += 0.3 / float(i) * cos(float(i) * 3.0 * p.x + t + float(taBeat) * 0.4);
    }
    
    // Plasma equations
    float v1 = sin(p.x * 2.0 + t);
    float v2 = sin(p.y * 2.0 + t * 1.2);
    float v3 = sin((p.x + p.y) * 2.0 + t * 0.7);
    float dist = length(p);
    float v4 = sin(dist * 4.0 - t * 2.0);
    
    float val = (v1 + v2 + v3 + v4) * 0.25;
    
    // Cyberpunk palette with parameter shift
    vec3 colA = vec3(0.0, 0.95, 1.0);  // Cyan
    vec3 colB = vec3(1.0, 0.0, 0.55);  // Magenta
    vec3 colC = vec3(1.0, 0.7, 0.0);   // Amber
    
    vec3 col = mix(colA, colB, 0.5 + 0.5 * sin(val * 3.14 + u_colorShift));
    col += colC * pow(max(0.0, sin(dist * 8.0 - t * 4.0)), 4.0) * (0.3 + taTreble * 0.7) * u_glow;
    
    // Dynamic beat impact flash & glow
    if (taStrongBeat > 0) {
        col += vec3(0.4, 0.2, 0.5) * (1.0 - length(uv));
    }
    
    // Vignette
    float vig = 1.0 - smoothstep(0.5, 1.4, length(uv));
    col *= vig * (0.4 + taRms * 0.8);
    
    fragColor = vec4(col, 1.0);
}
