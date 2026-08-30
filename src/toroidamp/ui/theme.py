"""
ToroidAMP - Minimal Internal Theme Foundation
Provides concrete ThemeDefinition contracts, palettes, packaged asset loading,
custom font registration, and reactive theme switching for bundled themes.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QColor, QFontDatabase, QImage, QPixmap

from ..resources import resolve_package_asset

logger = logging.getLogger("toroidamp.theme")


@dataclass
class ThemePalette:
    """Concrete color definitions for player chrome and UI components."""
    # Backgrounds
    bg_chassis: QColor = field(default_factory=lambda: QColor(10, 11, 16, 250))
    bg_module: QColor = field(default_factory=lambda: QColor(13, 14, 21, 250))
    bg_lcd: str = "#040508"
    bg_surface: str = "#12141f"
    bg_surface_alt: str = "#141724"
    bg_control: str = "#12141f"
    bg_control_hover: str = "#161c2e"
    bg_control_pressed: str = "#00f0ff"
    
    # Borders & Outlines
    border_chassis_default: QColor = field(default_factory=lambda: QColor(0, 240, 255, 220))
    border_module_default: QColor = field(default_factory=lambda: QColor(0, 240, 255, 180))
    border_panel: str = "#1a2233"
    border_control: str = "#1f273d"
    border_control_hover: str = "#00f0ff"
    
    # Primary & Accents
    primary: str = "#00f0ff"
    accent: str = "#ff0077"
    warning: str = "#ffaa00"
    danger: str = "#ff0055"
    
    # Typography Colors
    text_primary: str = "#ffffff"
    text_secondary: str = "#e2e8f0"
    text_muted: str = "#cbd5e1"
    text_dim: str = "#94a3b8"
    text_lcd: str = "#00ffcc"
    text_lcd_time: str = "#ffaa00"
    
    # Surface-Aware Foreground & Controls (e.g. for light painted chassis vs dark panels)
    text_on_chassis: str = "#00f0ff"
    text_on_chassis_muted: str = "#64748b"
    bg_control_on_chassis: str = "#141724"
    border_control_on_chassis: str = "#1f273d"
    text_control_on_chassis: str = "#cbd5e1"
    
    # Chips
    chip_vis_bg: str = "#0d111c"
    chip_vis_border: str = "#1f2a40"
    chip_vis_text: str = "#00f0ff"
    chip_vis_active_bg: str = "#00f0ff"
    chip_vis_active_text: str = "#040508"
    
    chip_pl_bg: str = "#140d17"
    chip_pl_border: str = "#3d1f2e"
    chip_pl_text: str = "#ff0077"
    chip_pl_active_bg: str = "#ff0077"
    chip_pl_active_text: str = "#ffffff"
    
    # Sliders
    slider_groove: str = "#1a1d2e"
    slider_subpage: str = "#00f0ff"
    slider_handle: str = "#ffffff"
    slider_handle_border: str = "#00f0ff"
    
    # Lists
    list_bg: str = "#06070a"
    list_border: str = "#1a1d2e"
    list_item_text: str = "#e2e8f0"
    list_item_border: str = "#11131c"
    list_selected_bg: str = "#141a2e"
    list_selected_text: str = "#00f0ff"
    list_hover_bg: str = "#0f121d"
    list_hover_text: str = "#00e5ff"


@dataclass
class ThemeAssets:
    """Packaged raster assets and optional stylesheets for theme chrome."""
    chassis_image_path: Optional[Path] = None
    panel_image_path: Optional[Path] = None
    hazard_strip_path: Optional[Path] = None
    logo_image_path: Optional[Path] = None
    wordmark_image_path: Optional[Path] = None
    qss_path: Optional[Path] = None
    
    # Pre-cached Pixmaps (lazy-loaded)
    _pixmap_cache: Dict[str, QPixmap] = field(default_factory=dict, repr=False)
    
    def get_pixmap(self, asset_name: str) -> Optional[QPixmap]:
        path = getattr(self, f"{asset_name}_path", None) or getattr(self, f"{asset_name}_image_path", None)
        if not path or not path.is_file():
            return None
        key = str(path)
        if key not in self._pixmap_cache:
            pm = QPixmap(key)
            if not pm.isNull():
                self._pixmap_cache[key] = pm
            else:
                return None
        return self._pixmap_cache[key]


@dataclass
class ThemeTypography:
    """Resolved font families for display and standard controls."""
    display_family: str = "monospace"
    monospace_family: str = "monospace"
    has_custom_display_font: bool = False


@dataclass
class ThemeDefinition:
    """
    Complete bundle specification for a ToroidAMP player theme.
    """
    id: str
    display_name: str
    palette: ThemePalette
    assets: ThemeAssets
    typography: ThemeTypography
    is_image_backed: bool = False
    qss_override: str = ""


def resolve_theme_asset_path(theme_id: str, relative_subpath: str | Path) -> Optional[Path]:
    """Resolves a theme-specific asset path safely (RC-069-002: delegates to the shared package-asset resolver)."""
    rel = Path(f"assets/themes/{theme_id}") / relative_subpath
    return resolve_package_asset(rel)


def disconnect_theme_listener(signal_instance, slot) -> None:
    """
    Best-effort disconnect of a `ThemeManager.theme_changed` listener.

    ThemeManager is a process-wide singleton (ThemeManager.get_instance()),
    so a widget's connection to it is the only thing keeping the singleton
    aware the widget exists. Intended for use as a QObject.destroyed slot
    (guaranteed to fire for every destruction path, including Qt's own
    parent-child cascade, unlike a Python-level deleteLater() override)
    so the singleton never retains a connection to an already-destroyed
    C++ object.
    """
    try:
        signal_instance.disconnect(slot)
    except Exception:
        pass


class ThemeManager(QObject):
    """
    Central Registry and Lifecycle Controller for ToroidAMP themes.
    Maintains registered bundled themes and broadcasts theme change events.
    """
    theme_changed = Signal(object)  # Emits ThemeDefinition

    _instance: Optional["ThemeManager"] = None

    @classmethod
    def get_instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._themes: Dict[str, ThemeDefinition] = {}
        self._active_theme_id: str = "default"
        self._custom_fonts_loaded: bool = False
        self._quantum_family: str = "monospace"
        
        self._load_custom_fonts()
        self._register_bundled_themes()

    def _load_custom_fonts(self):
        """Loads and registers packaged TrueType fonts via QFontDatabase."""
        quantum_path = resolve_package_asset(Path("assets/themes/cyber_yellow/fonts/quantum.ttf"))
        if quantum_path and quantum_path.is_file():
            font_id = QFontDatabase.addApplicationFont(str(quantum_path))
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    self._quantum_family = families[0]
                    self._custom_fonts_loaded = True
                    logger.info(f"Loaded bundled font '{self._quantum_family}' (ID: {font_id})")
                else:
                    logger.warning("Quantum font registered with font_id but no families returned")
            else:
                logger.warning(f"Failed to register Quantum font from {quantum_path}")
        else:
            logger.info("Quantum font asset not found; falling back to monospace")

    def _read_theme_qss(self, qss_path: Optional[Path]) -> str:
        """Reads optional theme.qss file safely without throwing on missing or unreadable files."""
        if not qss_path or not qss_path.is_file():
            return ""
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                content = f.read()
                logger.info(f"Loaded theme QSS override from {qss_path} ({len(content)} chars)")
                return content
        except Exception as e:
            logger.warning(f"Failed to read theme QSS override from {qss_path}: {e}")
            return ""

    def _register_bundled_themes(self):
        """Builds and registers DEFAULT and CYBER YELLOW ThemeDefinitions."""
        # 1. DEFAULT THEME
        def_qss_path = resolve_package_asset(Path("assets/themes/default/theme.qss"))
        default_def = ThemeDefinition(
            id="default",
            display_name="DEFAULT",
            palette=ThemePalette(),
            assets=ThemeAssets(qss_path=def_qss_path),
            typography=ThemeTypography(
                display_family="monospace",
                monospace_family="monospace",
                has_custom_display_font=False
            ),
            is_image_backed=False,
            qss_override=self._read_theme_qss(def_qss_path)
        )
        self._themes["default"] = default_def

        # 2. CYBER YELLOW THEME
        cy_qss_path = resolve_package_asset(Path("assets/themes/cyber_yellow/theme.qss"))
        cy_assets = ThemeAssets(
            chassis_image_path=resolve_package_asset(Path("assets/themes/cyber_yellow/images/chassis.png")),
            panel_image_path=resolve_package_asset(Path("assets/themes/cyber_yellow/images/panel_brushed_metal.png")),
            hazard_strip_path=resolve_package_asset(Path("assets/themes/cyber_yellow/images/hazard_strip.png")),
            logo_image_path=resolve_package_asset(Path("assets/themes/cyber_yellow/images/logo.png")),
            wordmark_image_path=resolve_package_asset(Path("assets/themes/cyber_yellow/images/wordmark.png")),
            qss_path=cy_qss_path
        )

        cy_palette = ThemePalette(
            bg_chassis=QColor(22, 23, 26, 250),
            bg_module=QColor(20, 21, 25, 250),
            bg_lcd="#0c0d12",
            bg_surface="#181a20",
            bg_surface_alt="#202228",
            bg_control="#1a1c22",
            bg_control_hover="#282a32",
            bg_control_pressed="#ffd700",
            
            border_chassis_default=QColor(255, 215, 0, 230),
            border_module_default=QColor(255, 215, 0, 180),
            border_panel="#3a382c",
            border_control="#484435",
            border_control_hover="#ffd700",
            
            primary="#ffd700",
            accent="#ff2a4b",
            warning="#ffaa00",
            danger="#ff1a35",
            
            text_primary="#ffffff",
            text_secondary="#f3f4f6",
            text_muted="#d1d5db",
            text_dim="#9ca3af",
            text_lcd="#ffd700",
            text_lcd_time="#ffffff",
            
            # Contrast-Tuned Surface Tokens for Yellow Chassis
            text_on_chassis="#18181b",
            text_on_chassis_muted="#3f3f46",
            bg_control_on_chassis="#181a20",
            border_control_on_chassis="#3f3f46",
            text_control_on_chassis="#18181b",
            
            chip_vis_bg="#1c1b12",
            chip_vis_border="#4a4218",
            chip_vis_text="#ffd700",
            chip_vis_active_bg="#ffd700",
            chip_vis_active_text="#000000",
            
            chip_pl_bg="#201416",
            chip_pl_border="#4a2228",
            chip_pl_text="#ff2a4b",
            chip_pl_active_bg="#ff2a4b",
            chip_pl_active_text="#ffffff",
            
            slider_groove="#252730",
            slider_subpage="#ffd700",
            slider_handle="#ffffff",
            slider_handle_border="#ffd700",
            
            list_bg="#0e0f14",
            list_border="#3a382c",
            list_item_text="#f3f4f6",
            list_item_border="#1c1e26",
            list_selected_bg="#2c2818",
            list_selected_text="#ffd700",
            list_hover_bg="#1e1f26",
            list_hover_text="#fff275"
        )

        cyber_yellow_def = ThemeDefinition(
            id="cyber_yellow",
            display_name="CYBER YELLOW",
            palette=cy_palette,
            assets=cy_assets,
            typography=ThemeTypography(
                display_family=self._quantum_family,
                monospace_family="monospace",
                has_custom_display_font=self._custom_fonts_loaded
            ),
            is_image_backed=True,
            qss_override=self._read_theme_qss(cy_qss_path)
        )
        self._themes["cyber_yellow"] = cyber_yellow_def

    def get_theme(self, theme_id: str) -> Optional[ThemeDefinition]:
        """Retrieves a theme definition by id."""
        return self._themes.get(theme_id)

    def get_available_themes(self) -> list[str]:
        """Returns list of registered theme ids."""
        return list(self._themes.keys())

    @property
    def current_theme(self) -> ThemeDefinition:
        return self._themes.get(self._active_theme_id, self._themes["default"])

    @property
    def active_theme_id(self) -> str:
        return self._active_theme_id

    def set_theme(self, theme_id: str):
        """Activates a theme by internal ID and notifies all listening UI surfaces."""
        if theme_id not in self._themes:
            logger.warning(f"Unknown theme ID '{theme_id}'; falling back to 'default'")
            theme_id = "default"
        
        if self._active_theme_id != theme_id or theme_id == "default":
            self._active_theme_id = theme_id
            theme = self.current_theme
            # Refresh QSS override in case the file was modified
            if theme.assets.qss_path:
                theme.qss_override = self._read_theme_qss(theme.assets.qss_path)
            logger.info(f"Active theme switched to: {theme.display_name} ({theme.id})")
            self.theme_changed.emit(theme)

    def toggle_theme(self) -> str:
        """Toggles between DEFAULT and CYBER YELLOW."""
        next_id = "cyber_yellow" if self._active_theme_id == "default" else "default"
        self.set_theme(next_id)
        return next_id
