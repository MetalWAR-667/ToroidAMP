"""
ToroidAMP - Session & Configuration Persistence Subsystem
Atomic JSON session management, window geometry sanity clamping,
and cross-platform standard directory handling.
"""

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .paths import get_app_data_dir

logger = logging.getLogger("toroidamp.session")


@dataclass
class WindowPosition:
    x: int = 250
    y: int = 180
    w: int = 420
    h: int = 135


@dataclass
class ModulePosition:
    x: int = 250
    y: int = 320
    # 0 means "unset" — the restoring code falls back to the module's own
    # DEFAULT_SIZE. Session state stores raw geometry only; it does not know
    # about module-specific minimums or defaults (those are a UI concern).
    width: int = 0
    height: int = 0
    is_docked: bool = True
    dock_edge: str = "bottom"
    is_visible: bool = False


@dataclass
class SessionState:
    """
    Serializable session state contract.
    Contains user preferences, layout topology, and queue state.
    """
    version: int = 1
    # Scale & Preferences
    scale: str = "normal"  # 'mini' or 'normal'
    volume: float = 0.8
    fade_enabled: bool = True
    shuffle: bool = False
    repeat: bool = False
    selected_visualizer_idx: int = 0
    close_to_tray: bool = True
    theme_id: str = "default"
    # Visualizer Settings
    visualizer_parameters: dict[str, dict[str, float]] = field(default_factory=dict) # {vis_id: {param_name: val}}

    # Window Geometries
    chassis_pos: WindowPosition = field(default_factory=WindowPosition)
    vis_module: ModulePosition = field(default_factory=lambda: ModulePosition(x=250, y=320, is_docked=True, dock_edge="bottom", is_visible=False))
    pl_module: ModulePosition = field(default_factory=lambda: ModulePosition(x=675, y=180, is_docked=True, dock_edge="right", is_visible=False))

    # Playlist & Track State
    playlist_files: list[dict[str, Any]] = field(default_factory=list) # [{filepath, title, duration}]
    current_track_index: int = -1
    last_position_seconds: float = 0.0


