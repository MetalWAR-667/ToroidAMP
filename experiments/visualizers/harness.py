"""
Visualizer Lab II — Experimental Harness

Runs ONE experimental visualizer standalone, fed by deterministic synthetic
AudioFrame profiles. Not a second application — a tiny Pygame window.

Usage:
    python experiments\\visualizers\\harness.py deep-field
    python experiments\\visualizers\\harness.py floor
    python experiments\\visualizers\\harness.py matrix-wing

Controls (also drawn on-screen):
    1-5     switch profile: SILENCE / ORCHESTRAL / METAL / ELECTRONIC / AMBIENT
    SPACE   inject a beat
    ENTER   inject a strong_beat
    F       toggle FPS/debug overlay
    ESC     quit
    window is resizable — every experiment must tolerate arbitrary sizes.
"""

import os
import sys
import time

# Allow running directly via `python experiments\visualizers\harness.py ...`
# without requiring the repo to be pip-installed in the current environment.
_REPO_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
if _REPO_SRC not in sys.path:
    sys.path.insert(0, _REPO_SRC)

import pygame

from profiles import PROFILES, PROFILE_ORDER

EXPERIMENTS = {
    "deep-field": ("deep_field", "DeepFieldVisualizer"),
    "floor": ("toroidamp_floor", "ToroidAMPFloorVisualizer"),
    "matrix-wing": ("matrix_wing_commander", "MatrixWingCommanderVisualizer"),
}


def _load_visualizer_class(module_name: str, class_name: str):
    import importlib
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in EXPERIMENTS:
        print(__doc__)
        print(f"Available experiments: {', '.join(EXPERIMENTS)}")
        return 1

    exp_key = sys.argv[1]
    module_name, class_name = EXPERIMENTS[exp_key]
    VisualizerClass = _load_visualizer_class(module_name, class_name)

    pygame.init()
    width, height = 960, 540
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    pygame.display.set_caption(f"ToroidAMP Lab II — {exp_key}")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 14)

    vis = VisualizerClass(width, height)

    profile_name = "silence"
    profile = PROFILES[profile_name]()

    show_debug = True
    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                width, height = event.w, event.h
                screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                vis.resize(width, height)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    profile.inject_beat(strong=False)
                elif event.key == pygame.K_RETURN:
                    profile.inject_beat(strong=True)
                elif event.key == pygame.K_f:
                    show_debug = not show_debug
                elif pygame.K_1 <= event.key <= pygame.K_5:
                    idx = event.key - pygame.K_1
                    profile_name = PROFILE_ORDER[idx]
                    profile = PROFILES[profile_name]()

        frame = profile.tick(dt)
        # Mirrors production integration exactly: the harness (like
        # VisualizerModule/RetinaMeltWindow) calls only render(); each
        # visualizer calls its own update() internally. See Lab I's
        # contract-quirk finding — this experiment intentionally does not
        # "fix" it, to gather real evidence on whether it matters.
        vis.render(screen, frame, dt)

        if show_debug:
            fps = clock.get_fps()
            lines = [
                f"[{exp_key}]  profile={profile_name}  fps={fps:5.1f}  dt={dt*1000:5.1f}ms  size={width}x{height}",
                "1-5 profile | SPACE beat | ENTER strong_beat | F toggle overlay | ESC quit",
            ]
            for i, line in enumerate(lines):
                surf = font.render(line, True, (0, 255, 200))
                bg = pygame.Surface(surf.get_size())
                bg.set_alpha(140)
                bg.fill((0, 0, 0))
                screen.blit(bg, (4, 4 + i * 16))
                screen.blit(surf, (4, 4 + i * 16))

        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
