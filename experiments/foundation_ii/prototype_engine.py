"""
ToroidAMP - Foundation II Prototype Engine
Dual-Source Audio Pipeline & Tracker PCM Prototype
"""

from dataclasses import dataclass
import threading
import time
import os
import ctypes
import numpy as np
import soundfile as sf
import sounddevice as sd
import pygame


@dataclass(slots=True)
class AudioFrame:
    """
    Normalized downstream contract delivered to visualizers.
    Derived purely from real-time decoded PCM.
    """
    rms: float             # Overall loudness [0.0 - 1.0]
    peak: float            # Peak sample amplitude [0.0 - 1.0]
    bass: float            # Sub/Bass energy [20 - 250 Hz] [0.0 - 1.0]
    mids: float            # Midrange energy [250 - 4000 Hz] [0.0 - 1.0]
    treble: float          # High frequency energy [4000 - 20000 Hz] [0.0 - 1.0]
    spectrum: list[float]  # 64-bin normalized log-spaced spectrum [0.0 - 1.0]
    waveform: list[float]  # 128-point subsampled normalized mono waveform [-1.0 - 1.0]
    beat: bool             # Transient threshold trigger
    strong_beat: bool      # Heavy kick transient trigger


class AnalysisHandoff:
    """
    Ultra-low latency thread-safe handoff between high-priority audio callback
    and visualization consumer thread.
    """
    def __init__(self, buffer_frames: int = 2048):
        self.buffer_frames = buffer_frames
        self._buffer = np.zeros((buffer_frames, 2), dtype=np.float32)
        self._lock = threading.Lock()
        
        # Energy history for dynamic beat detection
        self._energy_history = []
        self._last_beat_time = 0.0

    def push_audio(self, pcm_chunk: np.ndarray):
        """Called from audio output stream thread (~10-15us)."""
        n = len(pcm_chunk)
        with self._lock:
            if n >= self.buffer_frames:
                self._buffer[:] = pcm_chunk[-self.buffer_frames:]
            else:
                self._buffer[:-n] = self._buffer[n:]
                self._buffer[-n:] = pcm_chunk

    def get_audio_frame(self, sr: int = 44100) -> AudioFrame:
        """Called from visualizer update timer (~50-100us)."""
        with self._lock:
            pcm = self._buffer.copy()

        mono = np.mean(pcm, axis=1) if pcm.ndim > 1 else pcm
        n = len(mono)

        # 1. Amplitude metrics
        rms = float(np.sqrt(np.mean(mono**2)))
        peak = float(np.max(np.abs(mono)))

        # 2. Windowed FFT
        window = np.hanning(n)
        windowed = mono * window
        fft_complex = np.fft.rfft(windowed)
        # Normalized magnitude
        fft_mag = (np.abs(fft_complex) / (n / 2.0)) * 4.0 # visual scaling
        freqs = np.fft.rfftfreq(n, 1.0 / sr)

        # Frequency bands
        bass_mask = (freqs >= 20) & (freqs <= 250)
        bass = min(1.0, float(np.mean(fft_mag[bass_mask]) * 3.0)) if np.any(bass_mask) else 0.0

        mids_mask = (freqs > 250) & (freqs <= 4000)
        mids = min(1.0, float(np.mean(fft_mag[mids_mask]) * 4.0)) if np.any(mids_mask) else 0.0

        treble_mask = (freqs > 4000) & (freqs <= 20000)
        treble = min(1.0, float(np.mean(fft_mag[treble_mask]) * 6.0)) if np.any(treble_mask) else 0.0

        # Spectrum (64 log-spaced bins)
        bin_edges = np.geomspace(20, min(20000, sr / 2), 65)
        spectrum_bins = []
        for i in range(64):
            b_mask = (freqs >= bin_edges[i]) & (freqs < bin_edges[i + 1])
            val = float(np.mean(fft_mag[b_mask])) if np.any(b_mask) else 0.0
            spectrum_bins.append(min(1.0, val * 2.5))

        # Waveform (128 samples)
        step = max(1, n // 128)
        waveform = [float(x) for x in mono[::step][:128]]

        # 3. Dynamic Energy Beat Detection
        now = time.time()
        instant_energy = rms ** 2
        self._energy_history.append(instant_energy)
        if len(self._energy_history) > 40:
            self._energy_history.pop(0)

        avg_energy = float(np.mean(self._energy_history)) if self._energy_history else 0.001
        variance = float(np.var(self._energy_history)) if self._energy_history else 0.0
        # Dynamic threshold coefficient
        c = max(1.2, 1.5 - variance * 10)
        
        is_beat = False
        is_strong_beat = False
        if instant_energy > c * avg_energy and (now - self._last_beat_time) > 0.18:
            is_beat = True
            self._last_beat_time = now
            if bass > 0.4:
                is_strong_beat = True

        return AudioFrame(
            rms=min(1.0, rms * 1.5),
            peak=min(1.0, peak),
            bass=bass,
            mids=mids,
            treble=treble,
            spectrum=spectrum_bins,
            waveform=waveform,
            beat=is_beat,
            strong_beat=is_strong_beat
        )


class ModPlugDecoder:
    """Native tracker decoder using libmodplug CFFI/ctypes."""
    def __init__(self, modplug_dll_path: str):
        self.dll = ctypes.CDLL(modplug_dll_path)
        self.dll.ModPlug_Load.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self.dll.ModPlug_Load.restype = ctypes.c_void_p
        self.dll.ModPlug_Unload.argtypes = [ctypes.c_void_p]
        self.dll.ModPlug_Unload.restype = None
        self.dll.ModPlug_Read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        self.dll.ModPlug_Read.restype = ctypes.c_int
        self.dll.ModPlug_GetName.argtypes = [ctypes.c_void_p]
        self.dll.ModPlug_GetName.restype = ctypes.c_char_p
        self.dll.ModPlug_GetLength.argtypes = [ctypes.c_void_p]
        self.dll.ModPlug_GetLength.restype = ctypes.c_int
        self.dll.ModPlug_Seek.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.dll.ModPlug_Seek.restype = None

    def load_file(self, filepath: str):
        with open(filepath, "rb") as f:
            data = f.read()
        handle = self.dll.ModPlug_Load(data, len(data))
        if not handle:
            raise RuntimeError(f"Failed to load tracker file: {filepath}")
        return handle

    def unload(self, handle):
        if handle:
            self.dll.ModPlug_Unload(handle)

    def read_pcm_chunk(self, handle, frames: int) -> np.ndarray:
        """Reads interleaved 16-bit stereo PCM and normalizes to float32 [-1.0, 1.0]."""
        bytes_needed = frames * 4 # 2 channels * 2 bytes/sample
        buf = ctypes.create_string_buffer(bytes_needed)
        bytes_read = self.dll.ModPlug_Read(handle, buf, bytes_needed)
        if bytes_read <= 0:
            return np.zeros((0, 2), dtype=np.float32)
        int16_arr = np.frombuffer(buf[:bytes_read], dtype=np.int16)
        float32_pcm = (int16_arr.astype(np.float32) / 32768.0).reshape(-1, 2)
        return float32_pcm


class DualEnginePlayer:
    """
    Unified playback engine providing sample-accurate float32 PCM output
    for both conventional files (MP3/OGG/WAV/FLAC) and tracker files (MOD/XM/IT/S3M).
    """
    def __init__(self, modplug_dll_path: str):
        self.modplug = ModPlugDecoder(modplug_dll_path)
        self.handoff = AnalysisHandoff(2048)
        self.sr = 44100
        
        self.is_tracker = False
        self.conventional_data = None
        self.cursor = 0
        self.tracker_handle = None
        
        self.is_playing = False
        self.stream = None
        self._lock = threading.Lock()

    def load_track(self, filepath: str):
        self.stop()
        ext = os.path.splitext(filepath)[1].lower()
        self.is_tracker = ext in [".mod", ".xm", ".it", ".s3m"]

        if self.is_tracker:
            self.tracker_handle = self.modplug.load_file(filepath)
            self.conventional_data = None
        else:
            data, sr = sf.read(filepath, dtype="float32")
            if len(data.shape) == 1:
                data = np.column_stack((data, data))
            self.conventional_data = data
            self.sr = sr
            self.cursor = 0

    def play(self):
        if self.stream is None:
            self.stream = sd.OutputStream(
                samplerate=self.sr,
                channels=2,
                dtype="float32",
                callback=self._audio_callback,
                blocksize=512
            )
            self.stream.start()
        self.is_playing = True

    def pause(self):
        self.is_playing = False

    def stop(self):
        self.is_playing = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.tracker_handle:
            self.modplug.unload(self.tracker_handle)
            self.tracker_handle = None
        self.cursor = 0

    def _audio_callback(self, outdata, frames, time_info, status):
        if not self.is_playing:
            outdata.fill(0)
            return

        if self.is_tracker and self.tracker_handle:
            chunk = self.modplug.read_pcm_chunk(self.tracker_handle, frames)
            if len(chunk) < frames:
                if len(chunk) > 0:
                    outdata[:len(chunk)] = chunk
                outdata[len(chunk):].fill(0)
            else:
                outdata[:] = chunk
            self.handoff.push_audio(outdata)
        elif self.conventional_data is not None:
            total_len = len(self.conventional_data)
            if self.cursor >= total_len:
                outdata.fill(0)
                self.is_playing = False
                return

            end = min(total_len, self.cursor + frames)
            chunk = self.conventional_data[self.cursor:end]
            if len(chunk) < frames:
                outdata[:len(chunk)] = chunk
                outdata[len(chunk):].fill(0)
                self.cursor = total_len
            else:
                outdata[:] = chunk
                self.cursor += frames
            self.handoff.push_audio(outdata)
        else:
            outdata.fill(0)


class Toroid3DVisualizer:
    """
    Extracted from MetalWar-Installer GeometricTransformer3D.
    Directly driven by real AudioFrame signals and demoscene archaeological fckvar.
    """
    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self.rows = 24
        self.cols = 36
        self.plasma_time = 0.0
        self.ghost_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        self._gen_torus_geometry()

    def _gen_torus_geometry(self):
        self.base_vertices = []
        self.edges = []
        R, r_torus = 1.0, 0.45
        
        for i in range(self.rows):
            u = i / self.rows
            theta = u * 2 * np.pi
            for j in range(self.cols):
                v = j / self.cols
                phi = v * 2 * np.pi
                
                common = R + r_torus * np.cos(phi)
                x = common * np.cos(theta)
                y = common * np.sin(theta)
                z = r_torus * np.sin(phi)
                self.base_vertices.append((x, y, z))

        for i in range(self.rows):
            row_start = i * self.cols
            next_row = ((i + 1) % self.rows) * self.cols
            for j in range(self.cols):
                curr = row_start + j
                right = row_start + ((j + 1) % self.cols)
                down = next_row + j
                self.edges.append((curr, right))
                self.edges.append((curr, down))

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float):
        self.plasma_time += dt * (1.0 + frame.mids * 2.0)
        
        # -------------------------------------------------------------
        # DEMOSCENE ARCHAEOLOGICAL COMPATIBILITY
        # Historical variable controlling musical deformation & irresponsibility
        # -------------------------------------------------------------
        beat_boost = 1.6 if frame.strong_beat else (0.8 if frame.beat else 0.0)
        fckvar = (frame.bass * 1.5) + (frame.rms * 0.5) + beat_boost
        # -------------------------------------------------------------

        # Dynamic rotation speed driven by mids & fckvar
        rot_speed = dt * (1.2 + fckvar * 1.5)
        self.rot_x += rot_speed * 0.7
        self.rot_y += rot_speed * 1.0
        self.rot_z += rot_speed * 0.3

        cx, cy = self.w // 2, self.h // 2
        fov = 480 + (fckvar * 80)
        scale_pulse = 1.0 + (frame.bass * 0.4) + (0.3 if frame.strong_beat else 0.0)

        # 3D Rotation matrices
        c_x, s_x = np.cos(self.rot_x), np.sin(self.rot_x)
        c_y, s_y = np.cos(self.rot_y), np.sin(self.rot_y)
        c_z, s_z = np.cos(self.rot_z), np.sin(self.rot_z)

        projected = []
        depths = []

        # Jitter active when fckvar exceeds threshold
        jitter_active = fckvar > 1.2
        
        for idx, (bx, by, bz) in enumerate(self.base_vertices):
            x = bx * scale_pulse
            y = by * scale_pulse
            z = bz * scale_pulse

            # Waveform vertex modulation
            wave_mod = frame.waveform[idx % len(frame.waveform)] * 0.15 * fckvar
            x += wave_mod
            y += wave_mod

            if jitter_active:
                x += np.random.uniform(-0.04, 0.04) * fckvar
                y += np.random.uniform(-0.04, 0.04) * fckvar

            # Y-rotation
            rx = x * c_y - z * s_y
            rz = x * s_y + z * c_y
            ry = y

            # X-rotation
            new_ry = ry * c_x - rz * s_x
            rz = ry * s_x + rz * c_x
            ry = new_ry

            # Z-rotation
            new_rx = rx * c_z - ry * s_z
            ry = rx * s_z + ry * c_z
            rx = new_rx

            depths.append(rz)
            divisor = 3.5 + rz
            if abs(divisor) < 0.01:
                divisor = 0.01
            factor = fov / divisor
            projected.append((int(rx * factor + cx), int(ry * factor + cy)))

        min_z, max_z = min(depths), max(depths)
        z_range = max(0.01, max_z - min_z)

        # Draw wireframe edges
        for p1_idx, p2_idx in self.edges:
            p1 = projected[p1_idx]
            p2 = projected[p2_idx]
            
            avg_z = (depths[p1_idx] + depths[p2_idx]) * 0.5
            norm_z = 1.0 - ((avg_z - min_z) / z_range)
            
            # Plasma color calculation with fckvar distortion
            heat = min(1.0, (norm_z * 0.5) + (frame.bass * 0.5) + (fckvar * 0.2))
            r = int(min(255, 30 + heat * 225 + (100 if frame.strong_beat else 0)))
            g = int(min(255, 100 + (1.0 - heat) * 155 + frame.mids * 100))
            b = int(min(255, 180 + frame.treble * 75))
            
            thickness = 1
            if heat > 0.7 or frame.strong_beat:
                thickness = 2
            if fckvar > 1.4:
                thickness = 3

            pygame.draw.line(surface, (r, g, b), p1, p2, thickness)

        # Ghosting effect on strong beats
        if frame.strong_beat or fckvar > 1.3:
            self.ghost_surf.fill((0, 0, 0, 0))
            g_offset = int(fckvar * 6)
            for p1_idx, p2_idx in self.edges[::4]:
                p1 = projected[p1_idx]
                p2 = projected[p2_idx]
                gp1 = (p1[0] + np.random.randint(-g_offset, g_offset), p1[1] + np.random.randint(-g_offset, g_offset))
                gp2 = (p2[0] + np.random.randint(-g_offset, g_offset), p2[1] + np.random.randint(-g_offset, g_offset))
                pygame.draw.line(self.ghost_surf, (0, 255, 230, 90), gp1, gp2, 1)
            surface.blit(self.ghost_surf, (0, 0))
