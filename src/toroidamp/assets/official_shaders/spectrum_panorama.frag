// ============================================================
// ToroidAMP Official :: Spectrum Panorama CRT (Synthwave / Outrun Sunset)
//
// 3D Raymarched Triangulated Wireframe Terrain & Synthwave Sunset:
//   - Raymarched procedural pseudo-tessellation terrain (trinoise + triangular grid)
//   - Audio-reactive elevation driven by taSpectrum[64], taBass, taMids, taTreble
//   - Blinds-striped Retrowave Sunset Sun with horizon haze & starlight
//   - Reflective neon metallic mountain slopes with specular highlights
//   - Neon wireframe grid edges with treble/strongbeat intensity & width
//   - 4-color cycling demoscene palette (Cyan/Magenta/Gold/White)
//   - CRT scanlines, curved vignette, and beat-decay surge
//   - Fully compatible with ToroidAMP native AudioFrame uniform contract
// ============================================================

// [param:float] u_speed: Flying Speed = 6.0 (1.0 .. 15.0)
// [param:float] u_mountainHeight: Mountain Elevation = 1.6 (0.5 .. 3.5)
// [param:float] u_wireWidth: Neon Wire Thickness = 1.0 (0.2 .. 3.0)
// [param:float] u_scanline: CRT Scanline Contrast = 0.45 (0.0 .. 1.0)
// [param:float] u_paletteSpeed: Color Cycle Speed = 0.35 (0.0 .. 2.0)

// ------------------------------------------------------------------
// 1. Demoscene 4-Color Palette (Cyan / Magenta / Gold / White)
// ------------------------------------------------------------------
vec3 synth_palette(float phase) {
    float p = fract(phase);
    float w0 = 0.5 + 0.5 * cos(6.2831853 * (p - 0.00));
    float w1 = 0.5 + 0.5 * cos(6.2831853 * (p - 0.25));
    float w2 = 0.5 + 0.5 * cos(6.2831853 * (p - 0.50));
    float w3 = 0.5 + 0.5 * cos(6.2831853 * (p - 0.75));
    float total = w0 + w1 + w2 + w3 + 0.0001;
    
    vec3 cCyan    = vec3(0.05, 0.92, 1.00);
    vec3 cMagenta = vec3(0.96, 0.08, 0.72);
    vec3 cGold    = vec3(1.00, 0.78, 0.14);
    vec3 cWhite   = vec3(0.96, 0.98, 1.00);
    
    return (cCyan * w0 + cMagenta * w1 + cGold * w2 + cWhite * w3) / total;
}

// ------------------------------------------------------------------
// 2. Audio Spectrum Sampler (interpolated from taSpectrum[64])
// ------------------------------------------------------------------
float sample_spectrum(float u) {
    float binIdx = clamp(abs(u) * 63.0, 0.0, 63.0);
    int i0 = int(floor(binIdx));
    int i1 = min(i0 + 1, 63);
    float f = fract(binIdx);
    f = f * f * (3.0 - 2.0 * f);
    return mix(taSpectrum[i0], taSpectrum[i1], f);
}

// ------------------------------------------------------------------
// 3. Mathematical & Noise Utilities
// ------------------------------------------------------------------
float hash21(vec2 co) {
    return fract(sin(dot(co.xy, vec2(1.9898, 7.233))) * 45758.5433);
}

float pow512(float a) {
    a *= a; a *= a; a *= a; a *= a;
    a *= a; a *= a; a *= a; a *= a;
    return a * a;
}

float pow1d5(float a) {
    return a * sqrt(max(a, 0.0));
}

float amp(vec2 p) {
    return smoothstep(1.0, 8.0, abs(p.x));
}

// Global runtime animation time
float gTime;

float terrain_hash(vec2 uv) {
    float a = amp(uv);
    if (a <= 0.0) return 0.0;
    
    // Wave ripple along mountains
    float w = 1.0 - 0.4 * pow512(0.51 + 0.49 * sin((0.02 * (uv.y + 0.5 * uv.x) - gTime * 0.2) * 2.0));
    float h = a * pow1d5(hash21(uv)) * w;
    
    // Modulate with audio spectrum frequencies
    float spec = sample_spectrum(clamp(abs(uv.x) * 0.12, 0.0, 1.0));
    h += spec * (0.8 + 1.2 * taBass);
    
    return h * u_mountainHeight;
}

float edgeMin(float dx, vec2 da, vec2 db, vec2 uv) {
    uv.x += 5.0;
    return min(min((1.0 - dx) * db.y, da.x), da.y);
}

