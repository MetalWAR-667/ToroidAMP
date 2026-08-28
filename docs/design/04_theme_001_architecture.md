# THEME-001 — Architecture & Implementation Specification: Internal Theme Foundation + Cyber Yellow

## 1. Overview & Context

ToroidAMP is establishing an internal theme system featuring two bundled first-party themes:
1. **DEFAULT**: The established dark/cyan neon cyber identity. Must maintain 100% appearance fidelity with no regression.
2. **CYBER YELLOW**: An original industrial / retro-futuristic theme featuring worn yellow painted chassis metal, dark brushed aluminium interiors, high-contrast white text, restrained hazard warning stripes, and the bundled Quantum typography.

This is an **internal theme foundation**, explicitly **NOT a generic skin manager** or dynamic plugin engine.

---

## 2. Styling Audit Findings

### 2.1 QSS & Stylesheet Ownership
- Stylesheets were previously defined locally across individual widget instantiations in `chassis.py`, `modules/base.py`, `modules/playlist_module.py`, `modules/visualizer_module.py`, `fullscreen.py`, and `tray.py`.
- Hardcoded colors included:
  - Cyan `#00f0ff`, `#00ffcc`, `#00e5ff`, `#00ffaa`
  - Deep dark background `#0a0b10`, `#040508`, `#06070a`, `#12141f`, `#141724`, `#181c2c`, `#1a1d2e`
  - Accent magenta/orange `#ff0077`, `#ffaa00`
  - Muted slate text `#8892b0`, `#64748b`, `#4a5270`, `#7882a0`

### 2.2 Painting & Neon System
- `UnifiedChassis` and `ModuleShell` implement custom `paintEvent` rendering:
  - Solid dark rounded rectangle background (`#0a0b10` and `#0d0e15`).
  - Tier 1 outer reactive border (derived from `NeonState.tier1_chassis_color` or fallback `#00f0ff`).
- `ReactiveNeonController` modulates cyan hue ($186^\circ$), shifting toward violet ($285^\circ$) on bass or ice blue ($195^\circ$) on treble. In Cyber Yellow, the reactive neon gracefully adjusts its baseline to industrial yellow/amber while retaining spectral shift dynamics.

### 2.3 Scoped / Isolated Dialogs
- `QColorDialog` in `fullscreen.py` (`_open_styled_color_dialog`) uses an explicit scoped stylesheet to prevent black-text-on-dark-background regression. The theme foundation centralizes color dialog styling while preserving high contrast.

### 2.4 Session Persistence
- `SessionState` in `session.py` persists window coordinates, scale, volume, playlist, and visualizer parameters.
- A `theme_id: str = "default"` field is added to `SessionState`, validated with fallback to `"default"`.

---

## 3. Minimal Theme Architecture (`toroidamp.ui.theme`)

### 3.1 `ThemePalette`
Holds concrete hex/QColor definitions for structural and functional UI elements:
- `bg_chassis`, `bg_panel`, `bg_lcd`, `bg_surface`, `bg_surface_alt`
- `border_chassis`, `border_panel`, `border_control`
- `primary`, `accent`, `warning`, `danger`
- `text_primary`, `text_secondary`, `text_muted`, `text_lcd`, `text_lcd_dim`
- `btn_bg`, `btn_hover_bg`, `btn_pressed_bg`, `btn_border`, `btn_hover_border`, `btn_text`, `btn_hover_text`
- `slider_groove`, `slider_subpage`, `slider_handle`, `slider_handle_border`

### 3.2 `ThemeAssets`
Stores optional paths and preloaded `QPixmap` / `QImage` assets:
- `chassis_bg`: Worn yellow painted metal texture.
- `panel_bg`: Dark brushed aluminium interior texture.
- `hazard_strip`: Industrial caution stripe accent.
- `logo`: Theme-specific ToroidAMP logo.
- `wordmark`: Theme-specific ToroidAMP wordmark.

### 3.3 `ThemeTypography`
- `display_font_family`: Registered font family name (e.g., "Quantum" or fallback "monospace").
- `monospace_font_family`: System monospace font family.

### 3.4 `ThemeDefinition` & `ThemeManager`
- `ThemeDefinition`: Encapsulates `id`, `display_name`, `palette`, `assets`, `typography`, and generator functions for widget stylesheets.
- `ThemeManager`: Singleton holding the registry (`DEFAULT`, `CYBER_YELLOW`), tracking active theme, managing `QFontDatabase` font registration, and emitting `theme_changed(ThemeDefinition)`.

---

## 4. Cyber Yellow Visual Design Strategy

1. **Outer / Structural Chrome**:
   - Chassis and module shell backgrounds draw the worn yellow painted metal texture (`chassis.png`) with crisp dark/amber borders.
2. **Inner Functional Surfaces**:
   - LCD displays, list widgets, and control wells use the dark brushed aluminium interior texture (`panel_brushed_metal.png`) or deep graphite slate (`#121318`).
3. **Typography**:
   - Header identity, badges, and key titles utilize the bundled `Quantum` font.
   - Sliders, time displays, list items, and dense parameters retain clean monospace for 100% legibility.
4. **Restrained Hazard Decoration**:
   - Applied tastefully as an accent line above or alongside the identity header in NORMAL mode and module titlebars.
5. **No Regressions**:
   - DEFAULT reproduces the exact production stylesheets, colors, and neon responsiveness.

---

## 5. Live Theme Switching & Persistence

- Live toggle button `⚡ THM` / `⚡ CYBER` placed in the chassis header.
- Switching live immediately re-applies stylesheets and triggers widget repaints across:
  - `UnifiedChassis` (NORMAL & MINI)
  - `VisualizerModule`
  - `PlaylistModule`
  - `RetinaMeltWindow` (HUD, TUNE, LAB, and dialogs)
- Audio playback, playlist indices, seek position, and visualizer rendering pipelines remain completely undisturbed.
