// ToroidAMP test fixture (MIT, project-owned). See ../README.md.
// Supported Shadertoy subset: mainImage + iResolution + iTime.
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float pulse = 0.5 + 0.5 * sin(iTime);
    fragColor = vec4(uv, pulse, 1.0);
}
