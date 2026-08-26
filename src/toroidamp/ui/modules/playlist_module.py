"""
ToroidAMP - Production Playlist Module
Provides interactive track list, drag-and-drop, add/remove,
reorder, clear, shuffle, repeat, and M3U/M3U8 load/save.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from .base import ModuleShell
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

    def __init__(self, manager: PlaylistManager, parent=None):
        super().__init__("// MODULE :: PLAYLIST", parent)
        self.manager = manager
        self.setFixedSize(270, 240)
        self.setAcceptDrops(True)

        # Playlist ListWidget
        self.list_widget = QListWidget(self)
        self.list_widget.setAcceptDrops(True)
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
        self.btn_add.setStyleSheet(btn_style)
        self.btn_add.clicked.connect(self._browse_add_files)
        b_layout.addWidget(self.btn_add)

        self.btn_del = QPushButton("-DEL", btn_bar)
        self.btn_del.setStyleSheet(btn_style)
        self.btn_del.clicked.connect(self._remove_selected)
        b_layout.addWidget(self.btn_del)

        self.btn_clear = QPushButton("CLR", btn_bar)
        self.btn_clear.setStyleSheet(btn_style)
        self.btn_clear.clicked.connect(self._clear_playlist)
        b_layout.addWidget(self.btn_clear)

        self.btn_shf = QPushButton("SHF", btn_bar)
        self.btn_shf.setCheckable(True)
        self.btn_shf.setStyleSheet(btn_style)
        self.btn_shf.clicked.connect(self._toggle_shuffle)
        b_layout.addWidget(self.btn_shf)

        self.btn_rep = QPushButton("REP", btn_bar)
        self.btn_rep.setCheckable(True)
        self.btn_rep.setStyleSheet(btn_style)
        self.btn_rep.clicked.connect(self._toggle_repeat)
        b_layout.addWidget(self.btn_rep)

        self.btn_m3u = QPushButton("M3U", btn_bar)
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
        self.queue_info.setStyleSheet("color: #4a5270; font-family: monospace; font-size: 9px;")
        f_layout.addWidget(self.queue_info)
        self.main_layout.addWidget(foot_bar)

    def refresh(self):
        """Refreshes the ListWidget to reflect current PlaylistManager state."""
        self.list_widget.clear()
        for idx, item in enumerate(self.manager.items):
            prefix = "▶ " if idx == self.manager.current_index else "  "
            list_item = QListWidgetItem(f"{prefix}[{idx+1:02d}] {item.title:<18} {item.display_duration}")
            self.list_widget.addItem(list_item)
        
        self.queue_info.setText(f"TOTAL: {len(self.manager)} TRACKS")
        if 0 <= self.manager.current_index < len(self.manager):
            self.list_widget.setCurrentRow(self.manager.current_index)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        row = self.list_widget.row(item)
        if row >= 0:
            self.manager.current_index = row
            self.refresh()
            self.track_double_clicked.emit(row)

    def _browse_add_files(self):
        filter_str = "Audio Files (*.mp3 *.ogg *.wav *.flac *.mod *.xm *.it *.s3m);;All Files (*.*)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Audio Tracks to Playlist", "", filter_str)
        if paths:
            self.manager.add_files(paths)
            self.refresh()

    def _remove_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.manager.remove_at(row)
            self.refresh()

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
        """Handles M3U loading or saving."""
        path, _ = QFileDialog.getSaveFileName(self, "Save Playlist as M3U8", "", "M3U8 Playlist (*.m3u8);;M3U Playlist (*.m3u)")
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
