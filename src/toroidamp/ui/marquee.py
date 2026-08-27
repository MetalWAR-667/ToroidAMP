"""
ToroidAMP - Marquee Label
Ping-pong horizontal scroll for titles that overflow their available width.

Pure information UX (title readability) — not audio-reactive, not a
visualizer. A title that fits stays still; a title that doesn't shows you
the rest, calmly.
"""
from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPainter, QFontMetrics


class MarqueeLabel(QLabel):
    """
    Drop-in QLabel replacement. Use `set_marquee_text()` instead of
    `setText()` — it owns overflow detection, ping-pong scroll state, and
    resets to the beginning whenever the text actually changes.

    Marquee state machine (only active while the text overflows):
        PAUSE_START -> SCROLL_FORWARD -> PAUSE_END -> SCROLL_BACKWARD -> repeat
    """

    PAUSE_MS = 1200            # dwell at each endpoint — readable, not a crawl
    SCROLL_SPEED_PX_S = 55.0   # moderate, calm horizontal speed
    TICK_MS = 30                # ~33fps animation tick, only while scrolling

    # Travel goes a bit past the point where the last character merely
    # touches the viewport edge — otherwise a title that only just overflows
    # produces a barely-perceptible wiggle instead of a readable scroll.
    # This is extra *travel*, not extra *reveal*: it opens a small gap of
    # blank space after the text at the far end, which is exactly what
    # makes "the end is now clearly exposed" perceptible.
    END_REVEAL_MARGIN_PX = 28

    _STATIC = "static"
    _PAUSE_START = "pause_start"
    _SCROLL_FWD = "scroll_fwd"
    _PAUSE_END = "pause_end"
    _SCROLL_BACK = "scroll_back"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._offset = 0.0
        self._overflow_px = 0   # raw overflow — text_width - visible_width; gates activation
        self._max_offset = 0    # actual scroll travel target — overflow + end_reveal_margin
        self._state = self._STATIC

        # A plain QLabel's minimumSizeHint equals its full, unwrapped text
        # width — for a long title that can be hundreds of pixels wider than
        # the label's actual available space, which fights (and can distort)
        # a QHBoxLayout's split against sibling widgets, and is exactly
        # backwards for a widget whose entire point is to occupy whatever
        # leftover space the layout gives it. Ignored decouples the two:
        # the layout is always free to size this label by its stretch factor
        # alone, regardless of how long the current title is.
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(40, fm.height() + 4)

    def minimumSizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(20, fm.height() + 4)

    def set_marquee_text(self, text: str):
        """Sets the canonical title text. Resets scroll to the beginning only when the text actually changes."""
        if text == self._full_text:
            return
        self._full_text = text
        # Keep QLabel's own .text() accurate for any other code/tests that
        # read it — paintEvent is fully overridden below, so this never
        # affects what's actually drawn on screen.
        super().setText(text)
        self._offset = 0.0
        # Force a full reset through _recompute_overflow — a change mid-scroll
        # must return to the readable start-pause, not continue whatever
        # forward/backward motion the previous title was in.
        self._state = self._STATIC
        self._timer.stop()
        self._recompute_overflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recompute_overflow()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # Re-measure against the current width rather than trusting whatever
        # was computed earlier: text can be set (via set_marquee_text) before
        # the surrounding layout has settled on this label's final width —
        # e.g. the very first track title arriving right after startup, or a
        # scale switch revealing a page that was hidden mid-layout. Since
        # set_marquee_text() only recomputes on an actual text *change*, a
        # stale "fits" verdict from that race would otherwise never be
        # corrected for as long as the title stays the same.
        self._recompute_overflow()
        if self._overflow_px > 0 and not self._timer.isActive():
            interval = self.TICK_MS if self._state in (self._SCROLL_FWD, self._SCROLL_BACK) else self.PAUSE_MS
            self._timer.start(interval)

    def _recompute_overflow(self):
        """
        Reevaluates overflow against the current font metrics and actual
        visible widget width. `max_offset = text_width - visible_width +
        end_reveal_margin` — the extra margin is travel, not reveal: the
        text's last character already touches the viewport edge at
        `text_width - visible_width`; scrolling a bit further than that is
        what makes the motion — and the fact that the end was reached —
        actually perceptible.
        """
        fm = QFontMetrics(self.font())
        text_w = fm.horizontalAdvance(self._full_text)
        visible_width = max(0, self.width())
        overflow = max(0, text_w - visible_width)

        self._overflow_px = overflow
        self._max_offset = overflow + self.END_REVEAL_MARGIN_PX if overflow > 0 else 0
        self._offset = min(self._offset, float(self._max_offset))

        if overflow <= 0:
            self._state = self._STATIC
            self._timer.stop()
            self._offset = 0.0
        elif self._state == self._STATIC:
            self._state = self._PAUSE_START
            if self.isVisible():
                self._timer.start(self.PAUSE_MS)
        self.update()

    def _tick(self):
        if self._state == self._PAUSE_START:
            self._state = self._SCROLL_FWD
            self._timer.start(self.TICK_MS)
        elif self._state == self._SCROLL_FWD:
            self._offset += self.SCROLL_SPEED_PX_S * (self.TICK_MS / 1000.0)
            if self._offset >= self._max_offset:
                self._offset = float(self._max_offset)
                self._state = self._PAUSE_END
                self._timer.start(self.PAUSE_MS)
        elif self._state == self._PAUSE_END:
            self._state = self._SCROLL_BACK
            self._timer.start(self.TICK_MS)
        elif self._state == self._SCROLL_BACK:
            self._offset -= self.SCROLL_SPEED_PX_S * (self.TICK_MS / 1000.0)
            if self._offset <= 0:
                self._offset = 0.0
                self._state = self._PAUSE_START
                self._timer.start(self.PAUSE_MS)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(self.foregroundRole()))
        fm = painter.fontMetrics()
        y = (self.height() + fm.ascent() - fm.descent()) // 2

        if self._overflow_px > 0:
            x = -int(self._offset)
        elif self.alignment() & Qt.AlignRight:
            x = max(0, self.width() - fm.horizontalAdvance(self._full_text))
        else:
            x = 0

        painter.drawText(x, y, self._full_text)
        painter.end()
