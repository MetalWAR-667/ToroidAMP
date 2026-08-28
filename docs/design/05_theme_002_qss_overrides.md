# THEME-002 — Editable QSS Override Foundation

## 1. Overview & Architecture

THEME-002 establishes an optional, human-editable stylesheet override layer (`theme.qss`) on top of the ToroidAMP internal theme foundation (`ThemeDefinition`).

### Hierarchy & Style Cascade Order:
```
ThemeDefinition (Python Palette & Typography)
    ↓
Generated / Programmatic Base Styling (Semantic selectors & Fallbacks)
    ↓
Optional theme.qss (User-editable stylesheet override)
    ↓
Final Qt Presentation (Rendered UI)
```

---

## 2. Style Cascade & Ownership Model

- **ThemeDefinition is Authoritative Base**: Color defaults, typography, raster textures, and reactive neon parameters are defined centrally in Python contracts.
- **QSS is an Override Layer**: `theme.qss` allows end-users and designers to tweak specific visual properties (e.g., text colors, slider highlights, button borders) directly without editing Python source code.
- **Safe Fallback**: If `theme.qss` is missing, unreadable, or empty, ToroidAMP operates normally using the base programmatic styling without errors or disruptions.

---

## 3. Supported Editable Surface in Initial Cut

The initial editable surface targets key NORMAL chassis elements and PLAYLIST action controls:

### NORMAL Core Player:
- `QLabel#normalVersion`: Version text beside the branding wordmark.
- `QLabel#normalTrackTitle`: Track title marquee inside the dark LCD rack.
- `QLabel#normalTimeDisplay`: Track elapsed / total time telemetry.
- `QLabel#normalVolumeLabel`: Volume label (`VOL`).
- `QSlider#normalVolumeSlider`: Volume slider subpage fill and handle border.
- `QSlider#normalSeekSlider`: Track seek progress slider.
- `QPushButton#normalBtnTheme`, `#normalBtnMini`, `#normalBtnMelt`: Top-right utility buttons.
- `QPushButton#normalBtnPrev`, `#normalBtnPlay`, `#normalBtnStop`, `#normalBtnNext`: Transport controls.

### PLAYLIST Module:
- `QPushButton[themeRole="playlistAction"]`: Action buttons (`+ADD`, `-DEL`, `CLR`, `SHF`, `REP`, `M3U`).
  - Supports standard pseudo-classes: `:hover`, `:pressed`, `:checked` (for toggled repeat/shuffle), `:disabled`.

---

## 4. How to Edit Theme Colors

1. Open `src/toroidamp/assets/themes/<theme_id>/theme.qss` in any text editor.
2. Modify the target color hex values (e.g., change `QLabel#normalTrackTitle { color: #ff2a4b; }` to another color).
3. Save the file.
4. Restart ToroidAMP (or toggle themes) to load the changes.

---

## 5. Scope & Deferred Future Capabilities

- **Not a Skin Manager**: THEME-002 does not introduce runtime skin loaders, theme marketplace/discovery, or hot-reload file watchers.
- **Future `user_themes/` Direction (DEFERRED)**: Future milestones may introduce arbitrary user theme directory scanning (`user_themes/<name>/theme.json` + `theme.qss`), but that is strictly deferred beyond THEME-002.
