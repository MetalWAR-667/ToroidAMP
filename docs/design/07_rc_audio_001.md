# RC-AUDIO-001 — Decoder Error Isolation & Recovery Specification

## 1. Overview & Problem Statement

During human torture testing of RC-POLISH-001, malformed MP3 files produced low-level mpg123 resync errors (`Illegal Audio-MPEG-Header`, `Giving up resync after 1024 bytes`) followed by `soundfile.LibsndfileError: Unspecified internal error`.

In the legacy architecture:
- Decoder read exceptions escaped directly into the `sounddevice` CFFI audio callback thread.
- Decoder seek exceptions escaped directly into Qt UI seek event handlers.
- A failed decoder could remain active, causing repeated exceptions and tracebacks on subsequent ticks or callbacks.

**RC-AUDIO-001 Principle**:
> The decoder is allowed to die. The player is not.
> Never allow a corrupt file exception to escape through a real-time audio callback.

---

## 2. Hard Boundary Audio Callback Isolation

In `PlayerEngine._audio_callback`:
```python
callback_gen = self._generation
try:
    chunk = self._active_decoder.read_frames(frames)
except Exception as e:
    # HARD BOUNDARY: Silence output immediately and record failure state
    outdata.fill(0)
    with self._lock:
        if self._generation == callback_gen:
            self._decoder_failed = True
            self._last_error_generation = callback_gen
            self._last_error_path = self._current_filepath
            self._last_error_msg = f"Read error: {e}"
            self._state = PlaybackState.STOPPED
            self._fade_state = FadeState.IDLE
            self._fade_envelope = 0.0
    return
```

### Key Guarantees:
1. **Deterministic Silence**: On error, output buffer is immediately filled with zeros (`outdata.fill(0)`).
2. **Zero Allocation / No Heavy Work in Callback**: No GUI calls, no file operations, no string allocations outside error capture.
3. **No Hammering / Spam**: `_decoder_failed` prevents any subsequent calls to `read_frames()` on the broken decoder.

---

## 3. Safe Seek Boundary

In `PlayerEngine.seek(target_seconds)`:
- Returns `bool` (`True` on success, `False` on failure).
- If the current decoder is in a failed state or raises an exception during seek:
  - Captures error into `_decoder_failed` state.
  - Sets playback state to `STOPPED`.
  - Logs a concise warning.
  - Returns `False` cleanly without throwing exceptions into the Qt UI event loop.

---

## 4. Generation Token & Rapid Track Switching Protection

- `_generation: int` increments atomically with every `load()` call.
- Audio callbacks capture `callback_gen = self._generation`.
- When an audio callback catches an exception from a slow/late read, it only flags failure if `self._generation == callback_gen`.
- This ensures rapidly pressing `Next` across multiple tracks cannot allow a late exception from Track A to poison or stop Track B.

---

## 5. Deferred Recovery Policy in UI Thread

In `WindowManager._tick()`:
```python
# 0. Check and Handle Decoder Failure from Audio Thread
has_error, failed_path, error_msg = self.player_engine.check_and_clear_error()
if has_error:
    track_name = os.path.basename(failed_path) if failed_path else "Current Track"
    logger.warning(f"Playback decoder failure on '{track_name}': {error_msg}")
    if len(self.playlist) > 0:
        next_idx = self.playlist.get_next_index()
        if next_idx is not None and next_idx != self.playlist.current_index:
            self._play_index(next_idx)
        else:
            self._stop_playback()
    else:
        self._stop_playback()
```
- Consumes error flag safely via thread-safe `check_and_clear_error()`.
- Logs concise non-intrusive diagnostic.
- Automatically advances to the next track in the playlist if available.
- Player and UI remain 100% operational and responsive.

---

## 6. Analysis Handoff & Fade Contract

- On decoder failure, `AnalysisHandoff` receives pure silence. Visualizers do not receive corrupted audio memory or uninitialized buffers.
- Fade envelope is reset safely to `IDLE` (safety takes precedence over fading corrupted PCM).
- Both `FDE ON` and `FDE OFF` work immediately upon recovery and track transition.
