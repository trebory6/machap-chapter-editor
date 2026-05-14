from PySide6.QtCore import QPointF, Signal, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class ChapterTimeline(QWidget):
    seekRequested = Signal(float)
    """Emitted when the user should seek the playhead (click or scrub)."""
    scrubbingChanged = Signal(bool)
    """True when a drag-scrub begins; False on release (if a scrub occurred)."""

    _drag_threshold_px = 4

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(20)
        self.setMaximumHeight(24)
        self.setMouseTracking(True)

        self.chapter_times = []
        self.video_duration = 1
        self.playhead_time = 0

        self._scrub_active = False
        self._press_pos: QPointF | None = None

    def set_chapters(self, chapter_times, video_duration):
        """chapter_times: list of floats (in seconds)"""
        self.chapter_times = chapter_times
        self.video_duration = max(video_duration, 1)
        self.update()

    def _time_at_x(self, x: float) -> float:
        w = self.width()
        if w <= 0 or not self.video_duration:
            return 0.0
        rel = max(0.0, min(1.0, x / w))
        return rel * self.video_duration

    def _emit_seek_for_event(self, event) -> None:
        seek_time = self._time_at_x(event.position().x())
        self.seekRequested.emit(seek_time)

    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()
        height = self.height()

        painter.fillRect(event.rect(), QColor(40, 0, 0))  # Dark red background

        # chapter markers
        pen = QPen(QColor(255, 100, 100))
        pen.setWidth(2)
        painter.setPen(pen)

        for chapter in self.chapter_times:
            x = int((chapter / self.video_duration) * width)
            x = max(0, min(x, width - 1))
            painter.drawLine(x, 0, x, height)

        # Playhead
        playhead_x = int((self.playhead_time / self.video_duration) * width)
        playhead_x = max(0, min(playhead_x, width - 1))
        pen = QPen(QColor(0, 255, 255))  # Cyan
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(playhead_x, 0, playhead_x, height)

        pen = QPen(QColor(200, 200, 200, 100))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(0, height - 1, width, height - 1)

    def sizeHint(self):
        return self.parent().size() if self.parent() else super().sizeHint()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        if not self.video_duration or self.width() <= 0:
            return

        self._press_pos = QPointF(event.position())
        self._scrub_active = False
        self._emit_seek_for_event(event)

    def mouseMoveEvent(self, event):
        if not self.video_duration or self.width() <= 0:
            return super().mouseMoveEvent(event)

        if event.buttons() & Qt.MouseButton.LeftButton:
            if self._press_pos is not None and not self._scrub_active:
                delta = event.position() - self._press_pos
                if delta.manhattanLength() >= self._drag_threshold_px:
                    self._scrub_active = True
                    self.scrubbingChanged.emit(True)
            if self._press_pos is not None:
                self._emit_seek_for_event(event)
                return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was = self._scrub_active
            self._press_pos = None
            self._scrub_active = False
            if was:
                self.scrubbingChanged.emit(False)
            return
        super().mouseReleaseEvent(event)

    def set_playhead_time(self, time_sec):
        self.playhead_time = min(max(time_sec, 0), self.video_duration)
        self.update()
