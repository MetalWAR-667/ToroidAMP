# ToroidAMP — FIX-001: Startup, Lifecycle & Voice Identity Report

> **"ToroidAMP has three distinct lifecycle operations: MINI (visible compact mode), MINIMIZE (hide to tray, keep playing), and CLOSE (actually exit ToroidAMP)."**
> **"ToroidAMP... It really warps the toroid's ass!"**

---

## 1. Executive Summary

FIX-001 corrects startup, window lifecycle, and playlist restoration decisions based on authoritative human feedback:
1. **Window Close (`✕`) = EXIT**: Clicking `✕` on the chassis title bar immediately executes the full application shutdown sequence, stopping all audio, saving session data, closing windows, and terminating the process.
2. **Minimize (`─`) = HIDE TO TRAY**: Minimizing gets ToroidAMP out of the way into the system tray while playback continues uninterrupted.
3. **MINI ($380 \times 36\text{ px}$)**: Preserved as the compact visible desktop experience scale (NOT an OS minimize).
4. **Startup Empty-State Contract**: On startup, ToroidAMP restores the playlist and settings, but leaves `current_track = NONE` and `state = STOPPED`.
5. **Playlist Sanitization**: Restored playlists are rigorously validated; any non-existent/dead paths are permanently purged so `Next` / `Previous` never fail on missing files.
6. **Voice Identity Announcement & Robotic Parity**: Recreated the exact `MetalWar-Installer` voice synthesis recipe in `VoiceService` with robotic dual-channel stereo delay ($20\text{ ms}$ channel delay, $0.9$ secondary volume) to speak the iconic demoscene motto at startup (`"ToroidAMP... It really warps the toroid's ass!"`).
7. **Canonical Session Path**: Fixed duplicated nested directories (`ToroidAMP\ToroidAMP`), establishing single canonical path `%LOCALAPPDATA%/ToroidAMP/session.json` with seamless migration.


---

## 2. Lifecycle Architecture: MINI vs. MINIMIZE vs. CLOSE

```text
┌──────────────┐     Toggle Scale
│    NORMAL    │ ◄────────────────► ┌──────────────┐
│  420 × 135   │                    │     MINI     │
└──────┬───────┘                    │   380 × 36   │
       │                            └──────┬───────┘
       │ Minimize [─]                      │ Minimize [─]
       ▼                                   ▼
┌──────────────────────────────────────────────────┐
│              SYSTEM TRAY (HIDDEN)                │
│             Playback Continues Alive             │
└──────────────────────┬───────────────────────────┘
                       │ Restore
                       ▼
                 Last UI Scale
```

```text
Close [✕] (from NORMAL, MINI, or Tray Menu)
       ↓
Save Session Atomically
       ↓
Stop Timers (Render & Snap)
       ↓
Stop PlayerEngine & Close sounddevice stream
       ↓
Release Decoders & Native Handles
       ↓
Destroy Windows & Remove Tray Icon
       ↓
Terminate Process (Process Dead)
```

---

## 3. MetalWAR-Installer Voice Audit & ToroidAMP VoiceService

### Audit Findings:
* `MetalWar-Installer` uses `pyttsx3` with female voice filtering (`"zira"`), saving to a temporary `.wav` file, and playing via `pygame.mixer.Sound`.
* In ToroidAMP, we adapted this into an isolated [`VoiceService`](file:///C:/ToroidAMP/ToroidAMP/src/toroidamp/audio/voice.py) running in a background daemon thread (`ToroidAMP-VoiceThread`).
* Output is streamed via `sounddevice` and `soundfile`, cleaning up temporary `.wav` files upon completion.
* **Failure Isolation**: If `pyttsx3` or OS TTS is unavailable, the failure is caught gracefully without blocking UI initialization.
* **Non-Music Invariant**: The startup phrase does not touch `PlaylistManager`, `AudioFrame`, or `ToroidVisualizer`.

---

## 4. Command-Line Media Policy

* `toroidamp`: Launches application, restores valid queue in empty/stopped state, speaks startup bark, and waits for user input.
* `toroidamp "song.mp3"`: Explicit media supplied by user overrides the empty-startup rule, bypasses the startup bark, populates the queue, and begins playback immediately.

---

## 5. Test Suite & Verification Results

* **Regression Test Suite**: [`tests/test_fix_001.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_fix_001.py)
  * `test_playlist_sanitization_and_traversal`: **PASS**
  * `test_startup_empty_state_and_session_restore`: **PASS**
  * `test_lifecycle_separation_mini_minimize_close`: **PASS**
  * `test_voice_service_isolation`: **PASS**
* **Integration Tests**:
  * [`tests/test_production_cut1b.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_production_cut1b.py): **PASS (100%)**
  * [`tests/test_production_cut2.py`](file:///C:/ToroidAMP/ToroidAMP/tests/test_production_cut2.py): **PASS (100%)**
* **Manual End-to-End Test**:
  * Verified startup speech, empty state, play activation, hide to tray on `─`, and immediate process termination on `✕`.

---

## 6. Future Bark Extension Seams
* The isolated `VoiceService` design provides clean extension hooks for future personality barks (e.g. RETINA MELT transitions, decoder warnings) without polluting the core DSP audio engine.
