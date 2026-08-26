"""
ToroidAMP - Production Modular Window Manager
Coordinates lifecycle, docking choreography, magnetic snapping,
playback orchestration, session persistence, system tray, and clean shutdown.
"""

import logging
import os
from typing import Optional
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication

from .chassis import UnifiedChassis
from .fullscreen import RetinaMeltWindow
from .modules.base import ModuleShell
from .modules.visualizer_module import VisualizerModule
from .modules.playlist_module import PlaylistModule
from .tray import ToroidTrayIcon

from ..audio.player import PlayerEngine, PlaybackState
from ..audio.playlist import PlaylistManager
from ..analysis.audio_frame import AnalysisHandoff, AudioFrame
from ..session import SessionManager, SessionState, WindowPosition, ModulePosition

logger = logging.getLogger("toroidamp.ui")


class WindowManager(QWidget):
    """
    Central Application Controller coordinating modular UI,
    real-time audio playback, system tray, and session persistence.
    """
    SNAP_THRESHOLD = 30 # px for modular docking

    def __init__(
        self,
        player: PlayerEngine,
        handoff: AnalysisHandoff,
        playlist: PlaylistManager,
        session_manager: Optional[SessionManager] = None
    ):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, 1, 1)

        self.player_engine = player
        self.handoff = handoff
        self.playlist = playlist
        self.session_manager = session_manager or SessionManager()

        # Load session state
        self.session_state = self.session_manager.load()

        # 1. Main Unified Chassis (MINI / NORMAL)
        self.chassis = UnifiedChassis()

        # 2. Dockable Modules
        self.vis_mod = VisualizerModule()
        self.pl_mod = PlaylistModule(self.playlist)

        # 3. Retina Melt Fullscreen Window
        self.retina_melt = RetinaMeltWindow()

        # 4. System Tray Icon
        self.tray_icon = ToroidTrayIcon(self)
        self.tray_icon.show()

        # Experience scale memory
        self.prior_scale = self.session_state.scale
        self.saved_vis_visible = self.session_state.vis_module.is_visible
        self.saved_pl_visible = self.session_state.pl_module.is_visible
        self.is_hidden_to_tray = False

        # Apply Restored Session State
        self._apply_restored_session()

        # Wire Signals
        self._wire_signals()

        # Render Loop Timer (~60 FPS)
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._tick)
        self.render_timer.start(16)

        # Magnetic Snap Monitor Timer (~30 FPS)
        self.snap_timer = QTimer(self)
        self.snap_timer.timeout.connect(self._check_magnetic_snapping)
        self.snap_timer.start(33)

        logger.info("WindowManager initialized successfully with session persistence & tray")

    def _apply_restored_session(self):
        """Restores window positions, modules, volume, playlist, and visualizer state from session."""
        st = self.session_state

        # 1. Restore Volume
        self.player_engine.volume = st.volume
        self.chassis.set_volume(st.volume)

        # 2. Restore Shuffle / Repeat
        self.playlist.shuffle = st.shuffle
        self.playlist.repeat = st.repeat
        self.pl_mod.btn_shf.setChecked(st.shuffle)
        self.pl_mod.btn_rep.setChecked(st.repeat)

        # 3. Restore Visualizer Selection
        if 0 <= st.selected_visualizer_idx < len(self.vis_mod.visualizers):
            self.vis_mod.vis_idx = st.selected_visualizer_idx
            name = self.vis_mod.current_visualizer.get_name().upper()
            self.vis_mod.btn_switch.setText(f"MODE: {name}")

        # 4. Restore Playlist Items (if not overridden by CLI args)
        if len(self.playlist) == 0 and st.playlist_files:
            for item_d in st.playlist_files:
                fp = item_d.get("filepath", "")
                if os.path.isfile(fp):
                    self.playlist.add_file(fp, item_d.get("title"), float(item_d.get("duration", 0.0)))
            self.playlist.sanitize()
            self.playlist.current_index = -1  # Authoritative rule: STARTUP = NO TRACK LOADED
            self.pl_mod.refresh()


        # 5. Restore Window Geometries with Screen Clamping
        screen = QGuiApplication.primaryScreen()
        screen_rect = screen.availableGeometry() if screen else None

        cx, cy = st.chassis_pos.x, st.chassis_pos.y
        if screen_rect:
            cx, cy = SessionManager.clamp_to_screen(cx, cy, st.chassis_pos.w, st.chassis_pos.h, screen_rect)
        self.chassis.move(cx, cy)

        # Visualizer Geometry
        vx, vy = st.vis_module.x, st.vis_module.y
        if screen_rect:
            vx, vy = SessionManager.clamp_to_screen(vx, vy, 420, 240, screen_rect)
        self.vis_mod.move(vx, vy)
        self.vis_mod.is_docked = st.vis_module.is_docked
        self.vis_mod.dock_edge = st.vis_module.dock_edge
        self.vis_mod.btn_dock.setText("⇱" if self.vis_mod.is_docked else "⇲")

        # Playlist Geometry
        px, py = st.pl_module.x, st.pl_module.y
        if screen_rect:
            px, py = SessionManager.clamp_to_screen(px, py, 270, 240, screen_rect)
        self.pl_mod.move(px, py)
        self.pl_mod.is_docked = st.pl_module.is_docked
        self.pl_mod.dock_edge = st.pl_module.dock_edge
        self.pl_mod.btn_dock.setText("⇱" if self.pl_mod.is_docked else "⇲")

        # 6. Restore Scale Mode & Module Visibility
        self.chassis.set_mode(st.scale, animated=False)
        self.chassis.show()

        if st.scale == "normal":
            if st.vis_module.is_visible:
                self.vis_mod.show()
                self.chassis.chip_vis.setChecked(True)
            if st.pl_module.is_visible:
                self.pl_mod.show()
                self.chassis.chip_pl.setChecked(True)
            self.realign_docked_modules()

    def _wire_signals(self):
        # Chassis Controls
        self.chassis.scale_changed.connect(self._on_scale_changed)
        self.chassis.retina_melt_requested.connect(self._enter_retina_melt)
        self.chassis.minimize_requested.connect(self.hide_to_tray)
        self.chassis.close_requested.connect(self.shutdown)
        self.chassis.play_toggled.connect(self._toggle_play)
        self.chassis.prev_clicked.connect(self._play_previous)
        self.chassis.next_clicked.connect(self._play_next)
        self.chassis.stop_clicked.connect(self._stop_playback)
        self.chassis.seek_changed.connect(self._on_seek)
        self.chassis.volume_changed.connect(self._on_volume_changed)
        self.chassis.toggle_vis_clicked.connect(self._toggle_vis)
        self.chassis.toggle_pl_clicked.connect(self._toggle_pl)
        self.chassis.files_dropped.connect(self._on_files_dropped)


        # Module Docking & Playlist
        self.vis_mod.dock_requested.connect(lambda m, edge: self.dock_module(m, "bottom"))
        self.vis_mod.undock_requested.connect(self.undock_module)
        self.vis_mod.closed_signal.connect(lambda m: self.chassis.chip_vis.setChecked(False))
        self.vis_mod.retina_melt_requested.connect(self._enter_retina_melt)

        self.pl_mod.dock_requested.connect(lambda m, edge: self.dock_module(m, "right"))
        self.pl_mod.undock_requested.connect(self.undock_module)
        self.pl_mod.closed_signal.connect(lambda m: self.chassis.chip_pl.setChecked(False))
        self.pl_mod.track_double_clicked.connect(self._play_index)
        self.pl_mod.files_dropped.connect(self._on_files_dropped)
        self.pl_mod.shuffle_toggled.connect(self._on_shuffle_toggled)
        self.pl_mod.repeat_toggled.connect(self._on_repeat_toggled)

        # Fullscreen RETINA MELT Controls
        self.retina_melt.exit_requested.connect(self._exit_retina_melt)
        self.retina_melt.play_toggled.connect(self._toggle_play)
        self.retina_melt.prev_clicked.connect(self._play_previous)
        self.retina_melt.next_clicked.connect(self._play_next)

        # System Tray Controls
        self.tray_icon.restore_requested.connect(self.restore_from_tray)
        self.tray_icon.play_toggled.connect(self._toggle_play)
        self.tray_icon.prev_requested.connect(self._play_previous)
        self.tray_icon.next_requested.connect(self._play_next)
        self.tray_icon.exit_requested.connect(self.shutdown)

    def handle_close_action(self):
        """
        Handles clicking the close button ('✕').
        If close_to_tray is enabled (default), hides to tray while playback continues.
        """
        if self.session_state.close_to_tray:
            self.hide_to_tray()
        else:
            self.shutdown()

    def hide_to_tray(self):
        """Hides the UI to system tray while keeping audio playback completely intact."""
        logger.info("Hiding ToroidAMP to System Tray")
        self.is_hidden_to_tray = True

        if self.retina_melt.isVisible():
            self.retina_melt.hide()

        if self.chassis.mode == "normal":
            self.saved_vis_visible = self.vis_mod.isVisible()
            self.saved_pl_visible = self.pl_mod.isVisible()

        self.chassis.hide()
        self.vis_mod.hide()
        self.pl_mod.hide()
        self.save_current_session()

    def restore_from_tray(self):
        """Restores the player to the last desktop experience scale."""
        logger.info("Restoring ToroidAMP from System Tray")
        self.is_hidden_to_tray = False

        if self.retina_melt.isVisible():
            self.retina_melt.hide()

        self.chassis.set_mode(self.prior_scale, animated=False)
        self.chassis.show()

        if self.prior_scale == "normal":
            if self.saved_vis_visible:
                if self.vis_mod.is_docked:
                    self.dock_module(self.vis_mod, "bottom")
                self.vis_mod.show()
                self.chassis.chip_vis.setChecked(True)
            if self.saved_pl_visible:
                if self.pl_mod.is_docked:
                    self.dock_module(self.pl_mod, "right")
                self.pl_mod.show()
                self.chassis.chip_pl.setChecked(True)
            self.realign_docked_modules()


    def save_current_session(self):
        """Gathers current runtime state and writes atomically to session JSON."""
        st = self.session_state
        st.scale = self.chassis.mode
        st.volume = self.player_engine.volume
        st.shuffle = self.playlist.shuffle
        st.repeat = self.playlist.repeat
        st.selected_visualizer_idx = self.vis_mod.vis_idx

        # Chassis position
        cp = self.chassis.pos()
        st.chassis_pos = WindowPosition(x=cp.x(), y=cp.y(), w=self.chassis.width(), h=self.chassis.height())

        # Visualizer position & state
        vp = self.vis_mod.pos()
        st.vis_module = ModulePosition(
            x=vp.x(),
            y=vp.y(),
            is_docked=self.vis_mod.is_docked,
            dock_edge=self.vis_mod.dock_edge or "bottom",
            is_visible=self.vis_mod.isVisible() if self.chassis.mode == "normal" else self.saved_vis_visible
        )

        # Playlist position & state
        pp = self.pl_mod.pos()
        st.pl_module = ModulePosition(
            x=pp.x(),
            y=pp.y(),
            is_docked=self.pl_mod.is_docked,
            dock_edge=self.pl_mod.dock_edge or "right",
            is_visible=self.pl_mod.isVisible() if self.chassis.mode == "normal" else self.saved_pl_visible
        )

        # Playlist tracks
        st.playlist_files = [
            {"filepath": item.filepath, "title": item.title, "duration": item.duration}
            for item in self.playlist.items
        ]
        st.current_track_index = self.playlist.current_index
        st.last_position_seconds = self.player_engine.position

        self.session_manager.save()

    def shutdown(self):
        """
        One unified clean application shutdown path:
        saves session, stops timers, releases audio & native resources, terminates Qt.
        """
        logger.info("Executing ToroidAMP shutdown sequence")
        self.save_current_session()

        # Stop timers
        self.render_timer.stop()
        self.snap_timer.stop()

        # Stop playback and release audio hardware
        self.player_engine.stop()
        self.player_engine.close()

        # Close all windows and tray
        self.retina_melt.close()
        self.vis_mod.close()
        self.pl_mod.close()
        self.chassis.close()
        self.tray_icon.hide()

        logger.info("Shutdown sequence complete. Exiting process.")
        QApplication.quit()

    def load_and_play(self, filepath: str):
        """Loads and starts playing a track."""
        try:
            self.player_engine.load(filepath)
            self.player_engine.play()
            logger.info(f"Playing: {filepath}")
        except Exception as e:
            logger.error(f"Failed to load track '{filepath}': {e}")

    def _play_index(self, index: int):
        self.playlist.current_index = index
        item = self.playlist.current_item
        if item:
            self.load_and_play(item.filepath)
            self.pl_mod.refresh()

    def _toggle_play(self):
        if self.player_engine.state == PlaybackState.PLAYING:
            self.player_engine.pause()
        elif self.player_engine.state == PlaybackState.PAUSED:
            self.player_engine.play()
        elif self.player_engine.state == PlaybackState.STOPPED:
            item = self.playlist.current_item
            if item:
                self.load_and_play(item.filepath)
            elif len(self.playlist) > 0:
                self._play_index(0)

    def _stop_playback(self):
        self.player_engine.stop()

    def _play_next(self):
        next_idx = self.playlist.get_next_index()
        if next_idx is not None:
            self._play_index(next_idx)

    def _play_previous(self):
        prev_idx = self.playlist.get_previous_index()
        if prev_idx is not None:
            self._play_index(prev_idx)

    def _on_seek(self, slider_val: int):
        duration = self.player_engine.duration
        if duration > 0.0:
            target_sec = (slider_val / 1000.0) * duration
            self.player_engine.seek(target_sec)

    def _on_volume_changed(self, vol: float):
        self.player_engine.volume = vol

    def _on_shuffle_toggled(self, enabled: bool):
        self.playlist.shuffle = enabled

    def _on_repeat_toggled(self, enabled: bool):
        self.playlist.repeat = enabled

    def _on_files_dropped(self, filepaths: list[str]):
        if len(self.playlist) == len(filepaths) and self.player_engine.state == PlaybackState.STOPPED:
            self._play_index(0)

    def _on_scale_changed(self, new_scale: str):
        if new_scale == "mini":
            if self.prior_scale == "normal":
                self.saved_vis_visible = self.vis_mod.isVisible()
                self.saved_pl_visible = self.pl_mod.isVisible()
            self.vis_mod.hide()
            self.pl_mod.hide()
            self.prior_scale = "mini"
        elif new_scale == "normal":
            if self.saved_vis_visible:
                if self.vis_mod.is_docked:
                    self.dock_module(self.vis_mod, "bottom")
                self.vis_mod.show()
                self.chassis.chip_vis.setChecked(True)
            if self.saved_pl_visible:
                if self.pl_mod.is_docked:
                    self.dock_module(self.pl_mod, "right")
                self.pl_mod.show()
                self.chassis.chip_pl.setChecked(True)
            self.prior_scale = "normal"
            self.realign_docked_modules()


    def _enter_retina_melt(self):
        self.prior_scale = self.chassis.mode
        if self.prior_scale == "normal":
            self.saved_vis_visible = self.vis_mod.isVisible()
            self.saved_pl_visible = self.pl_mod.isVisible()
        self.chassis.hide()
        self.vis_mod.hide()
        self.pl_mod.hide()
        self.retina_melt.set_visualizer_index(self.vis_mod.vis_idx)
        self.retina_melt.show_fullscreen_experience()

    def _exit_retina_melt(self):
        self.retina_melt.hide()
        self.chassis.set_mode(self.prior_scale, animated=False)
        self.chassis.show()

    def _toggle_vis(self):
        if self.vis_mod.isVisible():
            self.vis_mod.hide()
            self.chassis.chip_vis.setChecked(False)
        else:
            self.dock_module(self.vis_mod, "bottom")
            self.vis_mod.show()
            self.chassis.chip_vis.setChecked(True)

    def _toggle_pl(self):
        if self.pl_mod.isVisible():
            self.pl_mod.hide()
            self.chassis.chip_pl.setChecked(False)
        else:
            self.dock_module(self.pl_mod, "right")
            self.pl_mod.show()
            self.chassis.chip_pl.setChecked(True)

    def dock_module(self, module: ModuleShell, edge: str):
        module.is_docked = True
        module.dock_edge = edge
        module.btn_dock.setText("⇱")
        self.realign_docked_modules()

    def undock_module(self, module: ModuleShell):
        module.is_docked = False
        module.dock_edge = None
        module.btn_dock.setText("⇲")

    def realign_docked_modules(self):
        if self.chassis.mode != "normal" or not self.chassis.isVisible():
            return
        core_geom = self.chassis.geometry()

        if self.vis_mod.is_docked and self.vis_mod.isVisible():
            self.vis_mod.move(core_geom.left(), core_geom.bottom() + 2)

        if self.pl_mod.is_docked and self.pl_mod.isVisible():
            self.pl_mod.move(core_geom.right() + 2, core_geom.top())
            if self.vis_mod.is_docked and self.vis_mod.isVisible():
                self.pl_mod.setFixedHeight(core_geom.height() + self.vis_mod.height() + 2)
            else:
                self.pl_mod.setFixedHeight(core_geom.height())

    def _check_magnetic_snapping(self):
        if self.chassis.mode != "normal" or not self.chassis.isVisible():
            return
        core_geom = self.chassis.geometry()
        self.realign_docked_modules()

        # Check Visualizer Bottom Proximity
        if not self.vis_mod.is_docked and self.vis_mod.isVisible():
            vis_geom = self.vis_mod.geometry()
            dx = abs(vis_geom.left() - core_geom.left())
            dy = abs(vis_geom.top() - (core_geom.bottom() + 2))
            if dx < self.SNAP_THRESHOLD and dy < self.SNAP_THRESHOLD:
                self.dock_module(self.vis_mod, "bottom")

        # Check Playlist Right Proximity
        if not self.pl_mod.is_docked and self.pl_mod.isVisible():
            pl_geom = self.pl_mod.geometry()
            dx = abs(pl_geom.left() - (core_geom.right() + 2))
            dy = abs(pl_geom.top() - core_geom.top())
            if dx < self.SNAP_THRESHOLD and dy < self.SNAP_THRESHOLD:
                self.dock_module(self.pl_mod, "right")

    def _tick(self):
        # 1. Automatic Track Advancement on EOF
        if self.player_engine.state == PlaybackState.STOPPED and len(self.playlist) > 0 and self.player_engine.position > 0.0:
            next_idx = self.playlist.get_next_index()
            if next_idx is not None and next_idx != self.playlist.current_index:
                self._play_index(next_idx)

        # 2. Update Telemetry
        item = self.playlist.current_item
        title_str = f"♫ {item.title}" if item else "♫ No Track Loaded"
        
        pos = self.player_engine.position
        dur = self.player_engine.duration
        progress = (pos / dur) if dur > 0.0 else 0.0

        p_min, p_sec = int(pos // 60), int(pos % 60)
        d_min, d_sec = int(dur // 60), int(dur % 60)
        time_str = f"{p_min:02d}:{p_sec:02d} / {d_min:02d}:{d_sec:02d}"

        is_playing = self.player_engine.state == PlaybackState.PLAYING
        self.chassis.update_telemetry(title_str, time_str, progress, is_playing)
        self.retina_melt.update_telemetry(title_str, time_str, is_playing)
        self.tray_icon.update_status(title_str, is_playing)

        # 3. Only compute DSP & render visualizer if a visualizer is actually visible!
        # (Zero CPU/GPU visualizer waste when hidden to tray or in MINI mode)
        if self.vis_mod.isVisible() or self.retina_melt.isVisible():
            frame = self.handoff.get_audio_frame(44100)
            if self.vis_mod.isVisible():
                self.vis_mod.render_frame(frame, 0.016)
            if self.retina_melt.isVisible():
                self.retina_melt.render_frame(frame, 0.016)
