"""
ToroidAMP - Production Segmented LED Spectrum Analyzer Visualizer
"""

import pygame
from .base import Visualizer
from ..analysis.audio_frame import AudioFrame


class SegmentedSpectrumBarsVisualizer(Visualizer):
    """
    Dedicated 32-Band Segmented LED Spectrum Analyzer with Physics-based
    floating peak-hold caps, tricolor demoscene gradient, and wet floor mirror reflection.
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.w = max(10, width)
        self.h = max(10, height)
        self.num_bars = 32
        self.peaks = [0.0] * self.num_bars
        self.peak_speeds = [0.0] * self.num_bars
        self.smoothed_spectrum = [0.0] * self.num_bars

    def get_id(self) -> str:
        return "segmented_spectrum_bars"

    def get_name(self) -> str:
        return "Spectrum LED Bars"

    def resize(self, width: int, height: int) -> None:
        self.w = max(10, width)
        self.h = max(10, height)

    def update(self, frame: AudioFrame, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None:
        w, h = surface.get_size()
        base_col = (6, 8, 14)
        surface.fill(base_col)
        
        num_bars = self.num_bars
        if len(self.peaks) != num_bars:
            self.peaks = [0.0] * num_bars
            self.peak_speeds = [0.0] * num_bars
            self.smoothed_spectrum = [0.0] * num_bars
            
        margin_x = max(10, int(w * 0.05))
        usable_w = w - 2 * margin_x
        bar_gap = max(2, int(usable_w / (num_bars * 5)))
        bar_w = max(3, (usable_w - (num_bars - 1) * bar_gap) // num_bars)
        
        baseline_y = int(h * 0.74)
        max_bar_h = int(h * 0.62)
        seg_h = max(2, int(h * 0.016))
        seg_gap = 1
        
        for i in range(num_bars):
            src_idx = int((i / num_bars) * len(frame.spectrum))
            src_idx2 = min(len(frame.spectrum) - 1, int(((i + 1) / num_bars) * len(frame.spectrum)))
            if src_idx2 > src_idx:
                raw_val = sum(frame.spectrum[src_idx:src_idx2]) / (src_idx2 - src_idx)
            else:
                raw_val = frame.spectrum[src_idx] if src_idx < len(frame.spectrum) else 0.0
                
            eq_boost = 1.0 + (i / num_bars) * 1.5
            raw_val = min(1.0, raw_val * eq_boost * (1.2 + frame.bass * 0.3))
            
            if raw_val > self.smoothed_spectrum[i]:
                self.smoothed_spectrum[i] = raw_val
            else:
                self.smoothed_spectrum[i] = max(0.0, self.smoothed_spectrum[i] - dt * 2.2)
                
            val = self.smoothed_spectrum[i]
            
            if val >= self.peaks[i]:
                self.peaks[i] = val
                self.peak_speeds[i] = 0.0
            else:
                self.peak_speeds[i] += dt * 3.5
                self.peaks[i] = max(0.0, self.peaks[i] - self.peak_speeds[i] * dt)
                
            x = margin_x + i * (bar_w + bar_gap)
            current_h = int(val * max_bar_h)
            num_segs = max(1, current_h // (seg_h + seg_gap)) if current_h > 0 else 0
            
            for s in range(num_segs):
                frac = s / max(1, (max_bar_h // (seg_h + seg_gap)))
                if frac < 0.5:
                    t = frac * 2.0
                    col = (int(0 * (1-t) + 255 * t), int(240 * (1-t) + 200 * t), int(255 * (1-t) + 20 * t))
                else:
                    t = (frac - 0.5) * 2.0
                    col = (int(255 * (1-t) + 255 * t), int(200 * (1-t) + 30 * t), int(20 * (1-t) + 120 * t))
                    
                sy = baseline_y - (s + 1) * (seg_h + seg_gap)
                pygame.draw.rect(surface, col, (x, sy, bar_w, seg_h))
                
                refl_y = baseline_y + 4 + s * (seg_h + seg_gap)
                if refl_y + seg_h < h:
                    refl_col = (col[0] // 5, col[1] // 5, col[2] // 5)
                    pygame.draw.rect(surface, refl_col, (x, refl_y, bar_w, seg_h))
                    
            if self.peaks[i] > 0.02:
                peak_y = baseline_y - int(self.peaks[i] * max_bar_h) - seg_h - 2
                peak_col = (255, 255, 255) if (frame.strong_beat and i % 4 == 0) else (255, 230, 100)
                pygame.draw.rect(surface, peak_col, (x, peak_y, bar_w, max(2, seg_h // 2)))
                
        pygame.draw.line(surface, (0, 180, 255), (margin_x - 4, baseline_y + 2), (w - margin_x + 4, baseline_y + 2), 2)
