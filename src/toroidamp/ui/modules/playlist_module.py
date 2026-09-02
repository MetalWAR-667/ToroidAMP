"""
ToroidAMP - Production Playlist Module
Provides interactive track list, drag-and-drop, add/remove,
reorder, clear, shuffle, repeat, quick search/filter, and M3U/M3U8 load/save.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMenu, QAbstractItemView,
    QLineEdit
)
from PySide6.QtCore import Qt, QSize, Signal, QPoint, QEvent, QItemSelectionModel
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from .base import ModuleShell
from ..neon import NeonState
from ..theme import ThemeDefinition
from ..dialogs import platform_file_dialog_options
from ...audio.playlist import PlaylistManager, PlaylistItem, SUPPORTED_AUDIO_EXTENSIONS



class PlaylistModule(ModuleShell):
    """
    Compact Dockable Playlist Module.
    """
    track_double_clicked = Signal(int)
    files_dropped = Signal(list)
    shuffle_toggled = Signal(bool)
    repeat_toggled = Signal(bool)

    SUPPORTED_EXTENSIONS = SUPPORTED_AUDIO_EXTENSIONS

    # UX-003: 270x240 is the established production default. 230x200 keeps
    # the toolbar buttons, search, and footer usable while leaving a real list.
    DEFAULT_SIZE = QSize(270, 240)
    MIN_SIZE = QSize(230, 200)
    DOCK_LOCKED_EDGES = {"left", "top"}

    def __init__(self, manager: PlaylistManager, parent=None, embedded: bool = False):
        super().__init__("// MODULE :: PLAYLIST", parent, embedded=embedded)
        self.manager = manager
        self._search_query: str = ""
        self._filtered_indices: list[int] = []
        self.setAcceptDrops(True)

        # Quick Search Bar (UX-005C)
        self.search_container = QWidget(self)
        self.search_container.setFixedHeight(22)
        search_layout = QHBoxLayout(self.search_container)
        search_layout.setContentsMargins(2, 0, 2, 0)
        search_layout.setSpacing(3)

        self.search_edit = QLineEdit(self.search_container)
        self.search_edit.setObjectName("playlistSearchEdit")
        self.search_edit.setPlaceholderText("Filter playlist (Esc to clear)...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_edit.installEventFilter(self)
        search_layout.addWidget(self.search_edit, stretch=1)

        self.btn_clear_search = QPushButton("✕", self.search_container)
        self.btn_clear_search.setObjectName("playlistBtnClearSearch")
        self.btn_clear_search.setFixedSize(16, 16)
        self.btn_clear_search.setToolTip("Clear search (Esc)")
        self.btn_clear_search.clicked.connect(self.hide_search)
        search_layout.addWidget(self.btn_clear_search)

        self.search_container.hide()
        self.main_layout.addWidget(self.search_container)

        # Playlist ListWidget
        self.list_widget = QListWidget(self)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.installEventFilter(self)
        self.main_layout.addWidget(self.list_widget, stretch=1)

        # Action Toolbar (Add, Del, Clear, Shuffle, Repeat, M3U)
        btn_bar = QWidget(self)
        btn_bar.setFixedHeight(22)
        b_layout = QHBoxLayout(btn_bar)
        b_layout.setContentsMargins(2, 0, 2, 0)
        b_layout.setSpacing(3)

        self.btn_add = QPushButton("+ADD", btn_bar)
        self.btn_add.setObjectName("playlistBtnAdd")
        self.btn_add.setProperty("themeRole", "playlistAction")
        self.btn_add.clicked.connect(self._browse_add_files)
        b_layout.addWidget(self.btn_add)

        self.btn_del = QPushButton("-DEL", btn_bar)
        self.btn_del.setObjectName("playlistBtnDel")
        self.btn_del.setProperty("themeRole", "playlistAction")
        self.btn_del.clicked.connect(self._remove_selected)
        b_layout.addWidget(self.btn_del)

        self.btn_clear = QPushButton("CLR", btn_bar)
        self.btn_clear.setObjectName("playlistBtnClear")
        self.btn_clear.setProperty("themeRole", "playlistAction")
        self.btn_clear.clicked.connect(self._clear_playlist)
        b_layout.addWidget(self.btn_clear)

        self.btn_shf = QPushButton("SHF", btn_bar)
        self.btn_shf.setObjectName("playlistBtnShuffle")
        self.btn_shf.setProperty("themeRole", "playlistAction")
        self.btn_shf.setCheckable(True)
        self.btn_shf.clicked.connect(self._toggle_shuffle)
        b_layout.addWidget(self.btn_shf)

        self.btn_rep = QPushButton("REP", btn_bar)
        self.btn_rep.setObjectName("playlistBtnRepeat")
        self.btn_rep.setProperty("themeRole", "playlistAction")
        self.btn_rep.setCheckable(True)
        self.btn_rep.clicked.connect(self._toggle_repeat)
        b_layout.addWidget(self.btn_rep)

        self.btn_m3u = QPushButton("M3U", btn_bar)
        self.btn_m3u.setObjectName("playlistBtnM3u")
        self.btn_m3u.setProperty("themeRole", "playlistAction")
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

        # Search field styling
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {pal.bg_lcd};
                border: 1px solid {pal.primary};
                border-radius: 2px;
                color: {pal.text_lcd};
                font-family: {mono_font};
                font-size: 9px;
                padding: 1px 4px;
            }}
            QLineEdit:focus {{
                border: 1px solid {pal.accent if theme.id == 'cyber_yellow' else '#ffffff'};
            }}
        """)

        self.btn_clear_search.setStyleSheet(f"""
            QPushButton {{
                background-color: {pal.bg_control};
                border: 1px solid {pal.border_control};
                border-radius: 2px;
                color: {pal.text_muted};
                font-family: {mono_font};
                font-size: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {pal.danger};
                border-color: {pal.danger};
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
        for btn in (self.btn_add, self.btn_del, self.btn_clear, self.btn_shf, self.btn_rep, self.btn_m3u):
            btn.setStyleSheet("")

        self.queue_info.setStyleSheet(f"color: {pal.text_dim}; font-family: {mono_font}; font-size: 9px;")

        combined_mod_qss = base_pl_btn_style + "\n" + (theme.qss_override or "")
        self.setStyleSheet(combined_mod_qss)

    def show_search(self):
        """Exposes and focuses the quick search filter."""
        self.search_container.show()
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def hide_search(self):
        """Clears search filter, restores full canonical list, and hides search bar."""
        self.search_edit.clear()
        self._search_query = ""
        self.search_container.hide()
        self.refresh()
        self.list_widget.setFocus()

    def _on_search_text_changed(self, text: str):
        """Updates incremental search filter."""
        self._search_query = text.strip()
        self.refresh()

    def refresh(self):
        """
        Refreshes the ListWidget to reflect current PlaylistManager state or active filter.
        Search/filter is purely a VIEW operation and never mutates underlying playlist order or content.
        """
        # Preserve selection across refresh via canonical item index stored in Qt.UserRole
        selected_canonical_indices = set()
        for r in range(self.list_widget.count()):
            item = self.list_widget.item(r)
            if item.isSelected():
                can_idx = item.data(Qt.UserRole)
                if can_idx is not None:
                    selected_canonical_indices.add(can_idx)

        self.list_widget.clear()
        self._filtered_indices = []

        q = self._search_query.lower()
        for idx, item in enumerate(self.manager.items):
            if not q or (q in item.title.lower() or q in os.path.basename(item.filepath).lower()):
                self._filtered_indices.append(idx)
                prefix = "▶ " if idx == self.manager.current_index else "  "
                list_item = QListWidgetItem(f"{prefix}[{idx+1:02d}] {item.title:<18} {item.display_duration}")
                list_item.setData(Qt.UserRole, idx)
                self.list_widget.addItem(list_item)
                if idx in selected_canonical_indices:
                    list_item.setSelected(True)

        if self._search_query:
            self.queue_info.setText(f"MATCHES: {len(self._filtered_indices)} / {len(self.manager)}")
        else:
            self.queue_info.setText(f"TOTAL: {len(self.manager)} TRACKS")

        # Set cursor on playing track if present in visible rows
        if 0 <= self.manager.current_index < len(self.manager):
            for r in range(self.list_widget.count()):
                if self.list_widget.item(r).data(Qt.UserRole) == self.manager.current_index:
                    self.list_widget.setCurrentRow(r, QItemSelectionModel.NoUpdate)
                    break

    def _on_item_double_clicked(self, item: QListWidgetItem):
        canonical_idx = item.data(Qt.UserRole)
        if canonical_idx is not None and 0 <= canonical_idx < len(self.manager):
            self.manager.current_index = canonical_idx
            self.refresh()
            self.track_double_clicked.emit(canonical_idx)

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
        """
        Removes every selected row in one operation using canonical indices
        (falls back to the current row when nothing is explicitly selected).
        """
        canonical_indices = sorted(
            {self.list_widget.item(r).data(Qt.UserRole) for r in range(self.list_widget.count()) if self.list_widget.item(r).isSelected()},
            reverse=True
        )
        if not canonical_indices:
            curr = self.list_widget.currentItem()
            if curr and curr.data(Qt.UserRole) is not None:
                canonical_indices = [curr.data(Qt.UserRole)]
        if not canonical_indices:
            return
        for idx in canonical_indices:
            self.manager.remove_at(idx)
        self.refresh()

    def eventFilter(self, obj, event):
        if obj is self.search_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.hide_search()
                return True
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if self.list_widget.count() > 0:
                    row = self.list_widget.currentRow()
                    if row < 0 or row >= self.list_widget.count():
                        row = 0
                    item = self.list_widget.item(row)
                    self._on_item_double_clicked(item)
                return True
            elif event.key() == Qt.Key_Down:
                if self.list_widget.count() > 0:
                    self.list_widget.setFocus()
                    if self.list_widget.currentRow() < 0:
                        self.list_widget.setCurrentRow(0)
                return True

        if obj is self.list_widget and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_F and (event.modifiers() & Qt.ControlModifier):
                self.show_search()
                return True
            elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                self._remove_selected()
                return True
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                curr = self.list_widget.currentItem()
                if curr:
                    self._on_item_double_clicked(curr)
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
        dropped_paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        if dropped_paths:
            self.files_dropped.emit(dropped_paths)
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
