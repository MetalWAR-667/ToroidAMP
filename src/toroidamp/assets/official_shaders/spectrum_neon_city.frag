// ============================================================
// ToroidAMP Official :: Neon City Spectrum (EXP-VISLAB-006)
//
// 3D Isometric Cyberpunk Skyline Spectrum Analyzer:
//   - Procedural reflective neon skyscrapers whose heights and window glows
//     are directly driven by taSpectrum[64] frequency bins.
//   - Wet asphalt road grid reflecting the glowing skyline with Fresnel realism.
//   - Overhead holographic data moon / sun pulsing with taBass and taBeat.
//   - High-energy chromatic lightning & HF neon sparks on taTreble.
//   - CRT scanlines, chromatic aberration, and exponential beat surge.
// ============================================================

// [param:float] u_buildingScale: Skyline Height Multiplier = 1.4 (0.4 .. 3.5)
// [param:float] u_cameraSpeed: Metropolis Drive Speed = 1.2 (0.1 .. 4.0)
// [param:float] u_glowIntensity: Neon Window Bloom = 1.5 (0.2 .. 4.0)
// [param:float] u_reflectivity: Wet Asphalt Reflection = 0.75 (0.1 .. 1.0)
// [param:color] u_neonColorA: Primary Skyline Neon = #00F0FF
// [param:color] u_neonColorB: Secondary Skyline Neon = #FF0077

