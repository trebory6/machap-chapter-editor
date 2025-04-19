from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QMessageBox
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import QUrl

from detector import detect_black_frames, format_timestamp

from timeline import ChapterTimeline

from PySide6.QtWidgets import QHBoxLayout  # Add to your imports at the top if not already

class ChapterEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MaChap Chapter Editor")

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.durationChanged.connect(self.store_video_duration)

        self.time_label = QLabel("00:00:00.000")

        self.timeline = ChapterTimeline()
        self.timeline.setFixedHeight(20)  # You can tweak this

        self.timeline.seekRequested.connect(self.seek_to_time)

        self.load_button = QPushButton("Load Video")
        self.detect_button = QPushButton("Detect Black Frames")
        self.result_label = QLabel("Results will appear here...")

        layout = QVBoxLayout()
        layout.addWidget(self.video_widget)
        layout.addWidget(self.timeline)

        self.load_button = QPushButton("Load Video")
        self.detect_button = QPushButton("Detect Black Frames")
        self.result_label = QLabel("Results will appear here...")

        self.play_pause_button = QPushButton("▶ Play")
        self.mute_button = QPushButton("🔇 Mute")
        self.next_frame_button = QPushButton("→ Frame")
        self.prev_frame_button = QPushButton("← Frame")

        # button definitions
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

        from PySide6.QtWidgets import QHBoxLayout  # you can move this to the top of the file
        nav_row = QHBoxLayout()
        nav_row.addWidget(self.play_pause_button)
        nav_row.addWidget(self.mute_button)
        nav_row.addWidget(self.prev_frame_button)
        nav_row.addWidget(self.next_frame_button)

        layout.addLayout(nav_row)

        layout.addWidget(self.time_label)
        layout.addWidget(self.load_button)
        layout.addWidget(self.detect_button)
        layout.addWidget(self.result_label)
        layout.addWidget(self.add_chapter_button)
        layout.addWidget(self.remove_chapter_button)
        layout.addWidget(self.export_chapters_button)

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
            QMessageBox.warning(self, "No video", "Please load a video first.")
            return

        black_frames = detect_black_frames(self.video_path)

        self.detected_chapters = [bf["black_start"] for bf in black_frames]

        if black_frames:
            summary = "\n".join(
                f"Start: {format_timestamp(bf['black_start'])}, Duration: {format_timestamp(bf['black_duration'])}"
                for bf in black_frames
            )


            duration_ms = self.media_player.duration()
            duration_sec = self.video_duration

            self.timeline.set_chapters(
                chapter_times=self.detected_chapters,
                video_duration=duration_sec
            )
        else:
            summary = "No black frames detected."

        self.result_label.setText(summary)

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

    def update_time_display(self, position_ms):
        seconds = position_ms / 1000.0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        self.time_label.setText(f"{h:02}:{m:02}:{s:02}.{ms:03}")

        self.timeline.set_playhead_time(seconds)

    def store_video_duration(self, duration_ms):
        self.video_duration = duration_ms / 1000.0 if duration_ms else 1
        self.timeline.video_duration = self.video_duration  # ✅ pass it to the timeline
        print(f"[DEBUG] Stored duration: {self.video_duration:.3f}s")


