from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from export_utils import normalize_export_format


class ScanSettingsDialog(QDialog):
    settingsApplied = Signal(dict)

    def __init__(self, parent=None, initial_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Black Frame Scan Settings")
        self.setMinimumWidth(420)

        self.settings = initial_settings or {
            "min_black_seconds": 2.0,
            "ratio_black_pixels": 0.98,
            "black_pixel_threshold": 0.1,
            "window_list": "",
            "export_format": "mp4",
            "max_analysis_width": 854,
            "use_hwaccel": False,
            "parallel_scan_jobs": 1,
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

        self.max_analysis_width = QSpinBox()
        self.max_analysis_width.setRange(0, 7680)
        self.max_analysis_width.setSingleStep(16)
        self.max_analysis_width.setSpecialValueText("Full resolution (slow)")
        mw_init = self.settings.get("max_analysis_width", 854)
        self.max_analysis_width.setValue(854 if mw_init is None else int(mw_init))
        self.max_analysis_width.setToolTip(
            "Downscale video to at most this width before blackdetect. "
            "Much faster on HD/4K; chapter times still match the file. "
            "0 = decode full size (slowest, maximum fidelity)."
        )
        layout.addRow("Max scan width (px, 0 = full):", self.max_analysis_width)

        self.use_hwaccel = QCheckBox("Prefer hardware decoding (-hwaccel auto)")
        self.use_hwaccel.setChecked(bool(self.settings.get("use_hwaccel", False)))
        self.use_hwaccel.setToolTip(
            "Lets FFmpeg use GPU/DXVA/VAAPI decoding when available. "
            "Turn off if FFmpeg fails to start or mis-detects on your system."
        )
        layout.addRow(self.use_hwaccel)

        self.parallel_scan_jobs = QSpinBox()
        self.parallel_scan_jobs.setRange(1, 12)
        self.parallel_scan_jobs.setValue(int(self.settings.get("parallel_scan_jobs", 1)))
        self.parallel_scan_jobs.setToolTip(
            "Number of parallel FFmpeg processes on different time ranges (1 = one "
            "slow pass, most accurate). Values >1 use fast input seek and can approach "
            "4× speed on a quad-core CPU; not used when scan time windows are set."
        )
        layout.addRow("Parallel scan jobs:", self.parallel_scan_jobs)

        self.export_format = QComboBox()
        self.export_format.addItem("MP4 (queue export / remux)", "mp4")
        self.export_format.addItem("MKV (queue export / remux)", "mkv")
        self.export_format.addItem("Chapter sidecar .txt (FFmpeg ffmetadata)", "txt")
        self.export_format.addItem("Chapter sidecar .txt (mkvmerge simple)", "mkvmerge_txt")

        current_fmt = normalize_export_format(self.settings.get("export_format", "mp4"))
        idx = self.export_format.findData(current_fmt)
        self.export_format.setCurrentIndex(0 if idx < 0 else idx)

        layout.addRow("Export format (queue / default file type):", self.export_format)

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

    def load_from(self, settings: dict) -> None:
        """Refresh widget values from a settings dict (same keys as ``get_settings``)."""
        self.min_black.setValue(settings["min_black_seconds"])
        self.ratio_black.setValue(settings["ratio_black_pixels"])
        self.threshold_black.setValue(settings["black_pixel_threshold"])
        self.window_list.setPlainText(settings.get("window_list", ""))
        mw = settings.get("max_analysis_width", 854)
        self.max_analysis_width.setValue(854 if mw is None else int(mw))
        self.use_hwaccel.setChecked(bool(settings.get("use_hwaccel", False)))
        self.parallel_scan_jobs.setValue(int(settings.get("parallel_scan_jobs", 1)))
        current_fmt = normalize_export_format(settings.get("export_format", "mp4"))
        idx = self.export_format.findData(current_fmt)
        self.export_format.setCurrentIndex(0 if idx < 0 else idx)

    def get_settings(self) -> dict:
        fmt = self.export_format.currentData()
        if fmt is None:
            fmt = "mp4"
        return {
            "min_black_seconds": self.min_black.value(),
            "ratio_black_pixels": self.ratio_black.value(),
            "black_pixel_threshold": self.threshold_black.value(),
            "window_list": self.window_list.toPlainText().strip(),
            "export_format": str(fmt),
            "max_analysis_width": self.max_analysis_width.value(),
            "use_hwaccel": self.use_hwaccel.isChecked(),
            "parallel_scan_jobs": self.parallel_scan_jobs.value(),
        }

    def apply_settings(self) -> None:
        self.settingsApplied.emit(self.get_settings())

    def accept(self) -> None:
        self.apply_settings()
        super().accept()
