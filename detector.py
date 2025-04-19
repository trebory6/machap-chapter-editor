import subprocess
from datetime import timedelta


def detect_black_frames(video_path):
    cmd = [
        "ffmpeg", "-hide_banner", "-i", video_path,
        "-vf", "blackdetect=d=0.5:pic_th=0.98",
        "-an", "-f", "null", "-"
    ]

    process = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    black_events = []

    for line in process.stderr.splitlines():
        if "black_start" in line:
            parts = line.split()
            event = {}
            for part in parts:
                if ':' in part:
                    key, value = part.split(":")
                    try:
                        event[key] = float(value)
                    except ValueError:
                        continue
            black_events.append(event)

    return black_events


def format_timestamp(seconds):
    """Convert float seconds to HH:MM:SS.mmm format."""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"
