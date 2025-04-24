import subprocess
from datetime import timedelta


def detect_black_frames(
    video_path,
    min_black_seconds=0.4,
    ratio_black_pixels=0.98,
    black_pixel_threshold=0.08,
    window_list=None
):
    vf_filter = (
        f"blackdetect=d={min_black_seconds}:pic_th={ratio_black_pixels}:pix_th={black_pixel_threshold}"
    )

    cmd = [
        "ffmpeg", "-hide_banner", "-i", video_path,
        "-vf", vf_filter,
        "-an", "-f", "null", "-"
    ]

    process = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    black_events = []

    print("🔎 FFmpeg stderr output:")
    print(process.stderr)

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

    # If window_list is defined, filter results
    if window_list:
        black_events = [
            e for e in black_events
            if any(start <= e["black_start"] <= end for start, end in window_list)
        ]

    return black_events

def format_timestamp(seconds):
    """Convert float seconds to HH:MM:SS.mmm format."""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"
