from PySide6.QtWidgets import (
    QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox,
    QTextEdit, QPushButton, QHBoxLayout, QWidget
)
from PySide6.QtCore import Qt, Signal


class ScanSettingsDialog(QDialog):
    settingsApplied = Signal(dict)  # 🔔 Signal to notify parent of changes

    def __init__(self, parent=None, initial_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Black Frame Scan Settings")
        self.setMinimumWidth(420)

        self.settings = initial_settings or {
            "min_black_seconds": 2.0,
            "ratio_black_pixels": 0.98,
            "black_pixel_threshold": 0.1,
            "window_list": "",
        }

        layout = QFormLayout()

        self.min_black = QDoubleSpinBox()
        self.min_black.setRange(0.1, 30.0)
        self.min_black.setValue(self.settings["min_black_seconds"])
        layout.addRow("Min Black Duration (sec):", self.min_black)

        self.ratio_black = QDoubleSpinBox()
        self.ratio_black.setRange(0.0, 1.0)
        self.ratio_black.setSingleStep(0.01)
        self.ratio_black.setValue(self.settings["ratio_black_pixels"])
        layout.addRow("Ratio of Black Pixels (0–1):", self.ratio_black)

        self.threshold_black = QDoubleSpinBox()
        self.threshold_black.setRange(0.0, 1.0)
        self.threshold_black.setSingleStep(0.01)
        self.threshold_black.setValue(self.settings["black_pixel_threshold"])
        layout.addRow("Black Pixel Threshold (0–1):", self.threshold_black)

        self.window_list = QTextEdit()
        self.window_list.setPlaceholderText("00:02:00-00:03:00, 00:08:30-00:10:00")
        self.window_list.setPlainText(self.settings.get("window_list", ""))
        self.window_list.setFixedHeight(60)
        layout.addRow("Scan Time Windows:", self.window_list)

        # Buttons: OK, Cancel, Apply
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)

        button_row = QHBoxLayout()
        button_row.addWidget(self.buttons)
        button_row.addWidget(self.apply_button)

        container = QWidget()
        container.setLayout(button_row)
        layout.addRow(container)

        self.setLayout(layout)

    def get_settings(self):
        return {
            "min_black_seconds": self.min_black.value(),
            "ratio_black_pixels": self.ratio_black.value(),
            "black_pixel_threshold": self.threshold_black.value(),
            "window_list": self.window_list.toPlainText().strip()
        }

    def apply_settings(self):
        new_settings = self.get_settings()
        self.settingsApplied.emit(new_settings)  # 🔔 Tell parent new settings were saved
