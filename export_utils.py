from __future__ import annotations

import json
import subprocess
from typing import Any


def normalize_export_format(value: str | None) -> str:
    """Return ``mp4``, ``mkv``, ``txt`` (ffmetadata), or ``mkvmerge_txt``."""
    if not value:
        return "mp4"
    v = value.strip().lower()
    if "mkvmerge" in v:
        return "mkvmerge_txt"
    if v in ("mp4", ".mp4"):
        return "mp4"
    if v in ("mkv", ".mkv"):
        return "mkv"
    if "txt" in v or v.endswith(".txt"):
        return "txt"
    return "mp4"


def write_ffmpeg_chapter_file(
    chapters: list[float],
    output_path: str,
    *,
    duration_sec: float | None = None,
) -> None:
    """
    Write an FFmpeg ffmetadata chapter file.

    Each chapter spans from its start time until the next chapter start, or
    ``duration_sec`` for the last chapter. If duration is unknown, the last
    chapter uses a minimal end offset so the file remains valid.
    """
    sorted_chapters = sorted(chapters)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(";FFMETADATA1\n")
        for i, start_time in enumerate(sorted_chapters):
            if i + 1 < len(sorted_chapters):
                end_sec = sorted_chapters[i + 1]
            elif duration_sec is not None and duration_sec > start_time:
                end_sec = duration_sec
            else:
                end_sec = start_time + 1.0
            start_ms = int(start_time * 1000)
            end_ms = int(end_sec * 1000)
            if end_ms <= start_ms:
                end_ms = start_ms + 1
            f.write("[CHAPTER]\n")
            f.write("TIMEBASE=1/1000\n")
            f.write(f"START={start_ms}\n")
            f.write(f"END={end_ms}\n")
            f.write(f"title=Chapter {i + 1}\n")


def write_mkvmerge_simple_chapters(chapters: list[float], output_path: str) -> None:
    """Write mkvmerge 'simple chapter format' (CHAPTER01= / CHAPTER01NAME=)."""
    sorted_chapters = sorted(chapters)
    lines: list[str] = []
    for i, ts in enumerate(sorted_chapters, start=1):
        h = int(ts // 3600)
        m = int((ts % 3600) // 60)
        s = int(ts % 60)
        ms = int(round((ts - int(ts)) * 1000))
        formatted = f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
        lines.append(f"CHAPTER{i:02d}={formatted}")
        lines.append(f"CHAPTER{i:02d}NAME=Chapter {i}")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        if lines:
            f.write("\n")


def get_bitrates(input_path: str) -> tuple[int, int]:
    video_bitrate = 1_000_000
    audio_bitrate = 128_000

    cmd_v = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=bit_rate",
        "-of",
        "json",
        input_path,
    ]
    result = subprocess.run(cmd_v, capture_output=True, text=True)
    try:
        data: dict[str, Any] = json.loads(result.stdout)
        video_bitrate = int(data["streams"][0]["bit_rate"])
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        pass

    cmd_a = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=bit_rate",
        "-of",
        "json",
        input_path,
    ]
    result = subprocess.run(cmd_a, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        audio_bitrate = int(data["streams"][0]["bit_rate"])
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        pass

    return video_bitrate, audio_bitrate


def get_media_duration_seconds(path: str) -> float | None:
    """Return container duration in seconds, or None if unknown."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None
