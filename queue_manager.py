import os
import subprocess
from typing import Any

from PySide6.QtCore import QElapsedTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blackdetect_worker import BatchBlackdetectWorker, format_eta
from export_utils import (
    get_bitrates,
    get_media_duration_seconds,
    normalize_export_format,
    write_ffmpeg_chapter_file,
    write_mkvmerge_simple_chapters,
)
from scan_settings import ScanSettingsDialog


class QueueManager(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scan_settings = {
            "min_black_seconds": 0.4,
            "ratio_black_pixels": 0.98,
            "black_pixel_threshold": 0.08,
            "window_list": "",
            "export_format": "mp4",
            "max_analysis_width": 854,
            "use_hwaccel": False,
            "parallel_scan_jobs": 1,
        }
        self.setWindowTitle("MaChap File Queue")
        self.resize(600, 500)

        self.project_files: list[dict[str, Any]] = []

        layout = QVBoxLayout()

        self.import_list = QListWidget()
        self.load_button = QPushButton("Load Files")
        self.load_button.clicked.connect(self.load_files)

        self.scan_all_button = QPushButton("Scan All Files")
        self.scan_all_button.clicked.connect(self.scan_all_files)

        self.settings_button = QPushButton("Scan Settings")
        self.settings_button.clicked.connect(self.open_scan_settings)

        layout.addWidget(QLabel("Import Queue"))
        layout.addWidget(self.import_list)

        button_row = QHBoxLayout()
        button_row.addWidget(self.load_button)
        button_row.addWidget(self.scan_all_button)
        button_row.addWidget(self.settings_button)
        layout.addLayout(button_row)

        self.add_all_to_export_button = QPushButton("Add All to Export Queue")
        self.add_all_to_export_button.clicked.connect(self.add_all_to_export_queue)
        layout.addWidget(self.add_all_to_export_button)

        self.export_list = QListWidget()
        self.export_button = QPushButton("Export Files")
        self.export_button.clicked.connect(self.export_files)

        layout.addWidget(QLabel("Export Queue"))
        layout.addWidget(self.export_list)
        layout.addWidget(self.export_button)

        self.export_all_button = QPushButton("Export All Files")
        self.export_all_button.clicked.connect(self.export_all_files)
        layout.addWidget(self.export_all_button)

        self.export_dir = os.path.expanduser("~")

        self.choose_export_dir_button = QPushButton("Select Export Directory")
        self.choose_export_dir_button.clicked.connect(self.select_export_directory)
        layout.addWidget(self.choose_export_dir_button)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.import_list.itemDoubleClicked.connect(self.load_in_editor)

        self.scan_thread: BatchBlackdetectWorker | None = None
        self.progress_dialog: QProgressDialog | None = None
        self._scan_elapsed: QElapsedTimer | None = None

    def load_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select video files", "", "Video Files (*.mp4 *.avi *.mkv *.webm *.mov)"
        )
        for path in files:
            item = QListWidgetItem(path)
            self.import_list.addItem(item)
            self.project_files.append(
                {
                    "path": path,
                    "chapters": [],
                    "settings": self.scan_settings.copy(),
                }
            )

    def export_files(self) -> None:
        for i in range(self.export_list.count()):
            data = self.export_list.item(i).data(1000)
            if data:
                self.process_export_item(data)

    def scan_all_files(self) -> None:
        paths = [self.import_list.item(i).text() for i in range(self.import_list.count())]
        if not paths:
            QMessageBox.information(self, "No files", "Load video files before scanning.")
            return

        if self.scan_thread is not None and self.scan_thread.isRunning():
            QMessageBox.information(self, "Scan in progress", "A scan is already running.")
            return

        self._scan_elapsed = QElapsedTimer()
        self._scan_elapsed.start()

        self.progress_dialog = QProgressDialog(self)
        self.progress_dialog.setWindowTitle("Scanning videos")
        self.progress_dialog.setLabelText("Starting…")
        self.progress_dialog.setCancelButtonText("Cancel")
        self.progress_dialog.setRange(0, 1000)
        self.progress_dialog.setValue(0)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.canceled.connect(self.cancel_scan)

        self.scan_thread = BatchBlackdetectWorker(paths, self.scan_settings.copy())
        self.scan_thread.file_progress.connect(self._on_batch_scan_progress)
        self.scan_thread.result.connect(self.handle_scan_result)
        self.scan_thread.file_error.connect(self._on_batch_file_error)
        self.scan_thread.finished.connect(self.finish_scan)
        self.scan_thread.canceled.connect(self.finish_scan)

        self.scan_all_button.setEnabled(False)
        self.settings_button.setEnabled(False)
        self.scan_thread.start()
        self.progress_dialog.show()

    def _on_batch_scan_progress(self, idx: int, total: int, path: str, ratio: float) -> None:
        overall = (idx + min(1.0, ratio)) / max(total, 1)
        if self.progress_dialog is not None:
            self.progress_dialog.setValue(int(1000 * overall))
        el = self._scan_elapsed.elapsed() / 1000.0 if self._scan_elapsed is not None else 0.0
        eta = el * (1.0 / max(overall, 0.01) - 1.0) if overall > 0.02 else None
        name = os.path.basename(path) if path else ""
        label = (
            f"File {idx + 1} of {total}\n{name}\n"
            f"Overall about {overall * 100:.0f}% — ETA ~ {format_eta(eta)}\n"
            f"Elapsed {format_eta(el)}"
        )
        if self.progress_dialog is not None:
            self.progress_dialog.setLabelText(label)

    def _on_batch_file_error(self, path: str, message: str) -> None:
        QMessageBox.warning(
            self,
            "Scan error",
            f"{os.path.basename(path)}\n\n{message}",
        )

    def open_scan_settings(self) -> None:
        dialog = ScanSettingsDialog(self, self.scan_settings)
        dialog.settingsApplied.connect(self.update_scan_settings)
        if dialog.exec():
            self.scan_settings = dialog.get_settings()

    def update_scan_settings(self, new_settings: dict[str, Any]) -> None:
        self.scan_settings = new_settings

    def load_in_editor(self, item: QListWidgetItem) -> None:
        index = self.import_list.row(item)
        if index < 0 or index >= len(self.project_files):
            QMessageBox.warning(self, "Error", "Could not resolve the selected row.")
            return

        project = self.project_files[index]
        if not project.get("chapters"):
            QMessageBox.information(
                self,
                "Scan required",
                "Run **Scan All Files** on this queue before opening a file in the editor.",
            )
            return

        from gui import ChapterEditor

        for widget in QApplication.instance().topLevelWidgets():
            if isinstance(widget, ChapterEditor):
                widget.load_from_queue(project["path"], project["chapters"])
                return

        QMessageBox.information(
            self,
            "Editor not open",
            "Open the main MaChap Chapter Editor window first, then double-click a scanned file.",
        )

    def cancel_scan(self) -> None:
        if self.scan_thread is not None and self.scan_thread.isRunning():
            self.scan_thread.cancel()

    def handle_scan_result(self, index: int, chapters: list[float]) -> None:
        if 0 <= index < len(self.project_files):
            self.project_files[index]["chapters"] = chapters
            self.project_files[index]["settings"] = self.scan_settings.copy()

    def finish_scan(self) -> None:
        self.scan_all_button.setEnabled(True)
        self.settings_button.setEnabled(True)
        if self.progress_dialog is not None:
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
        self._scan_elapsed = None

    def process_export_item(self, file_info: dict[str, Any]) -> None:
        path = file_info["path"]
        chapters = file_info["chapters"]
        export_format = normalize_export_format(file_info.get("format"))

        base_name = os.path.splitext(os.path.basename(path))[0]
        output_basename = os.path.join(self.export_dir, f"{base_name}_chaptered")
        duration_sec = get_media_duration_seconds(path)

        fmt = export_format
        if fmt == "mkvmerge_txt":
            metadata_file = f"{output_basename}_chapters_mkvmerge.txt"
            write_mkvmerge_simple_chapters(chapters, metadata_file)
            return

        if fmt == "txt":
            metadata_file = f"{output_basename}_chapters_ffmeta.txt"
            write_ffmpeg_chapter_file(chapters, metadata_file, duration_sec=duration_sec)
            return

        metadata_file = f"{output_basename}_chapters_ffmeta.txt"
        write_ffmpeg_chapter_file(chapters, metadata_file, duration_sec=duration_sec)

        ext = ".mp4" if fmt == "mp4" else ".mkv"
        output_file = f"{output_basename}{ext}"

        if path.lower().endswith((".avi", ".wmv")):
            video_bitrate, audio_bitrate = get_bitrates(path)
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                path,
                "-i",
                metadata_file,
                "-map_metadata",
                "1",
                "-c:v",
                "libx264",
                "-b:v",
                str(video_bitrate),
                "-c:a",
                "aac",
                "-b:a",
                str(audio_bitrate),
                output_file,
            ]
        elif path.lower().endswith((".mp4", ".mkv")):
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                path,
                "-i",
                metadata_file,
                "-map_metadata",
                "1",
                "-c",
                "copy",
                output_file,
            ]
        else:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                path,
                "-i",
                metadata_file,
                "-map_metadata",
                "1",
                "-c:v",
                "libx264",
                "-crf",
                "22",
                "-preset",
                "medium",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                output_file,
            ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(
                self,
                "FFmpeg failed",
                (e.stderr or str(e))[-2000:],
            )

    def export_all_files(self) -> None:
        for i in range(self.export_list.count()):
            data = self.export_list.item(i).data(1000)
            if data:
                self.process_export_item(data)

    def select_export_directory(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Export Folder",
            os.path.expanduser("~"),
        )
        if dir_path:
            self.export_dir = dir_path

    def add_to_export_queue(self, path: str, chapters: list[float], export_format: str) -> None:
        fmt = normalize_export_format(export_format)
        item = QListWidgetItem(f"{os.path.basename(path)} → {fmt}")
        item.setData(
            1000,
            {
                "path": path,
                "chapters": chapters,
                "format": fmt,
            },
        )
        self.export_list.addItem(item)

    def add_all_to_export_queue(self) -> None:
        for project in self.project_files:
            if not project.get("chapters"):
                continue
            self.add_to_export_queue(
                project["path"],
                project["chapters"],
                project["settings"].get("export_format", "mp4"),
            )