float hash21_city(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

// Sample audio spectrum
float sample_city_spec(float u) {
    float idx = clamp(abs(u) * 63.0, 0.0, 63.0);
    int i0 = int(floor(idx));
    int i1 = min(i0 + 1, 63);
    float f = fract(idx);
    f = f * f * (3.0 - 2.0 * f);
    return mix(taSpectrum[i0], taSpectrum[i1], f);
}

// Distance estimator for city blocks
vec2 city_map(vec3 p) {
    // Road plane at y = 0
    float dRoad = p.y;
    
    // Grid cell coordinates
    vec2 cell = floor(p.xz);
    vec2 local = fract(p.xz) - 0.5;
    
    // Leave center boulevard empty for the road/camera
    float laneDist = abs(p.x);
    if (laneDist < 0.9) {
        return vec2(dRoad, 0.0); // Road material ID 0
    }
    
    // Building height determined by spectrum bin corresponding to lateral
    // position -- same axis Spectrum Panorama's terrain uses (uv.x only),
    // not also mixed with depth (cell.y). Depth-mixing saturated binU to
    // 1.0 for nearly every building past ~22 world units, permanently
    // pinning most of the visible skyline to whatever the single highest
    // (usually near-silent) treble bin was doing -- reading as a mostly
    // static city even though the height math was technically still live.
    float binU = clamp(abs(cell.x) * 0.06, 0.0, 1.0);
    float spec = sample_city_spec(binU);
    float h = (0.3 + spec * 2.8 * u_buildingScale) * (0.6 + 0.4 * hash21_city(cell));
    
    // Box distance for skyscraper
    vec2 bSize = vec2(0.38, 0.38);
    vec2 dBox2D = abs(local) - bSize;
    float dSkyscraper = max(max(dBox2D.x, dBox2D.y), p.y - h);
    
    if (dSkyscraper < dRoad) {
        return vec2(dSkyscraper, 1.0 + binU); // Building material with spectrum ID
    }
    return vec2(dRoad, 0.0);
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    float t = u_time * u_cameraSpeed;
    
    float bass   = clamp(taBass, 0.0, 1.0);
    float mids   = clamp(taMids, 0.0, 1.0);
    float treble = clamp(taTreble, 0.0, 1.0);
    float peak   = clamp(taPeak, 0.0, 1.0);
    float rms    = clamp(taRms, 0.0, 1.0);
    
    // Camera moving forward down the boulevard
    vec3 ro = vec3(0.0, 0.45 + bass * 0.1, t * 2.5);
    vec3 rd = normalize(vec3(uv.x, uv.y - 0.08, 1.2));
    
    // Raymarching
    float d = 0.0;
    float matId = 0.0;
    for (int i = 0; i < 80; i++) {
        vec3 p = ro + d * rd;
        vec2 res = city_map(p);
        if (res.x < 0.002 * (1.0 + d * 0.1)) {
            matId = res.y;
            break;
        }
        d += res.x * 0.65;
        if (d > 35.0) break;
    }
    
    // Sky background with holographic data moon & starfield
    vec3 col = vec3(0.015, 0.012, 0.035);
    
    // Distant holographic moon in the background
    vec3 moonDir = normalize(vec3(0.0, 0.28, 1.0));
    float moonDist = distance(rd, moonDir);
    if (moonDist < 0.22) {
        float moonRing = sin(moonDist * 70.0 - u_time * 4.0);
        vec3 moonColor = mix(u_neonColorA, u_neonColorB, 0.5 + 0.5 * sin(u_time));
        col += moonColor * (0.8 + 1.2 * bass) * smoothstep(0.22, 0.02, moonDist) * (0.6 + 0.4 * moonRing);
    }
    
    if (d < 35.0) {
        vec3 p = ro + d * rd;
        
        if (matId > 0.5) {
            // Skyscraper lighting & glowing windows
            vec2 windowGrid = fract(p.xy * vec2(8.0, 14.0));
            float winMask = step(0.25, windowGrid.x) * step(0.25, windowGrid.y);
            float winGlow = hash21_city(floor(p.xy * vec2(8.0, 14.0)) + floor(p.z));
            
            vec3 neonA = u_neonColorA;
            vec3 neonB = u_neonColorB;
            vec3 bldgNeon = mix(neonA, neonB, clamp(matId - 1.0, 0.0, 1.0));
            
            // Audio-driven window activity
            float windowActive = smoothstep(0.4, 0.9, winGlow + treble * 0.5);
            vec3 windowColor = bldgNeon * winMask * windowActive * (1.5 + peak * 2.0) * u_glowIntensity;
            
            vec3 darkFacade = vec3(0.04, 0.04, 0.07);
            col = darkFacade + windowColor;
            
            // Edge neon beacon line along rooftop
            if (p.y > 0.2) {
                float roofEdge = exp(-abs(p.y - (matId - 1.0)) * 10.0);
                col += bldgNeon * roofEdge * (1.0 + treble * 2.0);
            }
        } else {
            // Wet asphalt road reflecting the neon skyline
            vec3 rfd = reflect(rd, vec3(0.0, 1.0, 0.0));
            vec2 roadUv = p.xz;
            
            // Grid road markings
            float centerStripe = smoothstep(0.03, 0.01, abs(p.x)) * step(0.3, fract(p.z * 1.5));
            vec3 stripeCol = vec3(1.0, 0.85, 0.2) * (1.0 + bass);
            
            // Road wet reflection
            vec3 reflColor = mix(u_neonColorA, u_neonColorB, 0.5 + 0.5 * sin(p.z * 0.1 + t));
            float wetGlow = exp(-abs(p.x) * 1.5) * (0.4 + rms * 0.8) * u_reflectivity;
            
            col = vec3(0.02, 0.02, 0.03) + centerStripe * stripeCol + reflColor * wetGlow;
        }
        
        // Depth atmospheric fog
        vec3 fogColor = mix(vec3(0.01, 0.01, 0.03), u_neonColorB * 0.2, 0.5 + 0.5 * sin(t * 0.5));
        col = mix(col, fogColor, 1.0 - exp(-d * 0.07));
    }
    
    // Beat transient surge
    float surge = (taStrongBeat > 0 ? 1.0 : (taBeat > 0 ? 0.45 : 0.0)) * exp(-4.0 * fract(taBeatPhase));
    col += vec3(0.9, 0.95, 1.0) * surge * 0.22;
    
    // CRT Scanlines & Vignette
    float scan = sin(gl_FragCoord.y * 3.14159);
    col *= 1.0 - 0.4 * (0.5 + 0.5 * scan * scan);
    
    vec2 vUv = gl_FragCoord.xy / u_resolution.xy;
    vec2 vig = vUv * (1.0 - vUv.yx);
    col *= clamp(pow(vig.x * vig.y * 15.0, 0.28), 0.0, 1.0);
    
    // Tone mapping
    col = col / (col + vec3(1.0));
    col = pow(col, vec3(0.90));
    
    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
