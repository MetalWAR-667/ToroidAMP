# RC-POLISH-001 — Playback & Core UX Polish Specification

## 1. Overview

RC-POLISH-001 delivers four key release-polish features for the first public executable:
1. **Playback Gain Envelope Fade-In / Fade-Out** (200 ms smooth curve).
2. **Always-Alive Marquee Motion Contract** across MINI, NORMAL, and RETINA MELT.
3. **General Panel Text Readability Pass** (high-contrast semantic tokens).
4. **M3U Action Chooser** (Unified Load M3U / Save M3U8 dialog).

---

## 2. Playback Gain Envelope & Fade Semantics

- **Envelope Duration**: 200 ms (`PlayerEngine.FADE_DURATION_SECONDS = 0.200`).
- **Chain of Execution**:
  ```
  Decoded PCM chunk
      ↓
  Sample-accurate Gain Envelope Interpolation (0.0 to 1.0)
      ↓
  User Master Volume Multiplier
      ↓
  Audio Output Device & Analysis Handoff
  ```
- **State Machine**:
  - `START / RESUME`: Enters `FadeState.FADING_IN`, smoothly ramping envelope from 0.0 to 1.0.
  - `STOP / TRACK TRANSITION`: Triggering `stop()` sets `FadeState.FADING_OUT` if actively playing, reaching silence before stopping stream. Immediate operations (e.g. `load()`, `close()`) use `stop_immediate()` to cleanly prevent buffer bleeding.
  - Master volume remains 100% decoupled from fade envelope state.

---

## 3. Always-Alive Marquee Motion Contract

- **Motion Philosophy**: No title remains static in ToroidAMP or RETINA MELT.
- **Overflowing Titles**:
  - `max_offset = (text_width - visible_width) + 28px` (travels leftward to reveal obscured text, dwells 1200ms at endpoints).
- **Short / Non-Overflowing Titles**:
  - `max_offset = min(28px, spare_width)` (restrained gentle drift rightward across the open viewport space).
- **Parity**: Exactly identical unified `MarqueeLabel` component utilized across `UnifiedChassis` (NORMAL & MINI) and `RetinaMeltWindow` (RETINA MELT HUD).

---

## 4. Panel Text Readability Architecture

- Updated `ThemePalette` tokens to promote informational text from dim slate to bright readable tones:
  - `text_secondary`: `#e2e8f0` (Default) / `#f3f4f6` (Cyber Yellow).
  - `text_muted`: `#cbd5e1` (Default) / `#d1d5db` (Cyber Yellow).
  - `list_item_text`: `#e2e8f0` (Default) / `#f3f4f6` (Cyber Yellow).
  - Preserved semantic hierarchy: Primary text/headers (White/Cyan/Yellow), Secondary (Near-white), Disabled (Subdued).

---

## 5. M3U Action Chooser & Serialization Policy

- Single compact `M3U` button opens a styled Qt popup menu:
  - `LOAD M3U PLAYLIST`: Opens file chooser for `.m3u` / `.m3u8` files.
  - `SAVE M3U8 PLAYLIST`: Opens save dialog targeting `.m3u8` extended format.
- **Format**: Standard Extended `#EXTM3U` format with `#EXTINF:<seconds>,<title>` and UTF-8 path serialization.
- **Path Policy**: Canonical absolute paths for reliable multi-directory portability across sessions.

---

## 6. FDE (Playback Fade) A/B Control & Session Persistence

- **User Control**: Added compact checkable `FDE` toggle button immediately before `VIS` in the NORMAL chassis control bar.
- **Behavior**:
  - `Checked (FDE ON)`: Active fade-in (200 ms) and fade-out envelope.
  - `Unchecked (FDE OFF)`: Direct immediate start/stop (`fade_gain = 1.0`), bypassing envelope interpolation.
- **Scope & Persistence**:
  - Global playback preference (`fade_enabled: bool = True`), persisted across restarts in `session.json`.
  - MINI and RETINA MELT inherit the global setting automatically without redundant controls.
