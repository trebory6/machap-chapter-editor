from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QListWidgetItem,
    QFileDialog, QLabel, QProgressDialog
)
from detector import detect_black_frames
from scan_settings import ScanSettingsDialog
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import Qt

from export_utils import write_ffmpeg_chapter_file
from export_utils import get_bitrates

import os
import subprocess

class ScanWorker(QThread):
    progress = Signal(int)
    finished = Signal()
    canceled = Signal()
    result = Signal(int, list)

    def __init__(self, file_list, settings):
        super().__init__()
        self.file_list = file_list
        self.settings = settings
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        from gui import parse_time_range_list
        from detector import detect_black_frames

        for i, path in enumerate(self.file_list):
            if self._cancel:
                self.canceled.emit()
                return

            window_list = parse_time_range_list(self.settings.get("window_list", ""))
            black_frames = detect_black_frames(
                path,
                min_black_seconds=self.settings["min_black_seconds"],
                ratio_black_pixels=self.settings["ratio_black_pixels"],
                black_pixel_threshold=self.settings["black_pixel_threshold"],
                window_list=window_list
            )

            chapters = [
                round(frame["black_start"] + frame["black_duration"] / 2, 3)
                for frame in black_frames
            ]

            self.result.emit(i, chapters)
            self.progress.emit(i + 1)

        self.finished.emit()


