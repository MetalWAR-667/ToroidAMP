// ToroidAMP test fixture (MIT, project-owned). See ../README.md.
// Structural literals only: expected to have no current-eligible parameter.
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float acc = 0.0;
    for (int i = 0; i < 8; i++) {
        acc += 0.125;
    }

    vec3 palette[3];
    palette[0] = vec3(0.1, 0.2, 0.3);
    palette[1] = vec3(0.3, 0.2, 0.1);
    palette[2] = vec3(0.2, 0.3, 0.1);

    int idx = int(acc * 2.0);
    fragColor = vec4(palette[idx] + vec3(uv, 0.0), 1.0);
}