class SessionManager:
    """
    Manages loading, validating, clamping, and atomic saving of SessionState.
    """

    def __init__(self, custom_path: Optional[str] = None):
        self._session_path = Path(custom_path) if custom_path else self._get_default_session_path()
        self.state: SessionState = SessionState()

    @staticmethod
    def _get_default_session_path() -> Path:
        """
        Resolves canonical cross-platform standard config directory:
        - Windows: %LOCALAPPDATA%/ToroidAMP/session.json
        - Linux: ~/.config/ToroidAMP/session.json
        Migrates legacy nested paths gracefully if present.

        RC-069-002: the shared root-directory resolution (QStandardPaths +
        the anti-double-nesting guard) now lives in `paths.get_app_data_dir()`
        — the same root logs/ and shaders/ also resolve under (paths.py) —
        so this method only adds its own session.json-specific concerns
        (the exact filename, legacy-path migration) on top.
        """
        target_dir = get_app_data_dir()
        canonical_file = target_dir / "session.json"

        # Check for legacy nested session file from earlier builds and migrate
        legacy_nested = target_dir / "ToroidAMP" / "session.json"
        if not canonical_file.exists() and legacy_nested.exists():
            try:
                import shutil
                shutil.copy2(legacy_nested, canonical_file)
                logger.info(f"Migrated legacy session from {legacy_nested} to {canonical_file}")
            except Exception as e:
                logger.warning(f"Could not migrate legacy session: {e}")

        return canonical_file

    @property
    def session_path(self) -> Path:
        return self._session_path

    @staticmethod
    def _safe_positive_int(value: Any) -> int:
        """Parses a saved dimension; invalid or non-positive values collapse to 0 ('unset')."""
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 0
        return parsed if parsed > 0 else 0


    def load(self) -> SessionState:
        """Loads and validates session JSON. Falls back cleanly on error."""
        if not self._session_path.exists():
            logger.info(f"No existing session file at {self._session_path}. Using default state.")
            self.state = SessionState()
            return self.state

        try:
            with open(self._session_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Reconstruct Dataclass with validation and field fallbacks
            chassis_d = data.get("chassis_pos", {})
            vis_d = data.get("vis_module", {})
            pl_d = data.get("pl_module", {})

            self.state = SessionState(
                version=data.get("version", 1),
                scale=data.get("scale", "normal"),
                volume=max(0.0, min(1.0, float(data.get("volume", 0.8)))),
                fade_enabled=bool(data.get("fade_enabled", True)),
                shuffle=bool(data.get("shuffle", False)),
                repeat=bool(data.get("repeat", False)),
                selected_visualizer_idx=int(data.get("selected_visualizer_idx", 0)),
                close_to_tray=bool(data.get("close_to_tray", True)),
                theme_id=str(data.get("theme_id", "default")) if str(data.get("theme_id", "default")) in ("default", "cyber_yellow") else "default",
                chassis_pos=WindowPosition(
                    x=int(chassis_d.get("x", 250)),
                    y=int(chassis_d.get("y", 180)),
                    w=int(chassis_d.get("w", 420)),
                    h=int(chassis_d.get("h", 135))
                ),
                vis_module=ModulePosition(
                    x=int(vis_d.get("x", 250)),
                    y=int(vis_d.get("y", 320)),
                    width=self._safe_positive_int(vis_d.get("width", 0)),
                    height=self._safe_positive_int(vis_d.get("height", 0)),
                    is_docked=bool(vis_d.get("is_docked", True)),
                    dock_edge=str(vis_d.get("dock_edge", "bottom")),
                    is_visible=bool(vis_d.get("is_visible", False))
                ),
                pl_module=ModulePosition(
                    x=int(pl_d.get("x", 675)),
                    y=int(pl_d.get("y", 180)),
                    width=self._safe_positive_int(pl_d.get("width", 0)),
                    height=self._safe_positive_int(pl_d.get("height", 0)),
                    is_docked=bool(pl_d.get("is_docked", True)),
                    dock_edge=str(pl_d.get("dock_edge", "right")),
                    is_visible=bool(pl_d.get("is_visible", False))
                ),
                playlist_files=data.get("playlist_files", []),
                current_track_index=int(data.get("current_track_index", -1)),
                last_position_seconds=float(data.get("last_position_seconds", 0.0)),
                visualizer_parameters=data.get("visualizer_parameters", {})
            )
            logger.info(f"Session loaded successfully from {self._session_path}")
        except Exception as e:
            logger.warning(f"Failed to parse session JSON from {self._session_path}: {e}. Falling back to default.")
            self.state = SessionState()

        return self.state

    def save(self) -> None:
        """Atomically saves the current SessionState to JSON."""
        try:
            self._session_path.parent.mkdir(parents=True, exist_ok=True)
            state_dict = asdict(self.state)

            # Atomic write: write to temp file in same directory, then rename
            with tempfile.NamedTemporaryFile("w", dir=self._session_path.parent, delete=False, encoding="utf-8") as tmp:
                json.dump(state_dict, tmp, indent=2, ensure_ascii=False)
                tmp_path = tmp.name

            # Windows atomic replace
            os.replace(tmp_path, self._session_path)
            logger.info(f"Session atomically saved to {self._session_path}")
        except Exception as e:
            logger.error(f"Failed to save session state: {e}")

    @staticmethod
    def clamp_to_screen(x: int, y: int, w: int, h: int, screen_rect: Any) -> tuple[int, int]:
        """
        Clamps window position so it never restores off-screen
        when monitors or resolutions change.
        """
        min_visible = 40  # Keep at least 40px on screen
        s_left = screen_rect.left()
        s_top = screen_rect.top()
        s_right = screen_rect.right()
        s_bottom = screen_rect.bottom()

        clamped_x = max(s_left - w + min_visible, min(s_right - min_visible, x))
        clamped_y = max(s_top, min(s_bottom - min_visible, y))

        return clamped_x, clamped_y
