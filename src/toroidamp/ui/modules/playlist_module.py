"""
ToroidAMP - Production Playlist Module
Provides interactive track list, drag-and-drop, add/remove,
reorder, clear, shuffle, repeat, and M3U/M3U8 load/save.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMenu, QAbstractItemView
)
from PySide6.QtCore import Qt, QSize, Signal, QPoint, QEvent, QItemSelectionModel
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from .base import ModuleShell
from ..neon import NeonState
from ..theme import ThemeDefinition
from ..dialogs import platform_file_dialog_options
from ...audio.playlist import PlaylistManager, PlaylistItem



class PlaylistModule(ModuleShell):
    """
    Compact Dockable Playlist Module.
    """
    track_double_clicked = Signal(int)
    files_dropped = Signal(list)
    shuffle_toggled = Signal(bool)
    repeat_toggled = Signal(bool)

    SUPPORTED_EXTENSIONS = {".mp3", ".ogg", ".wav", ".flac", ".mod", ".xm", ".it", ".s3m"}

    # UX-003: 270x240 is the established production default. 230x200 keeps
    # the six toolbar buttons and footer usable while leaving a real list.
    DEFAULT_SIZE = QSize(270, 240)
    MIN_SIZE = QSize(230, 200)
    # Docking only anchors PL's position (x to the chassis right edge, y to
    # the chassis top) — it must not force PL's size. Dragging the left/top
    # edges while docked would fight that position anchor (realign would
    # immediately snap them back), so only those two are excluded; width and
    # height (right/bottom edges) remain fully user-resizable while docked —
    # see UX-003 follow-up "Docked Playlist Vertical Resize".
    DOCK_LOCKED_EDGES = {"left", "top"}

    def __init__(self, manager: PlaylistManager, parent=None, embedded: bool = False):
        super().__init__("// MODULE :: PLAYLIST", parent, embedded=embedded)
        self.manager = manager
        self.setAcceptDrops(True)

        # Playlist ListWidget
        self.list_widget = QListWidget(self)
        self.list_widget.setAcceptDrops(True)
        # v0.666: native Qt multi-selection -- single click / Ctrl+click
        # (additive/discontinuous) / Shift+click (range) all come free with
        # ExtendedSelection, no custom selection tracking needed.
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #06070a;
                border: 1px solid #1a1d2e;
                color: #8892b0;
                font-family: monospace;
                font-size: 10px;
                padding: 2px;
            }
            QListWidget::item {
                padding: 3px;
                border-bottom: 1px solid #11131c;
            }
            QListWidget::item:selected {
                background-color: #141a2e;
                color: #00f0ff;
                font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: #0f121d;
                color: #00e5ff;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.installEventFilter(self)
        self.main_layout.addWidget(self.list_widget, stretch=1)

        # Action Toolbar (Add, Del, Clear, M3U)
        btn_bar = QWidget(self)
        btn_bar.setFixedHeight(22)
        b_layout = QHBoxLayout(btn_bar)
        b_layout.setContentsMargins(2, 0, 2, 0)
        b_layout.setSpacing(3)

        btn_style = """
            QPushButton {
                background-color: #141724;
                border: 1px solid #28304a;
                border-radius: 2px;
                color: #8892b0;
                font-family: monospace;
                font-size: 9px;
                font-weight: bold;
                padding: 2px 4px;
            }
            QPushButton:hover {
                border-color: #00f0ff;
                color: #00f0ff;
            }
            QPushButton:checked {
                background-color: #00f0ff;
                color: #000000;
            }
        """
        self.btn_add = QPushButton("+ADD", btn_bar)
        self.btn_add.setObjectName("playlistBtnAdd")
        self.btn_add.setProperty("themeRole", "playlistAction")
        self.btn_add.setStyleSheet(btn_style)
        self.btn_add.clicked.connect(self._browse_add_files)
        b_layout.addWidget(self.btn_add)

        self.btn_del = QPushButton("-DEL", btn_bar)
        self.btn_del.setObjectName("playlistBtnDel")
        self.btn_del.setProperty("themeRole", "playlistAction")
        self.btn_del.setStyleSheet(btn_style)
        self.btn_del.clicked.connect(self._remove_selected)
        b_layout.addWidget(self.btn_del)

        self.btn_clear = QPushButton("CLR", btn_bar)
        self.btn_clear.setObjectName("playlistBtnClear")
        self.btn_clear.setProperty("themeRole", "playlistAction")
        self.btn_clear.setStyleSheet(btn_style)
        self.btn_clear.clicked.connect(self._clear_playlist)
        b_layout.addWidget(self.btn_clear)

        self.btn_shf = QPushButton("SHF", btn_bar)
        self.btn_shf.setObjectName("playlistBtnShuffle")
        self.btn_shf.setProperty("themeRole", "playlistAction")
        self.btn_shf.setCheckable(True)
        self.btn_shf.setStyleSheet(btn_style)
        self.btn_shf.clicked.connect(self._toggle_shuffle)
        b_layout.addWidget(self.btn_shf)

        self.btn_rep = QPushButton("REP", btn_bar)
        self.btn_rep.setObjectName("playlistBtnRepeat")
        self.btn_rep.setProperty("themeRole", "playlistAction")
        self.btn_rep.setCheckable(True)
        self.btn_rep.setStyleSheet(btn_style)
        self.btn_rep.clicked.connect(self._toggle_repeat)
        b_layout.addWidget(self.btn_rep)

        self.btn_m3u = QPushButton("M3U", btn_bar)
        self.btn_m3u.setObjectName("playlistBtnM3u")
        self.btn_m3u.setProperty("themeRole", "playlistAction")
        self.btn_m3u.setStyleSheet(btn_style)
        self.btn_m3u.clicked.connect(self._m3u_menu)
        b_layout.addWidget(self.btn_m3u)

        self.main_layout.addWidget(btn_bar)

        # Queue Footer Info
        foot_bar = QWidget(self)
        foot_bar.setFixedHeight(18)
        f_layout = QHBoxLayout(foot_bar)
        f_layout.setContentsMargins(2, 0, 2, 0)
        self.queue_info = QLabel("TOTAL: 0 TRACKS", foot_bar)
        f_layout.addWidget(self.queue_info)
        self.main_layout.addWidget(foot_bar)

        self.apply_theme(self._current_theme)

    def apply_theme(self, theme: ThemeDefinition):
        """Applies theme palette and typography across playlist list and buttons."""
        super().apply_theme(theme)
        pal = theme.palette
        typo = theme.typography

        mono_font = f"'{typo.monospace_family}', monospace"

        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {pal.list_bg};
                border: 1px solid {pal.list_border};
                color: {pal.list_item_text};
                font-family: {mono_font};
                font-size: 10px;
                padding: 2px;
            }}
            QListWidget::item {{
                padding: 3px;
                border-bottom: 1px solid {pal.list_item_border};
            }}
            QListWidget::item:selected {{
                background-color: {pal.list_selected_bg};
                color: {pal.list_selected_text};
                font-weight: bold;
            }}
            QListWidget::item:hover {{
                background-color: {pal.list_hover_bg};
                color: {pal.list_hover_text};
            }}
        """)

        # In Cyber Yellow, playlist action buttons use the canonical red accent (pal.accent); Default uses cyan (pal.primary)
        pl_btn_accent = pal.accent if theme.id == "cyber_yellow" else pal.primary
        pl_btn_border_hover = pal.accent if theme.id == "cyber_yellow" else pal.border_control_hover

        base_pl_btn_style = f"""
            QPushButton[themeRole="playlistAction"] {{
                background-color: {pal.bg_control};
                border: 1px solid {pal.border_control};
                border-radius: 2px;
                color: {pal.text_muted};
                font-family: {mono_font};
                font-size: 9px;
                font-weight: bold;
                padding: 2px 4px;
            }}
            QPushButton[themeRole="playlistAction"]:hover {{
                border-color: {pl_btn_border_hover};
                color: {pl_btn_accent};
            }}
            QPushButton[themeRole="playlistAction"]:pressed {{
                background-color: {pl_btn_accent};
                color: {pal.bg_lcd};
                border-color: {pl_btn_accent};
            }}
            QPushButton[themeRole="playlistAction"]:checked {{
                background-color: {pl_btn_accent};
                color: #ffffff;
                border-color: {pl_btn_accent};
            }}
            QPushButton[themeRole="playlistAction"]:disabled {{
                color: {pal.text_dim};
                border-color: {pal.border_control};
                background-color: {pal.bg_surface};
            }}
        """
        # Clear widget-local overrides so parent/QSS cascade rules win
        for btn in (self.btn_add, self.btn_del, self.btn_clear, self.btn_shf, self.btn_rep, self.btn_m3u):
            btn.setStyleSheet("")

        self.queue_info.setStyleSheet(f"color: {pal.text_dim}; font-family: {mono_font}; font-size: 9px;")

        # Apply combined base + optional theme.qss override to the module container
        combined_mod_qss = base_pl_btn_style + "\n" + (theme.qss_override or "")
        self.setStyleSheet(combined_mod_qss)

    def refresh(self):
        """Refreshes the ListWidget to reflect current PlaylistManager state."""
        # v0.666: "currently playing" and "currently selected" are distinct
        # states. refresh() can fire for reasons unrelated to selection
        # (track advance, a bulk edit elsewhere) -- preserve whichever rows
        # the user had selected instead of letting the playing-row indicator
        # silently steal the selection out from under them.
        selected_rows = {self.list_widget.row(i) for i in self.list_widget.selectedItems()}

        self.list_widget.clear()
        for idx, item in enumerate(self.manager.items):
            prefix = "▶ " if idx == self.manager.current_index else "  "
            list_item = QListWidgetItem(f"{prefix}[{idx+1:02d}] {item.title:<18} {item.display_duration}")
            self.list_widget.addItem(list_item)

        self.queue_info.setText(f"TOTAL: {len(self.manager)} TRACKS")
        if 0 <= self.manager.current_index < len(self.manager):
            # NoUpdate: move the keyboard/"now playing" cursor without also
            # selecting the row -- selection is a separate, user-owned state.
            self.list_widget.setCurrentRow(self.manager.current_index, QItemSelectionModel.NoUpdate)

        for row in selected_rows:
            if 0 <= row < self.list_widget.count():
                self.list_widget.item(row).setSelected(True)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        row = self.list_widget.row(item)
        if row >= 0:
            self.manager.current_index = row
            self.refresh()
            self.track_double_clicked.emit(row)

    def _browse_add_files(self):
        filter_str = "Audio Files (*.mp3 *.ogg *.wav *.flac *.mod *.xm *.it *.s3m);;All Files (*.*)"
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Audio Tracks to Playlist",
            "",
            filter_str,
            options=platform_file_dialog_options()
        )
        if paths:
            self.manager.add_files(paths)
            self.refresh()

    def _remove_selected(self):
        """Removes every selected row in one operation (falls back to the
        current row when nothing is explicitly selected)."""
        rows = sorted({self.list_widget.row(i) for i in self.list_widget.selectedItems()}, reverse=True)
        if not rows:
            row = self.list_widget.currentRow()
            if row >= 0:
                rows = [row]
        if not rows:
            return
        for row in rows:
            self.manager.remove_at(row)
        self.refresh()

    def eventFilter(self, obj, event):
        if obj is self.list_widget and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                self._remove_selected()
                return True
        return super().eventFilter(obj, event)

    def _clear_playlist(self):
        self.manager.clear()
        self.refresh()

    def _toggle_shuffle(self, checked: bool):
        self.manager.shuffle = checked
        self.shuffle_toggled.emit(checked)

    def _toggle_repeat(self, checked: bool):
        self.manager.repeat = checked
        self.repeat_toggled.emit(checked)

    def _m3u_menu(self):
        """Presents an action chooser menu for loading or saving M3U/M3U8 playlists."""
        pal = self._current_theme.palette
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {pal.bg_surface_alt};
                border: 1px solid {pal.border_panel};
                color: {pal.text_primary};
                font-family: monospace;
                font-size: 10px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 4px 16px 4px 12px;
                border-radius: 2px;
            }}
            QMenu::item:selected {{
                background-color: {pal.primary};
                color: {pal.bg_lcd};
                font-weight: bold;
            }}
        """)
        
        load_action = menu.addAction("LOAD M3U PLAYLIST")
        save_action = menu.addAction("SAVE M3U8 PLAYLIST")
        
        # Position popup above/at the M3U button
        btn_pos = self.btn_m3u.mapToGlobal(QPoint(0, self.btn_m3u.height()))
        selected = menu.exec(btn_pos)
        
        if selected == load_action:
            filter_str = "Playlist Files (*.m3u *.m3u8);;All Files (*.*)"
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Load Playlist",
                "",
                filter_str,
                options=platform_file_dialog_options()
            )
            if path:
                self.manager.load_m3u(path)
                self.refresh()
        elif selected == save_action:
            filter_str = "M3U8 Playlist (*.m3u8);;M3U Playlist (*.m3u)"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Playlist",
                "playlist.m3u8",
                filter_str,
                options=platform_file_dialog_options()
            )
            if path:
                self.manager.save_m3u(path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        dropped_files = []
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if os.path.isfile(local_path):
                ext = os.path.splitext(local_path)[1].lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    dropped_files.append(local_path)
                elif ext in {".m3u", ".m3u8"}:
                    self.manager.load_m3u(local_path)
        if dropped_files:
            self.manager.add_files(dropped_files)
            self.refresh()
            self.files_dropped.emit(dropped_files)
        event.acceptProposedAction()

    def apply_neon_state(self, state: NeonState):
        """Propagates spectral neon palette to playlist container and active selections."""
        super().apply_neon_state(state)
        p_col = state.tier2_panel_color.name()
        c_col = state.tier1_chassis_color.name()

        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: #06070a;
                border: 1px solid {p_col};
                color: #8892b0;
                font-family: monospace;
                font-size: 10px;
                padding: 2px;
                border-radius: 2px;
            }}
            QListWidget::item {{
                padding: 3px;
                border-bottom: 1px solid #11131c;
            }}
            QListWidget::item:selected {{
                background-color: #141a2e;
                color: {c_col};
                font-weight: bold;
            }}
            QListWidget::item:hover {{
                background-color: #0f121d;
                color: #00e5ff;
            }}
        """)
        self.title_label.setStyleSheet(f"color: {c_col}; font-family: monospace; font-size: 10px; font-weight: bold;")

