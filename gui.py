from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QMessageBox
)
from queue_manager import QueueManager

from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import QUrl
from detector import detect_black_frames, format_timestamp
from timeline import ChapterTimeline
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtWidgets import QFrame

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import QObject, QEvent

from scan_settings import ScanSettingsDialog

from detector import detect_black_frames
# from scan_settings import parse_time_range_list

class ChapterListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor = parent

    def keyPressEvent(self, event):
        print("Key pressed:", event.key())
        if event.key() == Qt.Key_Delete:
            selected = self.currentItem()
            if selected:
                timestamp = selected.data(1000)
                self.editor.delete_chapter_by_timestamp(timestamp)
        else:
            super().keyPressEvent(event)

class KeyPressFilter(QObject):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            print("Global key press:", key)

            if key == Qt.Key_Space:
                self.editor.toggle_play_pause()
                return True
            elif key == Qt.Key_M:
                self.editor.toggle_mute()
                return True
            elif key == Qt.Key_Right:
                self.editor.step_forward()
                return True
            elif key == Qt.Key_Left:
                self.editor.step_backward()
                return True
            elif key == Qt.Key_A:
                self.editor.add_chapter_at_current_time()
                return True

        return super().eventFilter(obj, event)

class ChapterEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.scan_settings = {
            "min_black_seconds": 0.4,
            "ratio_black_pixels": 0.98,
            "black_pixel_threshold": 0.08,
            "window_list": "",
        }

        self.setWindowTitle("MaChap Chapter Editor")
        self.queue_window = None

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.video_widget.setFixedWidth(800)
        self.video_widget.setFixedHeight(450)
        size_policy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        size_policy.setHeightForWidth(True)
        self.video_widget.setSizePolicy(size_policy)

        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.durationChanged.connect(self.store_video_duration)

        self.current_time_label = QLabel("00:00:00.000")
        self.total_time_label = QLabel("00:00:00.000")



        self.current_time_label.setFixedHeight(20)
        self.total_time_label.setFixedHeight(20)

        self.time_bar = QHBoxLayout()
        self.time_bar.addWidget(self.current_time_label)
        self.time_bar.addStretch()
        self.time_bar.addWidget(self.total_time_label)

        self.timeline = ChapterTimeline()
        self.timeline.setFixedHeight(20)

        self.timeline.seekRequested.connect(self.seek_to_time)

        layout = QVBoxLayout()
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()

        # Queue Window
        self.queue_button = QPushButton("Open Queue Manager")
        self.queue_button.clicked.connect(self.open_queue_manager)
        self.queue_window = None

        left_layout.addWidget(self.video_widget)

        left_layout.addWidget(self.timeline)

        self.load_button = QPushButton("Load Video")
        self.detect_button = QPushButton("Detect Black Frames")
        self.settings_button = QPushButton("Scan Settings")
        self.settings_button.clicked.connect(self.open_scan_settings)
        left_layout.addSpacing(5)
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setLineWidth(1)
        divider.setMidLineWidth(1)
        divider.setFixedHeight(10)
        left_layout.addWidget(divider)

        self.play_pause_button = QPushButton("▶ Play")
        self.mute_button = QPushButton("🔇 Mute")
        self.next_frame_button = QPushButton("→ Frame")
        self.prev_frame_button = QPushButton("← Frame")

        self.chapter_list = ChapterListWidget(self)
        self.chapter_list.setFixedWidth(200)
        self.chapter_list.itemClicked.connect(self.jump_to_chapter_from_list)

        # Button signal connections
        self.load_button.clicked.connect(self.load_video)
        self.detect_button.clicked.connect(self.detect_chapters)
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.next_frame_button.clicked.connect(self.skip_next_frame)
        self.prev_frame_button.clicked.connect(self.skip_prev_frame)

        self.add_chapter_button = QPushButton("➕ Add Chapter Here")
        self.add_chapter_button.clicked.connect(self.add_chapter_at_current_time)

        self.export_chapters_button = QPushButton("💾 Export Chapters")
        self.export_chapters_button.clicked.connect(self.export_chapters_to_file)

        self.remove_chapter_button = QPushButton("🗑 Remove Chapter")
        self.remove_chapter_button.clicked.connect(self.remove_chapter_near_current_time)

        # Navigation row layout
        nav_row = QHBoxLayout()
        nav_row.addWidget(self.play_pause_button)
        nav_row.addWidget(self.mute_button)
        nav_row.addWidget(self.prev_frame_button)
        nav_row.addWidget(self.next_frame_button)

        # All widgets to left side layout
        left_layout.addLayout(nav_row)
        left_layout.addLayout(self.time_bar)
        left_layout.addWidget(self.load_button)

        self.queue_button = QPushButton("Open Queue Manager")
        self.queue_button.clicked.connect(self.open_queue_manager)
        left_layout.addWidget(self.queue_button)

        scan_row = QHBoxLayout()
        scan_row.addWidget(self.detect_button)
        scan_row.addWidget(self.settings_button)
        left_layout.addLayout(scan_row)

        left_layout.addWidget(self.add_chapter_button)
        left_layout.addWidget(self.remove_chapter_button)
        left_layout.addWidget(self.export_chapters_button)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(self.chapter_list)

        self.key_filter = KeyPressFilter(self)
        self.installEventFilter(self.key_filter)

        self.setLayout(main_layout)
        self.setLayout(layout)

        self.video_path = None

        self.manual_chapters = []

        self.media_player.positionChanged.connect(self.update_time_display)

    def load_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Video")
        if path:
            self.video_path = path
            self.media_player.setSource(QUrl.fromLocalFile(path))
            self.media_player.play()

    def detect_chapters(self):
        if not self.video_path:
            return

        print("🕵️ Detecting black frames for:", self.video_path)

        settings = self.scan_settings
        window_list = parse_time_range_list(settings.get("window_list", ""))

        black_frames = detect_black_frames(
            self.video_path,
            min_black_seconds=settings["min_black_seconds"],
            ratio_black_pixels=settings["ratio_black_pixels"],
            black_pixel_threshold=settings["black_pixel_threshold"],
            window_list=window_list
        )

        self.detected_chapters = [
            round(f["black_start"] + (f["black_duration"] / 2), 3)
            for f in black_frames
        ]
        self.timeline.set_chapters(self.detected_chapters + self.manual_chapters, self.video_duration)
        self.update_chapter_list()

        summary = "\n".join(
            f"Start: {format_timestamp(bf['black_start'])}, Duration: {format_timestamp(bf['black_duration'])}"
            for bf in black_frames
        )
        # self.results_label.setText(summary)

    def seek_to_time(self, seconds):
        self.media_player.setPosition(int(seconds * 1000))

    def skip_next_frame(self):
        current = self.media_player.position()
        self.media_player.setPosition(current + 42)

    def skip_prev_frame(self):
        current = self.media_player.position()
        self.media_player.setPosition(max(0, current - 42))

    def toggle_play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.play_pause_button.setText("▶ Play")
        else:
            self.media_player.play()
            self.play_pause_button.setText("⏸ Pause")

    def toggle_mute(self):
        is_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(not is_muted)
        self.mute_button.setText("🔊 Unmute" if is_muted else "🔇 Mute")

    def set_chapters(self, chapter_times, video_duration):
        self.chapter_times = chapter_times
        self.video_duration = video_duration if video_duration > 0 else 1
        self.update()

    def add_chapter_at_current_time(self):
        position_ms = self.media_player.position()
        position_sec = position_ms / 1000.0

        if position_sec in self.manual_chapters:
            return

        self.manual_chapters.append(position_sec)

        all_chapters = sorted(set(self.manual_chapters + getattr(self, "detected_chapters", [])))

        duration_ms = self.media_player.duration()
        duration_sec = duration_ms / 1000.0 if duration_ms else 1

        self.timeline.set_chapters(
            chapter_times=all_chapters,
            video_duration=duration_sec
        )
        self.update_chapter_list()

    def export_chapters_to_file(self):
        all_chapters = sorted(set(self.manual_chapters + getattr(self, "detected_chapters", [])))

        if not all_chapters:
            QMessageBox.information(self, "No Chapters", "No chapters to export.")
            return

        lines = []
        for i, timestamp in enumerate(all_chapters, start=1):
            h = int(timestamp // 3600)
            m = int((timestamp % 3600) // 60)
            s = int(timestamp % 60)
            ms = int((timestamp - int(timestamp)) * 1000)

            formatted = f"{h:02}:{m:02}:{s:02}.{ms:03}"
            lines.append(f"CHAPTER{i:02}={formatted}")
            lines.append(f"CHAPTER{i:02}NAME=Chapter {i}")

        try:
            with open("chapters.txt", "w") as f:
                f.write("\n".join(lines))

            QMessageBox.information(self, "Export Complete", "Chapters exported to 'chapters.txt'.")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def remove_chapter_near_current_time(self):
        position = self.media_player.position() / 1000.0  # current position in seconds
        tolerance = 10.0  # seconds

        all_chapters = self.manual_chapters + getattr(self, "detected_chapters", [])
        if not all_chapters:
            QMessageBox.information(self, "No Chapters", "No chapters to remove.")
            return

        closest = min(all_chapters, key=lambda t: abs(t - position))
        if abs(closest - position) > tolerance:
            QMessageBox.information(self, "No Nearby Chapter", f"No chapter within {tolerance:.1f} seconds.")
            return

        if hasattr(self, "detected_chapters") and closest in self.detected_chapters:
            self.detected_chapters.remove(closest)

        if closest in self.manual_chapters:
            self.manual_chapters.remove(closest)

        updated = sorted(set(self.manual_chapters + getattr(self, "detected_chapters", [])))
        duration_sec = self.media_player.duration() / 1000.0 or 1

        self.timeline.set_chapters(updated, duration_sec)

        self.update_chapter_list()

    def update_time_display(self, position_ms):
        seconds = position_ms / 1000.0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        self.current_time_label.setText(f"{h:02}:{m:02}:{s:02}.{ms:03}")

        self.timeline.set_playhead_time(seconds)

    def store_video_duration(self, duration_ms):
        self.video_duration = duration_ms / 1000.0 if duration_ms else 1
        self.timeline.video_duration = self.video_duration
        print(f"[DEBUG] Stored duration: {self.video_duration:.3f}s")
        h = int(self.video_duration // 3600)
        m = int((self.video_duration % 3600) // 60)
        s = int(self.video_duration % 60)
        ms = int((self.video_duration - int(self.video_duration)) * 1000)
        self.total_time_label.setText(f"{h:02}:{m:02}:{s:02}.{ms:03}")

    def jump_to_chapter_from_list(self, item):
        try:
            timestamp = float(item.data(1000))
            self.media_player.setPosition(int(timestamp * 1000))
        except Exception as e:
            print(f"Error seeking to chapter: {e}")

    def update_chapter_list(self):
        self.chapter_list.clear()
        all_chapters = sorted(set(self.manual_chapters + getattr(self, "detected_chapters", [])))

        for i, ts in enumerate(all_chapters, start=1):
            h = int(ts // 3600)
            m = int((ts % 3600) // 60)
            s = int(ts % 60)
            ms = int((ts - int(ts)) * 1000)

            label = f"{h:02}:{m:02}:{s:02}.{ms:03}"
            item = QListWidgetItem(f"Chapter {i}: {label}")
            item.setData(1000, ts)
            self.chapter_list.addItem(item)

    def delete_chapter_by_timestamp(self, ts):
        removed = False

        if ts in self.manual_chapters:
            self.manual_chapters.remove(ts)
            removed = True
        elif hasattr(self, "detected_chapters") and ts in self.detected_chapters:
            self.detected_chapters.remove(ts)
            removed = True

        if removed:
            all_chapters = sorted(set(self.manual_chapters + getattr(self, "detected_chapters", [])))
            self.timeline.set_chapters(all_chapters, self.video_duration)
            self.update_chapter_list()

    def keyPressEvent(self, event):
        key = event.key()
        print("Main window key press:", key)

        if key == Qt.Key_Space:
            self.toggle_play_pause()
        elif key == Qt.Key_M:
            self.toggle_mute()
        elif key == Qt.Key_Right:
            self.step_forward()
        elif key == Qt.Key_Left:
            self.step_backward()
        else:
            super().keyPressEvent(event)

    def step_forward(self):
        self.media_player.setPosition(self.media_player.position() + 1000 // 24)

    def step_backward(self):
        self.media_player.setPosition(self.media_player.position() - 1000 // 24)

    def open_queue_manager(self):
        if self.queue_window is None or not self.queue_window.isVisible():
            from queue_manager import QueueManager
            self.queue_window = QueueManager()
            self.queue_window.show()
        else:
            self.queue_window.raise_()
            self.queue_window.activateWindow()

    def open_scan_settings(self):
        if not hasattr(self, "_scan_settings_dialog") or self._scan_settings_dialog is None:
            self._scan_settings_dialog = ScanSettingsDialog(self, getattr(self, 'scan_settings', None))
            self._scan_settings_dialog.settingsApplied.connect(self.update_scan_settings)
        self._scan_settings_dialog.show()
        self._scan_settings_dialog.raise_()
        self._scan_settings_dialog.activateWindow()

    def update_scan_settings(self, new_settings):
        self.scan_settings = new_settings
        print("🔧 Updated scan settings:", self.scan_settings)

    def load_from_queue(self, path, chapters):
        self.load_video(path_override=path)
        self.detected_chapters = chapters
        self.manual_chapters = []
        self.timeline.set_chapters(chapters, self.video_duration)
        self.update_chapter_list()

    def load_video(self, path_override=None):
        file_path = path_override or QFileDialog.getOpenFileName(self, "Select Video")[0]
        if not file_path:
            return

        self.video_path = file_path
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        self.media_player.pause()

def parse_time_range_list(time_string):
    def hms_to_seconds(t):
        parts = t.strip().split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid time format: '{t}'")
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds

    ranges = []
    for pair in time_string.split(","):
        if "-" not in pair:
            continue
        start_str, end_str = pair.split("-")
        try:
            start = hms_to_seconds(start_str)
            end = hms_to_seconds(end_str)
            if start < end:
                ranges.append((start, end))
        except Exception as e:
            print(f"⚠️ Failed to parse time range '{pair}': {e}")
    return ranges

