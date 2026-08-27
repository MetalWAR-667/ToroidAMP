"""
ToroidAMP - Shared Production Hardware-Accelerated OpenGL Visualizer Host Canvas

Provides:
- QOpenGLWidget implementation with verified VAO/VBO attribute bindings.
- Direct standard QOpenGLFunctions glUniform* uniform upload.
- AudioFrame and dynamic parameter uniform upload.
- Packaged 2D texture loading with mipmapping.
- Explicit cleanupGL lifecycle hooked to context destruction and closeEvent.
- Zero CPU/GPU background rendering when inactive.
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLTexture,
    QOpenGLVertexArrayObject,
)

from ..analysis.audio_frame import AudioFrame
from .gpu_compiler import (
    FALLBACK_FRAG_SOURCE,
    VERTEX_SHADER_SOURCE,
    ShaderMetadata,
    ShaderParameter,
    classify_and_wrap_source,
)

logger = logging.getLogger("toroidamp.visualizers.gpu")


class GLVisualizerCanvas(QOpenGLWidget):
    """
    Production OpenGL viewport rendering GLSL fragment visualizers with
    live authoring parameter uniform bindings and packaged texture support.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._program: Optional[QOpenGLShaderProgram] = None
        self._fallback_program: Optional[QOpenGLShaderProgram] = None
        self._vbo: Optional[QOpenGLBuffer] = None
        self._vao: Optional[QOpenGLVertexArrayObject] = None

        # Packaged Texture
        self._texture0: Optional[QOpenGLTexture] = None
        self._context_connected: bool = False

        self._start_time = time.time()
        self._last_frame_time = time.time()
        self._frame_count = 0

        # AudioFrame State
        self._current_audio_frame: Optional[AudioFrame] = None

        # Telemetry & Benchmarking
        self.frame_times: List[float] = []
        self.last_render_dt_ms: float = 0.0
        self.last_fps: float = 60.0
        self.last_error_log: str = ""
        self.is_using_fallback: bool = False

        # Current shader source code, path, metadata & active parameters
        self.current_shader_path: Optional[Path] = None
        self.metadata: Optional[ShaderMetadata] = None
        self.active_shader_name: str = "None"
        self.current_params: Dict[str, float] = {}

    def initializeGL(self):
        import numpy as np

        quad_verts = np.array(
            [
                -1.0, -1.0,
                 1.0, -1.0,
                -1.0,  1.0,
                -1.0,  1.0,
                 1.0, -1.0,
                 1.0,  1.0,
            ],
            dtype=np.float32,
        )

        if self._vao is not None:
            self._vao.destroy()
        if self._vbo is not None:
            self._vbo.destroy()

        self._vao = QOpenGLVertexArrayObject(self)
        self._vao.create()
        self._vao.bind()

        self._vbo = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        self._vbo.create()
        self._vbo.bind()
        self._vbo.allocate(quad_verts.tobytes(), quad_verts.nbytes)

        # Build fallback program first to bind attribute pointers to VAO
        self._build_fallback_program()
        if self._fallback_program:
            self._fallback_program.bind()
            self._fallback_program.enableAttributeArray(0)
            self._fallback_program.setAttributeBuffer(0, 0x1406, 0, 2, 0)
            self._fallback_program.release()

        self._vao.release()
        self._vbo.release()

        # Connect context destruction signal for clean GPU resource disposal
        ctx = self.context()
        if ctx and not self._context_connected:
            ctx.aboutToBeDestroyed.connect(self.cleanupGL)
            self._context_connected = True

        # Load packaged texture
        self._load_packaged_texture()

        # If a shader was queued or previously loaded, compile it now with the live context
        if self.current_shader_path and self.current_shader_path.exists():
            self.load_shader_file(self.current_shader_path)

    def cleanupGL(self):
        """Cleanly releases OpenGL textures, VAO, and VBO while the context is active."""
        if not self.isValid():
            return
        self.makeCurrent()
        if self._texture0 is not None:
            self._texture0.destroy()
            self._texture0 = None
        if self._vao is not None:
            self._vao.destroy()
            self._vao = None
        if self._vbo is not None:
            self._vbo.destroy()
            self._vbo = None
        self.doneCurrent()

    def closeEvent(self, event):
        self.cleanupGL()
        super().closeEvent(event)

    def _resolve_packaged_texture_path(self) -> Optional[Path]:
        """Resolves the canonical packaged ToroidAMP master artwork."""
        pkg_dir = Path(__file__).resolve().parent.parent  # src/toroidamp
        candidates = [
            pkg_dir / "assets" / "images" / "ToroidAMP.png",
            pkg_dir / "assets" / "branding" / "toroidamp_icon.png",
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _load_packaged_texture(self):
        """Loads and uploads the packaged ToroidAMP master artwork to OpenGL texture."""
        target_img_path = self._resolve_packaged_texture_path()
        if target_img_path:
            try:
                img = QImage(str(target_img_path))
                if not img.isNull():
                    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
                    img = img.flipped() if hasattr(img, "flipped") else img.mirrored(False, True)
                    self._texture0 = QOpenGLTexture(img)
                    self._texture0.setMinMagFilters(QOpenGLTexture.LinearMipMapLinear, QOpenGLTexture.Linear)
                    self._texture0.generateMipMaps()
                    self._texture0.setWrapMode(QOpenGLTexture.ClampToEdge)
            except Exception as e:
                logger.warning(f"Failed to load packaged texture {target_img_path}: {e}")

    def _build_fallback_program(self):
        prog = QOpenGLShaderProgram(self)
        prog.addShaderFromSourceCode(QOpenGLShader.Vertex, VERTEX_SHADER_SOURCE)
        prog.addShaderFromSourceCode(QOpenGLShader.Fragment, FALLBACK_FRAG_SOURCE)
        if prog.link():
            self._fallback_program = prog
        else:
            logger.warning(f"Fallback shader link failed: {prog.log()}")

    def load_shader_file(self, file_path: Path) -> bool:
        if not file_path.exists():
            self.last_error_log = f"File not found: {file_path}"
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_code = f.read()
        except Exception as e:
            self.last_error_log = f"Failed to read file: {e}"
            return False

        wrapped_code, meta = classify_and_wrap_source(raw_code, file_path.stem)

        if not self.isValid():
            # In headless mode or before showEvent, store metadata and parameters and return True
            self.metadata = meta
            self.current_shader_path = file_path
            self.active_shader_name = meta.name
            new_params = {}
            for p_name, param in meta.parameters.items():
                if p_name in self.current_params:
                    new_params[p_name] = self.current_params[p_name]
                else:
                    new_params[p_name] = param.default_value
            self.current_params = new_params
            return True

        self.makeCurrent()
        new_prog = QOpenGLShaderProgram(self)
        if not new_prog.addShaderFromSourceCode(QOpenGLShader.Vertex, VERTEX_SHADER_SOURCE):
            self.last_error_log = f"Vertex Error:\n{new_prog.log()}"
            return False

        if not new_prog.addShaderFromSourceCode(QOpenGLShader.Fragment, wrapped_code):
            self.last_error_log = f"Fragment Compile Error in {file_path.name}:\n{new_prog.log()}"
            if self._program is None:
                self.is_using_fallback = True
            return False

        if not new_prog.link():
            self.last_error_log = f"Shader Link Error in {file_path.name}:\n{new_prog.log()}"
            if self._program is None:
                self.is_using_fallback = True
            return False

        # Bind VAO and VBO to configure attribute buffer for this new program
        if self._vao and self._vbo:
            self._vao.bind()
            self._vbo.bind()
            new_prog.bind()
            new_prog.enableAttributeArray(0)
            new_prog.setAttributeBuffer(0, 0x1406, 0, 2, 0)
            new_prog.release()
            self._vbo.release()
            self._vao.release()

        # Update authoritative program and metadata only upon link success
        self._program = new_prog
        self.current_shader_path = file_path
        self.metadata = meta
        self.active_shader_name = meta.name
        self.last_error_log = ""
        self.is_using_fallback = False

        new_params = {}
        for p_name, param in meta.parameters.items():
            if p_name in self.current_params:
                new_params[p_name] = self.current_params[p_name]
            else:
                new_params[p_name] = param.default_value
        self.current_params = new_params

        return True

    def reload_current_shader(self) -> bool:
        if self.current_shader_path:
            return self.load_shader_file(self.current_shader_path)
        return False

    def update_audio_frame(self, frame: AudioFrame):
        self._current_audio_frame = frame

    def set_param_value(self, name: str, value: any):
        self.current_params[name] = value

    def reset_params(self):
        if self.metadata:
            for p_name, param in self.metadata.parameters.items():
                self.current_params[p_name] = param.default_value

    def paintGL(self):
        t0 = time.perf_counter()

        now = time.time()
        dt = now - self._last_frame_time
        self._last_frame_time = now
        self._frame_count += 1
        elapsed = now - self._start_time

        gl = self.context().functions()
        w = max(1, self.width())
        h = max(1, self.height())
        gl.glViewport(0, 0, w, h)
        gl.glClearColor(0.02, 0.02, 0.04, 1.0)
        gl.glClear(0x00004000)

        prog = self._program if (self._program and not self.is_using_fallback) else self._fallback_program
        if not prog or not prog.bind():
            return

        # Helper functions for robust standard OpenGL uniform binding
        def set_u_float(name_str: str, val: float):
            loc = prog.uniformLocation(name_str.encode("utf-8"))
            if loc != -1:
                gl.glUniform1f(loc, float(val))

        def set_u_int(name_str: str, val: int):
            loc = prog.uniformLocation(name_str.encode("utf-8"))
            if loc != -1:
                gl.glUniform1i(loc, int(val))

        def set_u_vec2(name_str: str, x: float, y: float):
            loc = prog.uniformLocation(name_str.encode("utf-8"))
            if loc != -1:
                gl.glUniform2f(loc, float(x), float(y))

        def set_u_vec3(name_str: str, x: float, y: float, z: float):
            loc = prog.uniformLocation(name_str.encode("utf-8"))
            if loc != -1:
                gl.glUniform3f(loc, float(x), float(y), float(z))

        def set_u_array(name_str: str, arr: list, count: int):
            loc = prog.uniformLocation(name_str.encode("utf-8"))
            if loc != -1:
                gl.glUniform1fv(loc, count, list(arr))

        # Viewport & Timing
        set_u_vec2("u_resolution", float(w), float(h))
        set_u_float("u_time", float(elapsed))
        set_u_float("u_timeDelta", float(dt))
        set_u_int("u_frame", int(self._frame_count))

        set_u_vec3("iResolution", float(w), float(h), 1.0)
        set_u_float("iTime", float(elapsed))
        set_u_float("iTimeDelta", float(dt))
        set_u_int("iFrame", int(self._frame_count))

        frame = self._current_audio_frame
        if frame is not None:
            set_u_float("taRms", float(frame.rms))
            set_u_float("taPeak", float(frame.peak))
            set_u_float("taBass", float(frame.bass))
            set_u_float("taMids", float(frame.mids))
            set_u_float("taTreble", float(frame.treble))
            set_u_int("taBeat", 1 if frame.beat else 0)
            set_u_int("taStrongBeat", 1 if frame.strong_beat else 0)

            if len(frame.spectrum) == 64:
                set_u_array("taSpectrum", list(frame.spectrum), 64)

            if len(frame.waveform) == 128:
                set_u_array("taWaveform", list(frame.waveform), 128)
        else:
            set_u_float("taRms", 0.0)
            set_u_float("taPeak", 0.0)
            set_u_float("taBass", 0.0)
            set_u_float("taMids", 0.0)
            set_u_float("taTreble", 0.0)
            set_u_int("taBeat", 0)
            set_u_int("taStrongBeat", 0)
            set_u_array("taSpectrum", [0.0] * 64, 64)
            set_u_array("taWaveform", [0.0] * 128, 128)

        set_u_float("taBpm", 130.0)
        set_u_float("taBeatPhase", float((elapsed * 2.166) % 1.0))
        set_u_float("taBarPhase", float((elapsed * 0.541) % 1.0))

        # Dynamic Authoring Uniform Parameters (float, bool, color)
        param_meta_map = self.metadata.parameters if self.metadata else {}
        for p_name, p_val in self.current_params.items():
            meta_p = param_meta_map.get(p_name)
            p_type = meta_p.param_type if meta_p else "float"

            if p_type == "bool":
                b_int = 1 if (p_val is True or p_val == 1 or str(p_val).lower() in ("true", "1")) else 0
                set_u_int(p_name, b_int)
            elif p_type == "color":
                if isinstance(p_val, (tuple, list)) and len(p_val) == 3:
                    set_u_vec3(p_name, float(p_val[0]), float(p_val[1]), float(p_val[2]))
                elif isinstance(p_val, str):
                    from toroidamp.visualizers.gpu_compiler import hex_to_rgb_normalized
                    rgb = hex_to_rgb_normalized(p_val) or (1.0, 1.0, 1.0)
                    set_u_vec3(p_name, rgb[0], rgb[1], rgb[2])
                else:
                    set_u_vec3(p_name, 1.0, 1.0, 1.0)
            else:
                # Default float
                try:
                    set_u_float(p_name, float(p_val))
                except (ValueError, TypeError):
                    set_u_float(p_name, 0.0)

        if self._texture0 and self._texture0.isCreated():
            self._texture0.bind(0)
            set_u_int("taTexture0", 0)

        self._vao.bind()
        gl.glDrawArrays(0x0004, 0, 6)
        self._vao.release()

        if self._texture0 and self._texture0.isCreated():
            self._texture0.release()

        prog.release()

        t1 = time.perf_counter()
        render_ms = (t1 - t0) * 1000.0
        self.last_render_dt_ms = render_ms
        self.frame_times.append(render_ms)
        if len(self.frame_times) > 60:
            self.frame_times.pop(0)

        if dt > 0.0:
            current_instant_fps = 1.0 / dt
            self.last_fps = (self.last_fps * 0.9) + (current_instant_fps * 0.1)
