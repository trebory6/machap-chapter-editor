from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QFileDialog, QListWidgetItem
)

from detector import detect_black_frames  # assuming this is your scan function

from scan_settings import ScanSettingsDialog

class QueueManager(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scan_settings = {
            "min_black_seconds": 2.0,
            "ratio_black_pixels": 0.98,
            "black_pixel_threshold": 0.1,
            "window_list": "",
        }
        self.setWindowTitle("MaChap File Queue")
        self.resize(600, 500)  # ⬅ add this to ensure it has a size!

        self.project_files = []  # each entry: {"path": ..., "chapters": [...], "settings": {...}}

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

        # --- Export Queue Section ---
        self.export_list = QListWidget()
        self.export_button = QPushButton("Export Files")
        self.export_button.clicked.connect(self.export_files)

        layout.addWidget(QLabel("Export Queue"))
        layout.addWidget(self.export_list)
        layout.addWidget(self.export_button)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def load_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select video files", "", "Video Files (*.mp4 *.avi *.mkv)")
        for path in files:
            item = QListWidgetItem(path)
            self.import_list.addItem(item)

    def export_files(self):
        # Placeholder logic
        print("Exporting files in export queue...")
        for i in range(self.export_list.count()):
            print(self.export_list.item(i).text())


    def scan_all_files(self):
        for i in range(self.import_list.count()):
            path = self.import_list.item(i).text()

            # Use default or custom settings
            settings = {
                "min_black_seconds": 2.0,
                "ratio_black_pixels": 0.98,
                "black_pixel_threshold": 0.1,
            }

            black_frames = detect_black_frames(
                path,
                min_duration=settings["min_black_seconds"],
                ratio=settings["ratio_black_pixels"],
                threshold=settings["black_pixel_threshold"]
            )

            chapters = [round(frame["black_start"], 3) for frame in black_frames]

            # Store or update the project entry
            if i < len(self.project_files):
                self.project_files[i]["chapters"] = chapters
                self.project_files[i]["settings"] = settings
            else:
                self.project_files.append({
                    "path": path,
                    "chapters": chapters,
                    "settings": settings
                })

        print("✅ Scanned all files.")

    def open_scan_settings(self):
        dialog = ScanSettingsDialog(self, self.scan_settings)
        dialog.settingsApplied.connect(self.update_scan_settings)
        if dialog.exec():
            self.scan_settings = dialog.get_settings()

    def update_scan_settings(self, new_settings):
        self.scan_settings = new_settings
        print("📋 Queue Scan Settings updated:", self.scan_settings)
