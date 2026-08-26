"""
ToroidAMP - Playlist Data Model and Management Subsystem
Supports track queuing, reordering, progression, shuffle, repeat, and M3U/M3U8 load/save.
"""

from dataclasses import dataclass
import os
import random
from typing import Optional


@dataclass
class PlaylistItem:
    """Represents a single track entry in the current playlist queue."""
    filepath: str
    title: str
    duration: float = 0.0 # seconds (0.0 if unknown)

    @property
    def display_duration(self) -> str:
        if self.duration <= 0.0:
            return "--:--"
        mins = int(self.duration // 60)
        secs = int(self.duration % 60)
        return f"{mins:02d}:{secs:02d}"


class PlaylistManager:
    """
    Manages the current session playlist queue independent of decoders or playback state.
    """

    def __init__(self):
        self._items: list[PlaylistItem] = []
        self._current_index: int = -1
        self._shuffle: bool = False
        self._repeat: bool = False # Repeat all
        self._shuffle_order: list[int] = []

    @property
    def items(self) -> list[PlaylistItem]:
        return list(self._items)

    @property
    def current_index(self) -> int:
        return self._current_index

    @current_index.setter
    def current_index(self, index: int) -> None:
        if 0 <= index < len(self._items):
            self._current_index = index
        elif index == -1 or len(self._items) == 0:
            self._current_index = -1


    @property
    def current_item(self) -> Optional[PlaylistItem]:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return None

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @shuffle.setter
    def shuffle(self, enabled: bool) -> None:
        self._shuffle = enabled
        self._rebuild_shuffle_order()

    @property
    def repeat(self) -> bool:
        return self._repeat

    @repeat.setter
    def repeat(self, enabled: bool) -> None:
        self._repeat = enabled

    def __len__(self) -> int:
        return len(self._items)

    def _rebuild_shuffle_order(self) -> None:
        self._shuffle_order = list(range(len(self._items)))
        if self._shuffle:
            random.shuffle(self._shuffle_order)

    def sanitize(self) -> list[str]:
        """
        Validates all current entries in the playlist.
        Removes any files that no longer exist on disk.
        Returns the list of removed dead filepaths.
        """
        valid_items = []
        removed_paths = []
        for item in self._items:
            if os.path.isfile(item.filepath):
                valid_items.append(item)
            else:
                removed_paths.append(item.filepath)

        self._items = valid_items
        if len(self._items) == 0:
            self._current_index = -1
        elif self._current_index >= len(self._items):
            self._current_index = 0

        self._rebuild_shuffle_order()
        return removed_paths

    def add_file(self, filepath: str, title: str | None = None, duration: float = 0.0) -> PlaylistItem:

        """Adds a single track to the playlist."""
        norm_path = os.path.abspath(filepath)
        if not title:
            title = os.path.splitext(os.path.basename(filepath))[0]
        item = PlaylistItem(filepath=norm_path, title=title, duration=duration)
        self._items.append(item)
        self._rebuild_shuffle_order()
        if self._current_index == -1:
            self._current_index = 0
        return item

    def add_files(self, filepaths: list[str]) -> list[PlaylistItem]:
        """Adds multiple tracks to the playlist."""
        added = []
        for fp in filepaths:
            if os.path.isfile(fp):
                added.append(self.add_file(fp))
        return added

    def remove_at(self, index: int) -> None:
        """Removes an item at the specified index."""
        if 0 <= index < len(self._items):
            del self._items[index]
            if len(self._items) == 0:
                self._current_index = -1
            elif self._current_index >= len(self._items):
                self._current_index = len(self._items) - 1
            elif index < self._current_index:
                self._current_index -= 1
            self._rebuild_shuffle_order()

    def clear(self) -> None:
        """Clears all entries from the playlist."""
        self._items.clear()
        self._current_index = -1
        self._shuffle_order.clear()

    def move_item(self, from_index: int, to_index: int) -> None:
        """Reorders an item from from_index to to_index."""
        if 0 <= from_index < len(self._items) and 0 <= to_index < len(self._items):
            item = self._items.pop(from_index)
            self._items.insert(to_index, item)
            if self._current_index == from_index:
                self._current_index = to_index
            elif from_index < self._current_index <= to_index:
                self._current_index -= 1
            elif to_index <= self._current_index < from_index:
                self._current_index += 1
            self._rebuild_shuffle_order()

    def get_next_index(self) -> Optional[int]:
        """Calculates the next track index taking into account shuffle and repeat."""
        if len(self._items) == 0:
            return None

        if self._shuffle and len(self._shuffle_order) == len(self._items):
            try:
                curr_pos = self._shuffle_order.index(self._current_index)
                if curr_pos + 1 < len(self._shuffle_order):
                    return self._shuffle_order[curr_pos + 1]
                elif self._repeat:
                    return self._shuffle_order[0]
                else:
                    return None
            except ValueError:
                return 0

        # Normal sequential progression
        next_idx = self._current_index + 1
        if next_idx < len(self._items):
            return next_idx
        elif self._repeat:
            return 0
        return None

    def get_previous_index(self) -> Optional[int]:
        """Calculates the previous track index."""
        if len(self._items) == 0:
            return None

        if self._shuffle and len(self._shuffle_order) == len(self._items):
            try:
                curr_pos = self._shuffle_order.index(self._current_index)
                if curr_pos > 0:
                    return self._shuffle_order[curr_pos - 1]
                elif self._repeat:
                    return self._shuffle_order[-1]
                else:
                    return self._shuffle_order[0]
            except ValueError:
                return 0

        prev_idx = self._current_index - 1
        if prev_idx >= 0:
            return prev_idx
        elif self._repeat:
            return len(self._items) - 1
        return 0

    def load_m3u(self, m3u_path: str) -> list[PlaylistItem]:
        """Parses an M3U or M3U8 playlist file and appends items."""
        if not os.path.exists(m3u_path):
            raise FileNotFoundError(f"Playlist file not found: {m3u_path}")

        base_dir = os.path.dirname(os.path.abspath(m3u_path))
        loaded_items = []

        with open(m3u_path, "r", encoding="utf-8", errors="ignore") as f:
            pending_title = None
            pending_duration = 0.0

            for line in f:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("#EXTINF:"):
                    # Format: #EXTINF:seconds,Title
                    info = line[8:]
                    parts = info.split(",", 1)
                    try:
                        pending_duration = float(parts[0].strip())
                    except ValueError:
                        pending_duration = 0.0
                    if len(parts) > 1:
                        pending_title = parts[1].strip()
                elif not line.startswith("#"):
                    # File path (relative or absolute)
                    resolved_path = line if os.path.isabs(line) else os.path.normpath(os.path.join(base_dir, line))
                    if os.path.exists(resolved_path):
                        item = self.add_file(resolved_path, title=pending_title, duration=pending_duration)
                        loaded_items.append(item)
                    pending_title = None
                    pending_duration = 0.0

        return loaded_items

    def save_m3u(self, m3u_path: str) -> None:
        """Saves current playlist items as standard extended M3U8 format."""
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for item in self._items:
                dur_int = int(item.duration)
                f.write(f"#EXTINF:{dur_int},{item.title}\n")
                f.write(f"{item.filepath}\n")
