// ToroidAMP test fixture (MIT, project-owned). See ../README.md.
// Safe promotable constant: expected to be current-eligible.
const float SPEED = 0.6;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    fragColor = vec4(uv, SPEED, 1.0);
}