// Triangulated pseudo-tessellation noise (returns height and edge wireframe metric)
vec2 trinoise(vec2 uv) {
    const float sq = 1.22474487; // sqrt(3.0 / 2.0)
    uv.x *= sq;
    uv.y -= 0.5 * uv.x;
    vec2 d = fract(uv);
    uv -= d;

    bool c = (d.x + d.y) > 1.0;
    vec2 dd = 1.0 - d;
    vec2 da = c ? dd : d;
    vec2 db = c ? d : dd;
    
    float nn = terrain_hash(uv + (c ? vec2(1.0) : vec2(0.0)));
    float n2 = terrain_hash(uv + vec2(1.0, 0.0));
    float n3 = terrain_hash(uv + vec2(0.0, 1.0));

    float nmid = mix(n2, n3, d.y);
    float ns = mix(nn, c ? n2 : n3, da.y);
    float dx = (db.y > 0.0001) ? (da.x / db.y) : 0.0;
    
    return vec2(mix(ns, nmid, dx), edgeMin(dx, da, db, uv + d));
}

vec2 map(vec3 p) {
    vec2 n = trinoise(p.xz);
    // Valley floor with audio bounce on beats
    float bounce = (taStrongBeat > 0 ? 0.35 : (taBeat > 0 ? 0.18 : 0.0)) * exp(-4.0 * fract(taBeatPhase));
    float ground = p.y - 2.0 * n.x + bounce;
    return vec2(ground, n.y);
}

vec3 grad(vec3 p) {
    const vec2 e = vec2(0.005, 0.0);
    float a = map(p).x;
    return vec3(
        map(p + e.xyy).x - a,
        map(p + e.yxy).x - a,
        map(p + e.yyx).x - a
    ) / e.x;
}

vec2 intersect(vec3 ro, vec3 rd) {
    float d = 0.0;
    float h = 0.0;
    for (int i = 0; i < 90; i++) {
        vec3 p = ro + d * rd;
        vec2 s = map(p);
        h = s.x;
        d += h * 0.5;
        if (abs(h) < 0.003 * d)
            return vec2(d, s.y);
        if (d > 140.0 || p.y > 10.0) break;
    }
    return vec2(-1.0);
}

// ------------------------------------------------------------------
// 4. Synthwave Sun & Sky Generation
// ------------------------------------------------------------------
void addsun(vec3 rd, vec3 ld, inout vec3 col, float colorPhase) {
    float sunDist = distance(rd, ld);
    float sun = smoothstep(0.24, 0.23, sunDist);
    
    if (sun > 0.0) {
        float yd = (rd.y - ld.y);
        // Classic horizontal horizontal blind stripes that get thinner towards bottom
        float stripes = sin(3.14159 * exp(-yd * 14.0));
        sun *= smoothstep(-0.85, 0.0, stripes);
        
        // Sun color gradient (Gold top -> Hot Magenta bottom)
        vec3 sunTop = synth_palette(colorPhase + 0.50); // Gold
        vec3 sunBot = synth_palette(colorPhase + 0.25); // Magenta
        vec3 sunCol = mix(sunBot, sunTop, clamp((rd.y - ld.y + 0.2) * 2.5, 0.0, 1.0));
        
        col = mix(col, sunCol * 1.5, sun);
    }
}

float starnoise(vec3 rd) {
    float c = 0.0;
    vec3 p = normalize(rd) * 240.0;
    for (float i = 0.0; i < 3.0; i += 1.0) {
        vec3 q = fract(p) - 0.5;
        vec3 id = floor(p);
        float c2 = smoothstep(0.45, 0.0, length(q));
        c2 *= step(hash21(id.xz / (id.y + 0.1)), 0.04 - i * i * 0.004);
        c += c2;
        p = p * 0.6 + 0.5 * p * mat3(0.6, 0.0, 0.8, 0.0, 1.0, 0.0, -0.8, 0.0, 0.6);
    }
    return c * c;
}

vec3 gsky(vec3 rd, vec3 ld, bool mask, float colorPhase) {
    float haze = exp2(-5.0 * (abs(rd.y) - 0.2 * dot(rd, ld)));
    float stars = mask ? starnoise(rd) * (1.0 - min(haze, 1.0)) : 0.0;
    
    // Deep purple/magenta cosmic backdrop
    vec3 back = vec3(0.12, 0.02, 0.25) * (0.8 + 0.4 * taBass);
    vec3 horizonGlow = synth_palette(colorPhase + 0.25); // Magenta/Orange
    
    vec3 col = clamp(mix(back, horizonGlow, haze) + stars * (0.6 + taTreble * 0.8), 0.0, 1.0);
    if (mask) addsun(rd, ld, col, colorPhase);
    return col;
}

