"""Qt workers that run FFmpeg blackdetect off the GUI thread."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal

from detector import BlackdetectCancelled, BlackdetectError, detect_black_frames
from export_utils import get_media_duration_seconds
from time_windows import parse_time_range_list


def _max_analysis_width_from_settings(settings: dict[str, Any]) -> int | None:
    mw = settings.get("max_analysis_width", 854)
    if mw is None:
        return 854
    mw = int(mw)
    return mw if mw > 0 else None


def _use_hwaccel_from_settings(settings: dict[str, Any]) -> bool:
    return bool(settings.get("use_hwaccel", False))


def _parallel_scan_jobs_from_settings(settings: dict[str, Any]) -> int:
    return max(1, int(settings.get("parallel_scan_jobs", 1)))


def format_eta(seconds: float | None) -> str:
    if seconds is None or seconds != seconds or seconds < 0 or seconds > 86400 * 7:
        return "…"
    seconds = float(seconds)
    if seconds >= 3600:
        return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"
    if seconds >= 60:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{int(seconds)}s"


class EditorBlackdetectWorker(QThread):
    """Single-file scan for the main chapter editor."""

    progress_ratio = Signal(float)
    finished_ok = Signal(list)
    failed = Signal(object)
    canceled = Signal()

    def __init__(self, video_path: str, settings: dict[str, Any]):
        super().__init__()
        self.video_path = video_path
        self.settings = settings
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            window_list = parse_time_range_list(self.settings.get("window_list", ""))
            duration = get_media_duration_seconds(self.video_path) or 0.0

            def on_ratio(r: float) -> None:
                self.progress_ratio.emit(r)

            events = detect_black_frames(
                self.video_path,
                min_black_seconds=self.settings["min_black_seconds"],
                ratio_black_pixels=self.settings["ratio_black_pixels"],
                black_pixel_threshold=self.settings["black_pixel_threshold"],
                window_list=window_list,
                max_analysis_width=_max_analysis_width_from_settings(self.settings),
                use_hwaccel=_use_hwaccel_from_settings(self.settings),
                parallel_jobs=_parallel_scan_jobs_from_settings(self.settings),
                is_cancelled=lambda: self._cancel,
                on_time_ratio=on_ratio if duration > 0 else None,
                duration_hint_sec=duration if duration > 0 else None,
            )
            chapters = [
                round(e["black_start"] + (e["black_duration"] / 2), 3) for e in events
            ]
            self.finished_ok.emit(chapters)
        except BlackdetectCancelled:
            self.canceled.emit()
        except BlackdetectError as e:
            self.failed.emit(e)


class BatchBlackdetectWorker(QThread):
    """Queue: scan many files with cancel and per-file progress."""

    file_progress = Signal(int, int, str, float)
    result = Signal(int, list)
    finished = Signal()
    canceled = Signal()
    file_error = Signal(str, str)

    def __init__(self, file_list: list[str], settings: dict[str, Any]):
        super().__init__()
        self.file_list = file_list
        self.settings = settings
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        n = len(self.file_list)
        for i, path in enumerate(self.file_list):
            if self._cancel:
                self.canceled.emit()
                return

            self.file_progress.emit(i, n, path, 0.0)

            window_list = parse_time_range_list(self.settings.get("window_list", ""))
            duration = get_media_duration_seconds(path) or 0.0

            try:

                def on_ratio(
                    r: float,
                    *,
                    ii: int = i,
                    nn: int = n,
                    pp: str = path,
                ) -> None:
                    self.file_progress.emit(ii, nn, pp, r)

                events = detect_black_frames(
                    path,
                    min_black_seconds=self.settings["min_black_seconds"],
                    ratio_black_pixels=self.settings["ratio_black_pixels"],
                    black_pixel_threshold=self.settings["black_pixel_threshold"],
                    window_list=window_list,
                    max_analysis_width=_max_analysis_width_from_settings(self.settings),
                    use_hwaccel=_use_hwaccel_from_settings(self.settings),
                    parallel_jobs=_parallel_scan_jobs_from_settings(self.settings),
                    is_cancelled=lambda: self._cancel,
                    on_time_ratio=on_ratio if duration > 0 else None,
                    duration_hint_sec=duration if duration > 0 else None,
                )
            except BlackdetectCancelled:
                self.canceled.emit()
                return
            except BlackdetectError as e:
                self.file_error.emit(path, str(e))
                self.result.emit(i, [])
                continue

            chapters = [
                round(e["black_start"] + (e["black_duration"] / 2), 3) for e in events
            ]
            self.file_progress.emit(i, n, path, 1.0)
            self.result.emit(i, chapters)

        self.finished.emit()
