"""
ToroidAMP - EXP-GL-001 Benchmark & Validation Engine
Measures accurate GPU frame times at 420x240, 800x600, 1280x720, and 1920x1080
for Shader A (Plasma), Shader B (Raymarcher), and Shader C (Shadertoy tunnel).
"""

import sys
import time
from pathlib import Path
import numpy as np

# Ensure repository paths
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtCore import QTimer
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from experiments.gpu_visualizers.lab_app import GLVisualizerCanvas
from toroidamp.analysis.audio_frame import AudioFrame


def run_benchmark():
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication.instance() or QApplication(sys.argv)
    
    shader_dir = repo_root / "experiments" / "gpu_visualizers" / "shaders"

    canvas = GLVisualizerCanvas()
    canvas.show()
    app.processEvents()

    resolutions = [
        (420, 240, "Windowed Default (420x240)"),
        (800, 600, "Medium Scale (800x600)"),
        (1280, 720, "HD 720p (1280x720)"),
        (1920, 1080, "Full HD 1080p (1920x1080)")
    ]

    shaders = [
        ("shader_a_plasma.frag", "Shader A: Cyber Plasma"),
        ("shader_b_raymarch.frag", "Shader B: Hyper Torus Raymarch"),
        ("shader_c_shadertoy.frag", "Shader C: Shadertoy Level-1 Tunnel")
    ]

    synth_frame = AudioFrame(
        rms=0.7, peak=0.9, bass=0.8, mids=0.5, treble=0.6,
        spectrum=tuple([0.5]*64), waveform=tuple([0.0]*128),
        beat=True, strong_beat=True
    )
    canvas.update_audio_frame(synth_frame)

    print("================================================================================")
    print(" TOROIDAMP — EXP-GL-001 GPU BENCHMARK (PySide6 + QOpenGLWidget)")
    print("================================================================================")

    results = {}

    for s_file, s_name in shaders:
        s_path = shader_dir / s_file
        canvas.load_shader_file(s_path)
        print(f"\n--- Benchmarking: {s_name} ({s_file}) ---")
        
        results[s_file] = {}

        for w, h, desc in resolutions:
            canvas.resize(w, h)
            app.processEvents()

            # Warm up
            for _ in range(15):
                canvas.repaint()
                app.processEvents()

            # Measure full render cycles via canvas.repaint()
            times_ms = []
            num_frames = 60
            
            for _ in range(num_frames):
                t0 = time.perf_counter()
                canvas.repaint()
                t1 = time.perf_counter()
                times_ms.append((t1 - t0) * 1000.0)
                app.processEvents()

            avg_ms = float(np.mean(times_ms))
            p95_ms = float(np.percentile(times_ms, 95))
            min_ms = float(np.min(times_ms))
            max_ms = float(np.max(times_ms))
            approx_fps = 1000.0 / avg_ms if avg_ms > 0 else 9999.0

            results[s_file][f"{w}x{h}"] = {
                "avg_ms": avg_ms,
                "p95_ms": p95_ms,
                "min_ms": min_ms,
                "max_ms": max_ms,
                "fps": approx_fps
            }

            print(f"[{w:4d}x{h:4d}] {desc:32s} | Frame: {avg_ms:5.3f} ms | p95: {p95_ms:5.3f} ms | ~{approx_fps:6.1f} FPS")

    canvas.close()
    print("\n================================================================================")
    print(" BENCHMARK COMPLETED SUCCESSFULLY.")
    print("================================================================================")
    return results


if __name__ == "__main__":
    run_benchmark()
