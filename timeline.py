from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, Signal

class ChapterTimeline(QWidget):
    seekRequested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)

        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(30)
        self.setMaximumHeight(30)

        self.chapter_times = []
        self.video_duration = 1
        self.playhead_time = 0

    def set_chapters(self, chapter_times, video_duration):
        """chapter_times: list of floats (in seconds)"""
        self.chapter_times = chapter_times
        self.video_duration = max(video_duration, 1)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()
        height = self.height()

        print(f"[DEBUG] Timeline width: {width}px, duration: {self.video_duration}s")

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
        if not self.video_duration:
            return

        click_x = event.position().x()
        relative = click_x / self.width()
        seek_time = relative * self.video_duration
        self.seekRequested.emit(seek_time)

    def set_playhead_time(self, time_sec):
        self.playhead_time = min(max(time_sec, 0), self.video_duration)
        self.update()