class QueueManager(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scan_settings = {
            "min_black_seconds": 0.4,
            "ratio_black_pixels": 0.98,
            "black_pixel_threshold": 0.08,
            "window_list": "",
        }
        self.setWindowTitle("MaChap File Queue")
        self.resize(600, 500)

        self.project_files = []

        # Layouts
        layout = QVBoxLayout()

        # --- Import Queue Section ---
        self.import_list = QListWidget()
        self.load_button = QPushButton("Load Files")
        self.scan_all_button = QPushButton("Scan All Files")
        self.scan_all_button.clicked.connect(self.scan_all_files)
        self.load_button.clicked.connect(self.load_files)

        layout.addWidget(QLabel("Import Queue"))
        layout.addWidget(self.import_list)
        self.scan_all_button = QPushButton("Scan All Files")
        self.scan_all_button.clicked.connect(self.scan_all_files)
        self.settings_button = QPushButton("Scan Settings")
        self.settings_button.clicked.connect(self.open_scan_settings)

        button_row = QHBoxLayout()
        button_row.addWidget(self.load_button)
        button_row.addWidget(self.scan_all_button)
        button_row.addWidget(self.settings_button)

        layout.addLayout(button_row)

        self.add_all_to_export_button = QPushButton("Add All to Export Queue")
        self.add_all_to_export_button.clicked.connect(self.add_all_to_export_queue)
        layout.addWidget(self.add_all_to_export_button)

        # --- Export Queue Section ---
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

    def load_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select video files", "", "Video Files (*.mp4 *.avi *.mkv)")
        for path in files:
            item = QListWidgetItem(path)
            self.import_list.addItem(item)

    def export_files(self):
        print("Exporting files in export queue...")
        for i in range(self.export_list.count()):
            print(self.export_list.item(i).text())


    def scan_all_files(self):
        paths = [self.import_list.item(i).text() for i in range(self.import_list.count())]

        self.progress_dialog = QProgressDialog("Scanning files...", "Cancel", 0, len(paths), self)
        self.progress_dialog.setWindowTitle("Scanning")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_scan)

        self.scan_thread = ScanWorker(paths, self.scan_settings.copy())
        self.scan_thread.progress.connect(self.progress_dialog.setValue)
        self.scan_thread.result.connect(self.handle_scan_result)
        self.scan_thread.finished.connect(self.finish_scan)
        self.scan_thread.canceled.connect(self.finish_scan)
        self.scan_thread.start()

        self.progress_dialog.show()

        print("✅ Scanned all files.")

    def open_scan_settings(self):
        dialog = ScanSettingsDialog(self, self.scan_settings)
        dialog.settingsApplied.connect(self.update_scan_settings)
        if dialog.exec():
            self.scan_settings = dialog.get_settings()

    def update_scan_settings(self, new_settings):
        self.scan_settings = new_settings
        print("📋 Queue Scan Settings updated:", self.scan_settings)

    def load_in_editor(self, item):
        index = self.import_list.row(item)
        project = self.project_files[index]

        from gui import ChapterEditor

        for widget in QApplication.instance().topLevelWidgets():
            if isinstance(widget, ChapterEditor):
                widget.load_from_queue(project["path"], project["chapters"])
                print(f"📂 Loaded into editor: {project['path']} with {len(project['chapters'])} chapters")
                return

        print("❌ No ChapterEditor window open")

    def cancel_scan(self):
        if hasattr(self, "scan_thread"):
            self.scan_thread.cancel()

    def handle_scan_result(self, index, chapters):
        if index < len(self.project_files):
            self.project_files[index]["chapters"] = chapters
            self.project_files[index]["settings"] = self.scan_settings.copy()
        else:
            self.project_files.append({
                "path": self.import_list.item(index).text(),
                "chapters": chapters,
                "settings": self.scan_settings.copy()
            })

    def finish_scan(self):
        print("✅ Scanning complete or canceled.")
        self.progress_dialog.close()

    def process_export_item(self, file_info):
        path = file_info["path"]
        chapters = file_info["chapters"]
        export_format = file_info["format"]

        base, _ = os.path.splitext(path)
        original_dir = os.path.dirname(path)
        base_name = os.path.splitext(os.path.basename(path))[0]
        output_basename = os.path.join(original_dir, f"{base_name}_chaptered")
        metadata_file = f"{output_basename}_chapters.txt"

        # 1. Write chapter file
        write_ffmpeg_chapter_file(chapters, metadata_file)

        # 2. Export route
        if export_format.startswith(".txt"):
            print(f"📝 Saved chapter file only: {metadata_file}")
            return

        output_file = f"{output_basename}{export_format}"

        # --- AVI / WMV: Re-encode using original bitrates ---
        if path.lower().endswith((".avi", ".wmv")):
            video_bitrate, audio_bitrate = get_bitrates(path)
            print(f"🎯 Auto bitrate → Video: {video_bitrate} | Audio: {audio_bitrate}")

            cmd = [
                "ffmpeg", "-y", "-i", path, "-i", metadata_file,
                "-map_metadata", "1",
                "-c:v", "libx264", "-b:v", str(video_bitrate),
                "-c:a", "aac", "-b:a", str(audio_bitrate),
                output_file
            ]

        # --- MP4 / MKV: Stream copy + inject chapters ---
        elif path.lower().endswith((".mp4", ".mkv")):
            cmd = [
                "ffmpeg", "-y", "-i", path, "-i", metadata_file,
                "-map_metadata", "1", "-c", "copy", output_file
            ]

        # --- Other formats fallback: re-encode with reasonable defaults ---
        else:
            cmd = [
                "ffmpeg", "-y", "-i", path, "-i", metadata_file,
                "-map_metadata", "1",
                "-c:v", "libx264", "-crf", "22", "-preset", "medium",
                "-c:a", "aac", "-b:a", "160k",
                output_file
            ]

        print("🛠 FFmpeg command:", " ".join(cmd))

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("🔧 FFmpeg STDOUT:\n", result.stdout)
            print("⚠️ FFmpeg STDERR:\n", result.stderr)
            print(f"✅ Done: {output_file}")
        except subprocess.CalledProcessError as e:
            print("❌ FFmpeg failed:")
            print(e.stderr)


        # print(f"🚀 Exporting: {output_file}")
        # subprocess.run(cmd)
        # print(f"✅ Done: {output_file}")

    def export_all_files(self):
        for i in range(self.export_list.count()):
            data = self.export_list.item(i).data(1000)
            self.process_export_item(data)
        print("✅ All exports completed.")

    def select_export_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Export Folder", os.path.expanduser("~"))
        if dir_path:
            self.export_dir = dir_path
            print(f"📁 Export directory set to: {self.export_dir}")

    def add_to_export_queue(self, path, chapters, export_format):
        item = QListWidgetItem(f"{os.path.basename(path)} → {export_format}")
        item.setData(1000, {
            "path": path,
            "chapters": chapters,
            "format": export_format
        })
        self.export_list.addItem(item)
        print(f"📦 Added to export queue: {path} with {len(chapters)} chapters")

    def add_all_to_export_queue(self):
        for project in self.project_files:
            if not project["chapters"]:
                continue
            self.add_to_export_queue(
                project["path"],
                project["chapters"],
                project["settings"].get("export_format", ".mp4")
            )
        print("📦 All scanned files added to export queue.")