// ------------------------------------------------------------------
// 5. Main Shader Entry Point
// ------------------------------------------------------------------
void main() {
    vec2 uv = (2.0 * gl_FragCoord.xy - u_resolution.xy) / u_resolution.y;
    float t = u_time;
    gTime = t * u_speed;
    
    // Audio primitives
    float bass   = clamp(taBass, 0.0, 1.0);
    float mids   = clamp(taMids, 0.0, 1.0);
    float treble = clamp(taTreble, 0.0, 1.0);
    float rms    = clamp(taRms, 0.0, 1.0);
    float peak   = clamp(taPeak, 0.0, 1.0);
    
    float colorPhase = t * u_paletteSpeed + mids * 0.25;
    
    // Camera ray setup (flying above valley floor)
    vec3 ro = vec3(0.0, 1.0 + bass * 0.2, gTime);
    vec3 rd = normalize(vec3(uv, 1.333));
    
    // Light direction toward the sunset
    vec3 ld = normalize(vec3(0.0, 0.12 + 0.04 * sin(t * 0.2), 1.0));
    
    vec2 hit = intersect(ro, rd);
    float d = hit.x;
    
    vec3 sky = gsky(rd, ld, d < 0.0, colorPhase);
    vec3 col = sky;
    
    if (d > 0.0) {
        vec3 p = ro + d * rd;
        vec3 n = normalize(grad(p));
        
        // Directional shading + ambient up-light
        float diff = max(dot(n, ld), 0.0) + 0.15 * max(n.y, 0.0);
        vec3 groundBase = vec3(0.08, 0.09, 0.15) * diff;
        
        // Metallic specular reflections from sunset sky
        vec3 rfd = reflect(rd, n);
        vec3 rfcol = gsky(rfd, ld, true, colorPhase);
        float fresnel = 0.05 + 0.95 * pow(max(1.0 + dot(rd, n), 0.0), 4.0);
        groundBase = mix(groundBase, rfcol, fresnel);
        
        // Neon wireframe grid edges (sharp lines, reactive thickness)
        float wireThickness = (0.04 + treble * 0.04 + (taStrongBeat > 0 ? 0.06 : 0.0)) * u_wireWidth;
        float wireMask = smoothstep(wireThickness, 0.0, hit.y);
        
        // Wireframe glowing color from 4-color palette
        vec3 wireColor = synth_palette(colorPhase + 0.0); // Cyan/Magenta
        wireColor = mix(wireColor, vec3(1.0), 0.3 + 0.7 * treble);
        
        groundBase = mix(groundBase, wireColor * 2.2, wireMask);
        
        // Atmospheric depth fog
        vec3 fog = exp2(-d * vec3(0.08, 0.05, 0.14));
        col = mix(sky, groundBase, fog);
    }
    
    // ------------------------------------------------------------------
    // Beat Surge Flash + Micro-Glow
    // ------------------------------------------------------------------
    float surge = (taStrongBeat > 0 ? 1.0 : (taBeat > 0 ? 0.5 : 0.0)) * exp(-4.5 * fract(taBeatPhase));
    col += vec3(0.9, 0.85, 1.0) * surge * 0.25;
    
    // Central phosphor glow
    float coreGlow = exp(-length(uv) * 2.0) * (rms * 0.4 + peak * 0.3);
    col += synth_palette(colorPhase + 0.1) * coreGlow;
    
    // ------------------------------------------------------------------
    // CRT Scanlines & Vignette
    // ------------------------------------------------------------------
    float scan = sin(gl_FragCoord.y * 3.14159);
    col *= 1.0 - u_scanline * (0.5 + 0.5 * scan * scan);
    
    vec2 vUv = gl_FragCoord.xy / u_resolution.xy;
    vec2 vig = vUv * (1.0 - vUv.yx);
    col *= clamp(pow(vig.x * vig.y * 15.0, 0.30), 0.0, 1.0);
    
    // ------------------------------------------------------------------
    // Safe Tone Mapping
    // ------------------------------------------------------------------
    col = col / (col + vec3(1.0));
    col = pow(col, vec3(0.92));
    
    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
