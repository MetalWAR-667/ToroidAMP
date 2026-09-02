// ============================================================
// ToroidAMP - Shader B: Hyper Torus Raymarcher (EXP-VISLAB-001)
// Authentic 3D SDF raymarching torus with exposed authoring parameters.
// ============================================================

// [param:float] u_twist: Mesh Twist = 1.0 (0.0 .. 3.0)
// [param:float] u_radius: Base Radius = 1.6 (0.8 .. 3.0)
// [param:float] u_glowPower: Volumetric Halo = 1.0 (0.1 .. 3.0)
// [param:float] u_ripple: Surface Ripple = 1.0 (0.0 .. 4.0)

// SDF for Torus: t.x = major radius, t.y = minor tube radius
float sdTorus(vec3 p, vec2 t) {
    vec2 q = vec2(length(p.xz) - t.x, p.y);
    return length(q) - t.y;
}

// 2D rotation matrix
mat2 rot(float a) {
    float s = sin(a), c = cos(a);
    return mat2(c, -s, s, c);
}

// Map the scene distance field
float map(vec3 p) {
    // Coordinate twist driven by audio mids & parameter
    float twist = (0.5 + taMids * 1.5) * u_twist;
    p.xz *= rot(u_time * 0.8 + p.y * twist);
    p.yz *= rot(u_time * 0.5);
    
    // Bass pulse on major/minor radii
    float major_r = u_radius + taBass * 0.4;
    float minor_r = 0.45 + taTreble * 0.15 + (taStrongBeat > 0 ? 0.1 : 0.0);
    
    // Surface ripple from spectrum
    float ripple = sin(p.x * 10.0) * sin(p.y * 10.0) * sin(p.z * 10.0) * (0.02 + taTreble * 0.06) * u_ripple;
    
    return sdTorus(p, vec2(major_r, minor_r)) + ripple;
}

// Calculate normal via gradient
vec3 calcNormal(vec3 p) {
    float eps = 0.002;
    vec2 h = vec2(eps, 0.0);
    return normalize(vec3(
        map(p + h.xyy) - map(p - h.xyy),
        map(p + h.yxy) - map(p - h.yxy),
        map(p + h.yyx) - map(p - h.yyx)
    ));
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    
    // Camera setup
    vec3 ro = vec3(0.0, 0.0, -4.5);
    vec3 rd = normalize(vec3(uv, 1.3));
    
    // Raymarching loop
    float t = 0.0;
    float d = 0.0;
    float glow = 0.0;
    int max_steps = 64;
    
    for (int i = 0; i < max_steps; i++) {
        vec3 p = ro + rd * t;
        d = map(p);
        glow += 0.015 / (0.05 + abs(d));  // Volumetric neon halo
        if (d < 0.001 || t > 20.0) break;
        t += d * 0.8;
    }
    
    vec3 col = vec3(0.02, 0.02, 0.05);
    
    if (t < 20.0) {
        vec3 p = ro + rd * t;
        vec3 n = calcNormal(p);
        
        // Lighting
        vec3 lightDir = normalize(vec3(1.0, 2.0, -1.0));
        float diff = max(dot(n, lightDir), 0.0);
        float fresnel = pow(1.0 - max(dot(-rd, n), 0.0), 3.0);
        
        // Material colors
        vec3 baseColor = vec3(0.05, 0.8, 1.0);  // Neon Toroid Blue
        vec3 hotEdge = vec3(1.0, 0.1, 0.6);    // Hot Pink Fresnel
        
        col = baseColor * (diff * 0.6 + 0.2) + hotEdge * fresnel * 1.5;
        col += vec3(1.0) * pow(max(dot(reflect(-lightDir, n), -rd), 0.0), 16.0) * 0.8;
    }
    
    // Add audio-reactive volumetric glow modulated by parameter
    vec3 glowColor = mix(vec3(0.0, 0.6, 1.0), vec3(1.0, 0.0, 0.8), 0.5 + 0.5 * sin(u_time));
    col += glowColor * glow * 0.04 * (0.5 + taBass * 1.2) * u_glowPower;
    
    // Beat flash impulse
    if (taBeat > 0) {
        col += vec3(0.15, 0.05, 0.2);
    }
    
    // Energy master scale
    col *= (0.3 + taRms * 0.9);
    
    fragColor = vec4(col, 1.0);
}
