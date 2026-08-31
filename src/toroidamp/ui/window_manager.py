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
from .neon import ReactiveNeonController
from .theme import ThemeManager, ThemeDefinition

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

        # Initialize ThemeManager with restored theme before constructing UI
        self.theme_manager = ThemeManager.get_instance()
        restored_theme = getattr(self.session_state, "theme_id", "default")
        self.theme_manager.set_theme(restored_theme)

        self.neon_controller = ReactiveNeonController(theme_id=self.theme_manager.active_theme_id)

        # 1. Main Unified Chassis (MINI / NORMAL)
        self.chassis = UnifiedChassis()

        # RELEASE-BLOCKERS-001: Wayland's xdg-shell protocol gives a client
        # no way to set an independent top-level window's absolute
        # position -- compositors (GNOME/Mutter) simply center every
        # xdg_toplevel, which is what made Playlist/Visualizer appear
        # centered/overlapping instead of docked (UBUNTU-WAYLAND-002).
        # Rather than keep fighting that protocol limitation, Playlist and
        # Visualizer are hosted as plain CHILD widgets inside the chassis's
        # own single top-level surface on Wayland specifically (see
        # ModuleShell's `embedded` parameter and UnifiedChassis.
        # embed_module()) -- a child widget's position is Qt's own layout
        # concern, not the compositor's, so it works portably everywhere.
        # Windows/X11 are completely unaffected: this stays False there,
        # and every module-hosting code path below is a no-op unless it is
        # True.
        self._wayland_embedded = QGuiApplication.platformName() == "wayland"

        # 2. Dockable Modules — chassis is passed as Qt parent so that Windows
        #    treats VisualizerModule and PlaylistModule as "owned" windows of
        #    the chassis.  Owned windows do not receive their own taskbar entry
        #    on Windows; only the chassis (the owner) appears.  The Qt.Window
        #    flag in ModuleShell keeps them as independently positionable
        #    top-level windows — spatial independence is preserved; taskbar
        #    identity is not. On Linux/X11, the same Qt parent relationship
        #    makes Qt set the WM_TRANSIENT_FOR hint, which window managers
        #    that support it (v0.666: verified informally under Cinnamon)
        #    use for the equivalent single-application taskbar grouping.
        #    On Wayland, `embedded=True` builds these as plain child widgets
        #    instead (see note above).
        self.vis_mod = VisualizerModule(parent=self.chassis, embedded=self._wayland_embedded)
        self.pl_mod = PlaylistModule(self.playlist, parent=self.chassis, embedded=self._wayland_embedded)

        # 3. Retina Melt Fullscreen Window — same owned-window relationship
        # as the modules above (v0.666: previously created with no parent,
        # so it got no taskbar-grouping hint on either platform).
        self.retina_melt = RetinaMeltWindow(session_manager=self.session_manager, parent=self.chassis)

        # 4. System Tray Icon
        self.tray_icon = ToroidTrayIcon(self)
        self.tray_icon.show()

        # Experience scale memory
        self.prior_scale = self.session_state.scale
        self.saved_vis_visible = self.session_state.vis_module.is_visible
        self.saved_pl_visible = self.session_state.pl_module.is_visible
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

        # 1. Restore Volume & Playback Settings
        self.player_engine.volume = st.volume
        self.player_engine.fade_enabled = getattr(st, "fade_enabled", True)
        self.chassis.set_volume(st.volume)
        self.chassis.chip_fade.setChecked(self.player_engine.fade_enabled)

        # 2. Restore Shuffle / Repeat
        self.playlist.shuffle = st.shuffle
        self.playlist.repeat = st.repeat
        self.pl_mod.btn_shf.setChecked(st.shuffle)
        self.pl_mod.btn_rep.setChecked(st.repeat)

        # 3. Restore Visualizer Selection
        if 0 <= st.selected_visualizer_idx < len(self.vis_mod.visualizers):
            self.vis_mod.vis_idx = st.selected_visualizer_idx

        # 4. Restore Playlist Items (if not overridden by CLI args)
        if len(self.playlist) == 0 and st.playlist_files:
            for item_d in st.playlist_files:
                fp = item_d.get("filepath", "")
                if os.path.isfile(fp):
                    self.playlist.add_file(fp, item_d.get("title"), float(item_d.get("duration", 0.0)))
            self.playlist.sanitize()
            self.playlist.current_index = -1  # Authoritative rule: STARTUP = NO TRACK LOADED
            self.pl_mod.refresh()


        screen = QGuiApplication.primaryScreen()
        screen_rect = screen.availableGeometry() if screen else None

        # 5. Restore Scale Mode first — establishes authoritative chassis dimensions
        #    (MINI_WIDTH × MINI_HEIGHT or NORMAL_WIDTH × NORMAL_HEIGHT) so that
        #    screen clamping below uses the real window size, not a stale session
        #    value.  Old sessions that stored a narrower MINI width are silently
        #    upgraded: the position is preserved, but the new authoritative size wins.
        self.chassis.set_mode(st.scale, animated=False)
        self.chassis.show()

        # 6. Restore Window Geometries with Screen Clamping (using live chassis size)
        cx, cy = st.chassis_pos.x, st.chassis_pos.y
        if screen_rect:
            cx, cy = SessionManager.clamp_to_screen(
                cx, cy, self.chassis.width(), self.chassis.height(), screen_rect
            )
        self.chassis.move(cx, cy)

        # Visualizer Geometry & Size — USER SIZE IS STATE: a missing/invalid
        # saved size falls back to the module's stable DEFAULT_SIZE, never to
        # whatever the runtime geometry happens to be.
        vis_w = st.vis_module.width or self.vis_mod.DEFAULT_SIZE.width()
        vis_h = st.vis_module.height or self.vis_mod.DEFAULT_SIZE.height()
        if screen_rect:
            vis_w = min(vis_w, screen_rect.width())
            vis_h = min(vis_h, screen_rect.height())
        self.vis_mod.set_user_size(vis_w, vis_h)

        vx, vy = st.vis_module.x, st.vis_module.y
        if screen_rect:
            vx, vy = SessionManager.clamp_to_screen(vx, vy, self.vis_mod.width(), self.vis_mod.height(), screen_rect)
        self.vis_mod.move(vx, vy)
        self.vis_mod.is_docked = st.vis_module.is_docked
        self.vis_mod.dock_edge = st.vis_module.dock_edge

        # Playlist Geometry & Size
        pl_w = st.pl_module.width or self.pl_mod.DEFAULT_SIZE.width()
        pl_h = st.pl_module.height or self.pl_mod.DEFAULT_SIZE.height()
        if screen_rect:
            pl_w = min(pl_w, screen_rect.width())
            pl_h = min(pl_h, screen_rect.height())
        self.pl_mod.set_user_size(pl_w, pl_h)

        px, py = st.pl_module.x, st.pl_module.y
        if screen_rect:
            px, py = SessionManager.clamp_to_screen(px, py, self.pl_mod.width(), self.pl_mod.height(), screen_rect)
        self.pl_mod.move(px, py)
        self.pl_mod.is_docked = st.pl_module.is_docked
        self.pl_mod.dock_edge = st.pl_module.dock_edge

        # 7. Restore Module Visibility
        if st.scale == "normal":
            if st.vis_module.is_visible:
                self._sync_embedded_host(self.vis_mod, True)
                self.vis_mod.show()
                self.chassis.chip_vis.setChecked(True)
            if st.pl_module.is_visible:
                self._sync_embedded_host(self.pl_mod, True)
                self.pl_mod.show()
                self.chassis.chip_pl.setChecked(True)
            self.realign_docked_modules()

    def _wire_signals(self):
        # Chassis Controls
        self.chassis.scale_changed.connect(self._on_scale_changed)
        self.chassis.retina_melt_requested.connect(self._enter_retina_melt)
        self.chassis.minimize_requested.connect(lambda: self.chassis.set_mode("mini"))
        self.chassis.close_requested.connect(self.shutdown)
        self.chassis.play_toggled.connect(self._toggle_play)
        self.chassis.prev_clicked.connect(self._play_previous)
        self.chassis.next_clicked.connect(self._play_next)
        self.chassis.stop_clicked.connect(self._stop_playback)
        self.chassis.seek_changed.connect(self._on_seek)
        self.chassis.volume_changed.connect(self._on_volume_changed)
        self.chassis.toggle_fade_clicked.connect(self._on_fade_toggled)
        self.chassis.toggle_vis_clicked.connect(self._toggle_vis)
        self.chassis.toggle_pl_clicked.connect(self._toggle_pl)
        self.chassis.files_dropped.connect(self._on_files_dropped)
        self.chassis.theme_toggle_requested.connect(self._on_theme_toggle)


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
        self.retina_melt.volume_changed.connect(self._on_volume_changed)
        self.retina_melt.visualizer_switched.connect(self._on_retina_visualizer_switched)
        self.retina_melt.seek_changed.connect(self._on_seek)

        # System Tray Controls
        self.tray_icon.restore_requested.connect(self._focus_chassis)
        self.tray_icon.play_toggled.connect(self._toggle_play)
        self.tray_icon.prev_requested.connect(self._play_previous)
        self.tray_icon.next_requested.connect(self._play_next)
        self.tray_icon.exit_requested.connect(self.shutdown)

    def _on_fade_toggled(self, enabled: bool):
        self.player_engine.fade_enabled = enabled
        self.session_state.fade_enabled = enabled
        self.session_manager.save()

    def _on_theme_toggle(self):
        new_theme_id = self.theme_manager.toggle_theme()
        self.neon_controller.set_theme_id(new_theme_id)
        self.session_state.theme_id = new_theme_id
        self.session_manager.save()

    def _focus_chassis(self):
        """
        Tray 'Restore Player' action. If MINI, restores full NORMAL via the
        existing authoritative MINI->NORMAL transition (chassis.set_mode,
        same path the chassis's own ▲ NORMAL button uses) — this is what
        drives module restoration through _on_scale_changed, so there is
        only one restoration path. Already-NORMAL just raises/focuses.
        """
        if self.chassis.mode == "mini":
            self.chassis.set_mode("normal")
        self.chassis.raise_()
        self.chassis.activateWindow()


    def save_current_session(self):
        """Gathers current runtime state and writes atomically to session JSON."""
        st = self.session_state
        st.scale = self.chassis.mode
        st.theme_id = self.theme_manager.active_theme_id
        st.volume = self.player_engine.volume
        st.fade_enabled = self.player_engine.fade_enabled
        st.shuffle = self.playlist.shuffle
        st.repeat = self.playlist.repeat
        st.selected_visualizer_idx = self.vis_mod.vis_idx

        # Chassis position
        cp = self.chassis.pos()
        st.chassis_pos = WindowPosition(x=cp.x(), y=cp.y(), w=self.chassis.width(), h=self.chassis.height())

        # Visualizer position & state — user_size (not live geometry) is
        # persisted so a currently-docked, width-locked module still saves
        # the floating size the human actually chose.
        vp = self.vis_mod.pos()
        st.vis_module = ModulePosition(
            x=vp.x(),
            y=vp.y(),
            width=self.vis_mod.user_size.width(),
            height=self.vis_mod.user_size.height(),
            is_docked=self.vis_mod.is_docked,
            dock_edge=self.vis_mod.dock_edge or "bottom",
            is_visible=self.vis_mod.isVisible() if self.chassis.mode == "normal" else self.saved_vis_visible
        )

        # Playlist position & state
        pp = self.pl_mod.pos()
        st.pl_module = ModulePosition(
            x=pp.x(),
            y=pp.y(),
            width=self.pl_mod.user_size.width(),
            height=self.pl_mod.user_size.height(),
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
        if getattr(self, "_is_shutting_down", False):
            return
        self._is_shutting_down = True

        logger.info("Executing ToroidAMP shutdown sequence")
        self.save_current_session()

        # Stop timers
        self.render_timer.stop()
        self.snap_timer.stop()

        # Stop playback and release audio hardware
        self.player_engine.stop()
        self.player_engine.close()

        # Explicit GPU resource release while contexts are still current.
        # GLVisualizerCanvas.closeEvent() -- its own explicit cleanupGL()
        # call -- only fires for a *top-level* window being closed; both
        # gpu_canvas instances here are *child* widgets of vis_mod/
        # retina_melt, and closing a parent widget does not cascade
        # closeEvent() to its children (Qt only destroys them via the
        # ordinary object-tree destructor cascade). Their only other
        # cleanup path is each canvas's own QOpenGLContext.
        # aboutToBeDestroyed signal, which fires whenever Qt/Python
        # actually gets around to destroying that widget -- typically
        # during CPython's own interpreter-shutdown GC sweep after
        # QApplication.quit() returns control below, an environment that
        # does not reliably preserve "signal before the context becomes
        # unusable" ordering. That race is what produced
        # "QOpenGLTexturePrivate::destroy() called without a current
        # context" on shutdown. Calling cleanupGL() here, directly, while
        # the event loop and both contexts are still fully valid, releases
        # every GPU resource deterministically; cleanupGL() is already
        # idempotent, so the later aboutToBeDestroyed-triggered call (if
        # it ever fires) safely finds nothing left to do.
        try:
            self.vis_mod.gpu_canvas.cleanupGL()
        except Exception:
            pass
        try:
            self.retina_melt.gpu_canvas.cleanupGL()
        except Exception:
            pass

        # Close all windows and tray
        self.retina_melt.hide()
        self.vis_mod.hide()
        self.pl_mod.hide()
        self.chassis.hide()
        self.tray_icon.hide()

        self.retina_melt.close()
        self.vis_mod.close()
        self.pl_mod.close()
        self.chassis.close()

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
        self.chassis.set_volume(vol)
        self.retina_melt.set_volume(vol)
        self.session_state.volume = vol

    def _on_retina_visualizer_switched(self, index: int):
        self.vis_mod.vis_idx = index
        self.vis_mod._update_presentation_mode()
        self.session_state.selected_visualizer_idx = index

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
            self._sync_embedded_host(self.vis_mod, False)
            self.pl_mod.hide()
            self._sync_embedded_host(self.pl_mod, False)
            self.prior_scale = "mini"
        elif new_scale == "normal":
            if self.saved_vis_visible:
                if self.vis_mod.is_docked:
                    self.dock_module(self.vis_mod, "bottom")
                self._sync_embedded_host(self.vis_mod, True)
                self.vis_mod.show()
                self.chassis.chip_vis.setChecked(True)
            if self.saved_pl_visible:
                if self.pl_mod.is_docked:
                    self.dock_module(self.pl_mod, "right")
                self._sync_embedded_host(self.pl_mod, True)
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
        self._sync_embedded_host(self.vis_mod, False)
        self.pl_mod.hide()
        self._sync_embedded_host(self.pl_mod, False)
        self.retina_melt.set_volume(self.player_engine.volume)
        self.retina_melt.set_visualizer_index(self.vis_mod.vis_idx)
        self.retina_melt.show_fullscreen_experience()

    def _exit_retina_melt(self):
        self.retina_melt.hide()
        self.vis_mod._update_presentation_mode()
        self.chassis.set_mode(self.prior_scale, animated=False)
        self.chassis.show()

    def _toggle_vis(self):
        if self.vis_mod.isVisible():
            self.vis_mod.hide()
            self._sync_embedded_host(self.vis_mod, False)
            self.chassis.chip_vis.setChecked(False)
        else:
            self.dock_module(self.vis_mod, "bottom")
            self._sync_embedded_host(self.vis_mod, True)
            self.vis_mod.show()
            self.chassis.chip_vis.setChecked(True)

    def _toggle_pl(self):
        if self.pl_mod.isVisible():
            self.pl_mod.hide()
            self._sync_embedded_host(self.pl_mod, False)
            self.chassis.chip_pl.setChecked(False)
        else:
            self.dock_module(self.pl_mod, "right")
            self._sync_embedded_host(self.pl_mod, True)
            self.pl_mod.show()
            self.chassis.chip_pl.setChecked(True)

    def _sync_embedded_host(self, module: ModuleShell, visible: bool) -> None:
        """
        Wayland-only: mirrors a module's open/closed state into the
        chassis's grid-hosted embedding (see UnifiedChassis.embed_module()
        and the `_wayland_embedded` note in __init__). A complete no-op on
        Windows/X11, where these modules are independent top-level windows
        managed by the existing dock_module()/realign_docked_modules() path
        instead.
        """
        if not self._wayland_embedded:
            return
        region = "right" if module is self.pl_mod else "bottom"
        self.chassis.embed_module(region, module if visible else None)

    def dock_module(self, module: ModuleShell, edge: str):
        if self._wayland_embedded:
            # Embedded modules have no independent top-level position to
            # dock -- their placement is entirely owned by the chassis's
            # grid layout (embed_module(), synced via _sync_embedded_host()
            # at each show/hide call site). Nothing to do here.
            return
        module.is_docked = True
        module.dock_edge = edge
        self.realign_docked_modules()

    def undock_module(self, module: ModuleShell):
        module.is_docked = False
        module.dock_edge = None
        # DOCK / UNDOCK / REDOCK must preserve the user's chosen floating
        # size — restore it now that docking constraints no longer apply.
        module.restore_user_size()

    def realign_docked_modules(self):
        # Windows/X11 only (RELEASE-BLOCKERS-001): the move() calls below
        # place independent top-level VIS/PL windows correctly there. On
        # Wayland, xdg-shell gives a client no way to set an independent
        # top-level's absolute position at all -- compositors place every
        # xdg_toplevel themselves (GNOME/Mutter centers them), which is
        # exactly what made these modules appear centered/overlapping
        # instead of docked (UBUNTU-WAYLAND-002). Rather than keep fighting
        # that protocol limitation, Wayland hosts VIS/PL as embedded child
        # widgets instead (see `_wayland_embedded` in __init__ and
        # UnifiedChassis.embed_module()), which sidesteps it entirely --
        # this method has nothing to do on that path.
        if self._wayland_embedded:
            return
        if self.chassis.mode != "normal" or not self.chassis.isVisible():
            return
        core_geom = self.chassis.geometry()

        if self.vis_mod.is_docked and self.vis_mod.isVisible():
            # Docked VIS aligns its width to the chassis (simplest predictable
            # behavior); height stays whatever the user has resized it to.
            if self.vis_mod.width() != core_geom.width():
                self.vis_mod.resize(core_geom.width(), self.vis_mod.height())
            self.vis_mod.move(core_geom.left(), core_geom.bottom() + 2)

        if self.pl_mod.is_docked and self.pl_mod.isVisible():
            # Docking defines PL's ATTACHMENT (x follows the chassis right
            # edge, y follows the chassis top) — it does not define PL's
            # size. Height is user-resizable while docked and must survive
            # realignment untouched (UX-003 follow-up: "Docked Playlist
            # Vertical Resize"). A modular instrument may have asymmetric
            # module dimensions; PL is free to extend above or below the
            # VIS+chassis stack.
            self.pl_mod.move(core_geom.right() + 2, core_geom.top())

    def _check_magnetic_snapping(self):
        if self._wayland_embedded:
            # Embedded modules have no independent position to drift from
            # and re-snap to -- dragging is disabled for them entirely
            # (see ModuleShell.mousePressEvent's `embedded` guard).
            return
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
        # 0. Check and Handle Decoder Failure from Audio Thread
        has_error, failed_path, error_msg = self.player_engine.check_and_clear_error()
        if has_error:
            track_name = os.path.basename(failed_path) if failed_path else "Current Track"
            logger.warning(f"Playback decoder failure on '{track_name}': {error_msg}")
            # Safely advance to next track if playlist has items
            if len(self.playlist) > 0:
                next_idx = self.playlist.get_next_index()
                if next_idx is not None and next_idx != self.playlist.current_index:
                    self._play_index(next_idx)
                else:
                    self._stop_playback()
            else:
                self._stop_playback()

        # 1. Automatic Track Advancement on natural EOF only. PlaybackState
        # .STOPPED alone is not a reliable signal here -- it's also the
        # state a user-initiated STOP lands in, including the delayed
        # transition a fade-out completes asynchronously in the audio
        # callback well after PlayerEngine.stop() already returned.
        # consume_natural_eof() is set only where the decoder itself
        # genuinely ran out of frames, never by a user stop/pause/seek.
        elif self.player_engine.consume_natural_eof() and len(self.playlist) > 0:
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
        self.retina_melt.set_seek_position(pos, dur)
        self.tray_icon.update_status(title_str, is_playing)

        # 3. Update Reactive Neon Chassis & Module Breathing (~60 FPS)
        # Chassis is always visible — neon always runs.
        frame = self.handoff.get_audio_frame(44100) if is_playing else None
        is_mini = (self.chassis.mode == "mini")
        neon_state = self.neon_controller.update(0.016, frame, is_mini=is_mini)
        self.chassis.apply_neon_state(neon_state)
        if self.vis_mod.isVisible():
            self.vis_mod.apply_neon_state(neon_state)
        if self.pl_mod.isVisible():
            self.pl_mod.apply_neon_state(neon_state)

        # 4. Only compute DSP & render visualizer if a visualizer is actually visible!
        # (Zero CPU/GPU visualizer waste when hidden to tray or in MINI mode)
        if self.vis_mod.isVisible() or self.retina_melt.isVisible():
            frame = self.handoff.get_audio_frame(44100)
            if self.vis_mod.isVisible():
                self.vis_mod.render_frame(frame, 0.016)
            if self.retina_melt.isVisible():
                self.retina_melt.render_frame(frame, 0.016)

