import os
import json
import subprocess

def write_ffmpeg_chapter_file(chapters, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(";FFMETADATA1\n")
        for i, start_time in enumerate(chapters):
            start_ms = int(start_time * 1000)
            end_ms = start_ms + 500
            f.write("[CHAPTER]\n")
            f.write("TIMEBASE=1/1000\n")
            f.write(f"START={start_ms}\n")
            f.write(f"END={end_ms}\n")
            f.write(f"title=Chapter {i + 1}\n")

def get_bitrates(input_path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=bit_rate",
        "-of", "json",
        input_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    video_bitrate = None
    try:
        video_bitrate = int(json.loads(result.stdout)["streams"][0]["bit_rate"])
    except (KeyError, IndexError, ValueError):
        video_bitrate = 1000000

    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=bit_rate",
        "-of", "json",
        input_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    audio_bitrate = None
    try:
        audio_bitrate = int(json.loads(result.stdout)["streams"][0]["bit_rate"])
    except (KeyError, IndexError, ValueError):
        audio_bitrate = 128000

    return video_bitrate, audio_bitrate
