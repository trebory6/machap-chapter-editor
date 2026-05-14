from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from blackdetect_worker import EditorBlackdetectWorker, format_eta
from detector import BlackdetectError
from export_utils import (
    RemuxError,
    get_media_duration_seconds,
    normalize_export_format,
    remux_video_with_chapters,
    write_ffmpeg_chapter_file,
    write_mkvmerge_simple_chapters,
)
from scan_settings import ScanSettingsDialog
from time_windows import DEFAULT_SCAN_WINDOW_LIST_TEXT
from timeline import ChapterTimeline


class ChapterListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor = parent

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
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
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(obj, event)

        editor = self.editor
        if not editor:
            return False

        from PySide6.QtWidgets import QApplication

        if QApplication.activeWindow() is not editor:
            return False

        key = event.key()
        if key == Qt.Key.Key_Space:
            editor.toggle_play_pause()
            return True
        if key == Qt.Key.Key_M:
            editor.toggle_mute()
            return True
        if key == Qt.Key.Key_Right:
            editor.step_forward()
            return True
        if key == Qt.Key.Key_Left:
            editor.step_backward()
            return True
        if key == Qt.Key.Key_A:
            editor.add_chapter_at_current_time()
            return True

        return False


class ChapterEditor(QWidget):
    # Default frame step (~24 fps) until we read real frame rate from the player.
    _default_fps = 24.0

    def __init__(self):
        super().__init__()
        self.scan_settings = {
            "min_black_seconds": 0.4,
            "ratio_black_pixels": 0.98,
            "black_pixel_threshold": 0.08,
            "window_list": DEFAULT_SCAN_WINDOW_LIST_TEXT,
            "export_format": "mp4",
            "max_analysis_width": 854,
            "use_hwaccel": False,
            "parallel_scan_jobs": 4,
        }
        self._was_playing_before_scrub = False

        self.setWindowTitle("MaChap Chapter Editor")
        self.queue_window = None
        self._scan_worker: EditorBlackdetectWorker | None = None
        self._scan_dialog: QProgressDialog | None = None
        self._scan_elapsed: QElapsedTimer | None = None

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.video_widget.setFixedWidth(800)
        self.video_widget.setFixedHeight(450)
        size_policy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
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
        self.timeline.scrubbingChanged.connect(self._on_timeline_scrubbing)

        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()

        left_layout.addWidget(self.video_widget)
        left_layout.addWidget(self.timeline)

        self.load_button = QPushButton("Load Video")
        self.detect_button = QPushButton("Detect Black Frames")
        self.settings_button = QPushButton("Scan Settings")
        self.settings_button.clicked.connect(self.open_scan_settings)

        left_layout.addSpacing(5)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
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

        self.load_button.clicked.connect(self.load_video)
        self.detect_button.clicked.connect(self.detect_chapters)
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.next_frame_button.clicked.connect(self.step_forward)
        self.prev_frame_button.clicked.connect(self.step_backward)

        self.add_chapter_button = QPushButton("➕ Add Chapter Here")
        self.add_chapter_button.clicked.connect(self.add_chapter_at_current_time)

        self.export_file_button = QPushButton("📤 Export File")
        self.export_file_button.clicked.connect(self.export_loaded_media_with_chapters)

        self.export_chapters_button = QPushButton("💾 Export Chapters")
        self.export_chapters_button.clicked.connect(self.export_chapters_to_file)

        self.remove_chapter_button = QPushButton("🗑 Remove Chapter")
        self.remove_chapter_button.clicked.connect(self.remove_chapter_near_current_time)

        nav_row = QHBoxLayout()
        nav_row.addWidget(self.play_pause_button)
        nav_row.addWidget(self.mute_button)
        nav_row.addWidget(self.prev_frame_button)
        nav_row.addWidget(self.next_frame_button)

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
        left_layout.addWidget(self.export_file_button)
        left_layout.addWidget(self.export_chapters_button)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(self.chapter_list)

        self.setLayout(main_layout)

        self.video_path = None
        self.video_duration = 1.0
        self.manual_chapters: list[float] = []
        self.detected_chapters: list[float] = []

        self.media_player.positionChanged.connect(self.update_time_display)

    def _frame_step_ms(self) -> int:
        meta = self.media_player.metaData()
        rate = None
        if meta is not None:
            rate = meta.value(QMediaMetaData.Key.VideoFrameRate)
        try:
            if rate is not None and float(rate) > 0.1:
                return max(1, int(round(1000.0 / float(rate))))
        except (TypeError, ValueError):
            pass
        return max(1, int(round(1000.0 / self._default_fps)))

    def load_video(self, path_override: str | None = None, *, reset_chapters: bool = True) -> None:
        if path_override:
            file_path = path_override
        else:
            file_path, _ = QFileDialog.getOpenFileName(self, "Select Video")
        if not file_path:
            return

        self.video_path = file_path
        self.media_player.setSource(QUrl.fromLocalFile(file_path))

        if reset_chapters:
            self.manual_chapters = []
            self.detected_chapters = []
            self.timeline.set_chapters([], self.video_duration)
            self.update_chapter_list()
            self.media_player.play()
        else:
            self.media_player.pause()

    def load_from_queue(self, path: str, chapters: list[float]) -> None:
        self.load_video(path_override=path, reset_chapters=False)
        self.detected_chapters = list(chapters)
        self.manual_chapters = []
        self.timeline.set_chapters(
            sorted(set(self.detected_chapters + self.manual_chapters)),
            self.video_duration,
        )
        self.update_chapter_list()

    def detect_chapters(self) -> None:
        if not self.video_path:
            QMessageBox.information(self, "No video", "Load a video file first.")
            return

        if self._scan_worker is not None and self._scan_worker.isRunning():
            return

        self._scan_dialog = QProgressDialog(self)
        self._scan_dialog.setWindowTitle("Detecting black frames")
        self._scan_dialog.setCancelButtonText("Cancel")
        self._scan_dialog.setMinimumDuration(0)
        self._scan_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._scan_dialog.setAutoClose(False)
        self._scan_dialog.setAutoReset(False)

        duration = get_media_duration_seconds(self.video_path) or 0.0
        if duration > 0:
            self._scan_dialog.setRange(0, 1000)
            self._scan_dialog.setValue(0)
        else:
            self._scan_dialog.setRange(0, 0)

        self._scan_elapsed = QElapsedTimer()
        self._scan_elapsed.start()
        self._scan_dialog.setLabelText("Starting FFmpeg…")

        self._scan_worker = EditorBlackdetectWorker(self.video_path, self.scan_settings.copy())
        self._scan_worker.progress_ratio.connect(self._on_editor_scan_progress)
        self._scan_worker.finished_ok.connect(self._on_editor_scan_finished_ok)
        self._scan_worker.failed.connect(self._on_editor_scan_failed)
        self._scan_worker.canceled.connect(self._on_editor_scan_canceled)
        self._scan_worker.finished.connect(self._on_editor_scan_thread_finished)
        self._scan_dialog.canceled.connect(self._scan_worker.cancel)

        self.detect_button.setEnabled(False)
        self._scan_dialog.show()
        self._scan_worker.start()

    def _on_editor_scan_progress(self, ratio: float) -> None:
        if self._scan_dialog is None or self._scan_elapsed is None:
            return
        elapsed = self._scan_elapsed.elapsed() / 1000.0
        if self._scan_dialog.maximum() > 0:
            self._scan_dialog.setValue(int(min(1.0, ratio) * 1000))
            eta: float | None
            if ratio >= 0.12:
                eta = elapsed * (1.0 / max(ratio, 0.02) - 1.0)
            else:
                eta = None
            self._scan_dialog.setLabelText(
                "Scanning for black frames…\n"
                f"About {min(100.0, ratio * 100):.0f}% of runtime — ETA ~ {format_eta(eta)}\n"
                f"Elapsed {format_eta(elapsed)}"
            )
        else:
            self._scan_dialog.setLabelText(
                "Scanning (duration unknown — ETA unavailable)\n"
                f"Elapsed {format_eta(elapsed)}"
            )

    def _on_editor_scan_finished_ok(self, chapters: list[float]) -> None:
        self.detected_chapters = chapters
        self.timeline.set_chapters(
            sorted(set(self.detected_chapters + self.manual_chapters)),
            self.video_duration,
        )
        self.update_chapter_list()
        if not chapters:
            QMessageBox.information(
                self,
                "No black segments",
                "No black segments matched the current settings.",
            )

    def _on_editor_scan_failed(self, err: object) -> None:
        if isinstance(err, BlackdetectError):
            QMessageBox.critical(
                self,
                "Detection failed",
                f"{err}\n\n{(err.stderr or '')[-3000:]}",
            )
        else:
            QMessageBox.critical(self, "Detection failed", str(err))

    def _on_editor_scan_canceled(self) -> None:
        pass

    def _on_editor_scan_thread_finished(self) -> None:
        self.detect_button.setEnabled(True)
        if self._scan_dialog is not None:
            self._scan_dialog.close()
            self._scan_dialog.deleteLater()
            self._scan_dialog = None
        self._scan_elapsed = None
        self._scan_worker = None

    def _on_timeline_scrubbing(self, active: bool) -> None:
        if active:
            self._was_playing_before_scrub = (
                self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            )
            self.media_player.pause()
            self.play_pause_button.setText("▶ Play")
        elif self._was_playing_before_scrub:
            self.media_player.play()
            self.play_pause_button.setText("⏸ Pause")

    def seek_to_time(self, seconds: float) -> None:
        self.media_player.setPosition(int(seconds * 1000))

    def toggle_play_pause(self) -> None:
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_pause_button.setText("▶ Play")
        else:
            self.media_player.play()
            self.play_pause_button.setText("⏸ Pause")

    def toggle_mute(self) -> None:
        is_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(not is_muted)
        self.mute_button.setText("🔊 Unmute" if is_muted else "🔇 Mute")

    def add_chapter_at_current_time(self) -> None:
        position_ms = self.media_player.position()
        position_sec = position_ms / 1000.0

        if position_sec in self.manual_chapters:
            return

        self.manual_chapters.append(position_sec)

        all_chapters = sorted(set(self.manual_chapters + self.detected_chapters))

        duration_ms = self.media_player.duration()
        duration_sec = duration_ms / 1000.0 if duration_ms else self.video_duration

        self.timeline.set_chapters(
            chapter_times=all_chapters,
            video_duration=duration_sec,
        )
        self.update_chapter_list()

    def export_loaded_media_with_chapters(self) -> None:
        import os

        if not self.video_path:
            QMessageBox.information(self, "No video", "Load a video file first.")
            return

        all_chapters = sorted(set(self.manual_chapters + self.detected_chapters))
        if not all_chapters:
            QMessageBox.information(
                self,
                "No Chapters",
                "Add or detect at least one chapter before exporting the file.",
            )
            return

        fmt = normalize_export_format(self.scan_settings.get("export_format", "mp4"))
        if fmt in ("txt", "mkvmerge_txt"):
            QMessageBox.information(
                self,
                "Video export",
                "Scan Settings export format is set to a chapter sidecar only. "
                "Choose MP4 or MKV under Export format to remux a video with embedded chapters, "
                "or use Export Chapters to save a metadata text file.",
            )
            return

        ext = ".mp4" if fmt == "mp4" else ".mkv"
        base = os.path.splitext(os.path.basename(self.video_path))[0]
        default_name = f"{base}_chaptered{ext}"
        filter_str = (
            "MP4 video (*.mp4);;All files (*)"
            if fmt == "mp4"
            else "Matroska video (*.mkv);;All files (*)"
        )

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export video with chapters",
            default_name,
            filter_str,
        )
        if not path:
            return

        if not os.path.splitext(path)[1]:
            path = path + ext

        self.setEnabled(False)
        try:
            remux_video_with_chapters(self.video_path, all_chapters, path)
        except RemuxError as e:
            QMessageBox.critical(
                self,
                "FFmpeg failed",
                (e.stderr or str(e))[-3000:],
            )
            return
        except OSError as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        finally:
            self.setEnabled(True)

        QMessageBox.information(self, "Export complete", f"Video saved to:\n{path}")

    def export_chapters_to_file(self) -> None:
        all_chapters = sorted(set(self.manual_chapters + self.detected_chapters))

        if not all_chapters:
            QMessageBox.information(self, "No Chapters", "No chapters to export.")
            return

        fmt = normalize_export_format(self.scan_settings.get("export_format", "mp4"))
        base = "chapters"
        if self.video_path:
            import os

            base = os.path.splitext(os.path.basename(self.video_path))[0] + "_chapters"

        if fmt == "mkvmerge_txt":
            default_name = f"{base}_mkvmerge.txt"
            filter_str = "MKVmerge chapters (*.txt);;All files (*)"
        else:
            default_name = f"{base}_ffmeta.txt"
            filter_str = "FFmpeg metadata (*.txt);;All files (*)"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export chapters",
            default_name,
            filter_str,
        )
        if not path:
            return

        duration_sec = self.video_duration if self.video_duration > 0 else None
        try:
            if fmt == "mkvmerge_txt":
                write_mkvmerge_simple_chapters(all_chapters, path)
            else:
                write_ffmpeg_chapter_file(all_chapters, path, duration_sec=duration_sec)
            QMessageBox.information(self, "Export Complete", f"Chapters saved to:\n{path}")
        except OSError as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def remove_chapter_near_current_time(self) -> None:
        position = self.media_player.position() / 1000.0
        tolerance = 10.0

        all_chapters = self.manual_chapters + self.detected_chapters
        if not all_chapters:
            QMessageBox.information(self, "No Chapters", "No chapters to remove.")
            return

        closest = min(all_chapters, key=lambda t: abs(t - position))
        if abs(closest - position) > tolerance:
            QMessageBox.information(
                self,
                "No Nearby Chapter",
                f"No chapter within {tolerance:.1f} seconds.",
            )
            return

        if closest in self.detected_chapters:
            self.detected_chapters.remove(closest)

        if closest in self.manual_chapters:
            self.manual_chapters.remove(closest)

        updated = sorted(set(self.manual_chapters + self.detected_chapters))
        duration_sec = self.media_player.duration() / 1000.0 or self.video_duration

        self.timeline.set_chapters(updated, duration_sec)
        self.update_chapter_list()

    def update_time_display(self, position_ms: int) -> None:
        seconds = position_ms / 1000.0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        self.current_time_label.setText(f"{h:02}:{m:02}:{s:02}.{ms:03}")
        self.timeline.set_playhead_time(seconds)

    def store_video_duration(self, duration_ms: int) -> None:
        self.video_duration = duration_ms / 1000.0 if duration_ms else 1.0
        self.timeline.video_duration = self.video_duration
        h = int(self.video_duration // 3600)
        m = int((self.video_duration % 3600) // 60)
        s = int(self.video_duration % 60)
        ms = int((self.video_duration - int(self.video_duration)) * 1000)
        self.total_time_label.setText(f"{h:02}:{m:02}:{s:02}.{ms:03}")

        combined = sorted(set(self.manual_chapters + self.detected_chapters))
        if combined:
            self.timeline.set_chapters(combined, self.video_duration)

    def jump_to_chapter_from_list(self, item: QListWidgetItem) -> None:
        try:
            timestamp = float(item.data(1000))
            self.media_player.setPosition(int(timestamp * 1000))
        except (TypeError, ValueError):
            pass

    def update_chapter_list(self) -> None:
        self.chapter_list.clear()
        all_chapters = sorted(set(self.manual_chapters + self.detected_chapters))

        for i, ts in enumerate(all_chapters, start=1):
            h = int(ts // 3600)
            m = int((ts % 3600) // 60)
            s = int(ts % 60)
            ms = int((ts - int(ts)) * 1000)

            label = f"{h:02}:{m:02}:{s:02}.{ms:03}"
            item = QListWidgetItem(f"Chapter {i}: {label}")
            item.setData(1000, ts)
            self.chapter_list.addItem(item)

    def delete_chapter_by_timestamp(self, ts: float) -> None:
        removed = False

        if ts in self.manual_chapters:
            self.manual_chapters.remove(ts)
            removed = True
        elif ts in self.detected_chapters:
            self.detected_chapters.remove(ts)
            removed = True

        if removed:
            all_chapters = sorted(set(self.manual_chapters + self.detected_chapters))
            self.timeline.set_chapters(all_chapters, self.video_duration)
            self.update_chapter_list()

    def step_forward(self) -> None:
        step = self._frame_step_ms()
        self.media_player.setPosition(self.media_player.position() + step)

    def step_backward(self) -> None:
        step = self._frame_step_ms()
        self.media_player.setPosition(max(0, self.media_player.position() - step))

    def open_queue_manager(self) -> None:
        from queue_manager import QueueManager

        if self.queue_window is None or not self.queue_window.isVisible():
            self.queue_window = QueueManager()
            self.queue_window.show()
        else:
            self.queue_window.raise_()
            self.queue_window.activateWindow()

    def open_scan_settings(self) -> None:
        dlg = ScanSettingsDialog(self, self.scan_settings)
        dlg.load_from(self.scan_settings)
        dlg.settingsApplied.connect(self.update_scan_settings)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def update_scan_settings(self, new_settings: dict) -> None:
        self.scan_settings = new_settings
