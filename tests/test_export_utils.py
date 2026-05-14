import os
import tempfile

from export_utils import (
    normalize_export_format,
    write_ffmpeg_chapter_file,
    write_mkvmerge_simple_chapters,
)


def test_normalize_export_format() -> None:
    assert normalize_export_format(None) == "mp4"
    assert normalize_export_format("mp4") == "mp4"
    assert normalize_export_format(".MKV") == "mkv"
    assert normalize_export_format(".txt") == "txt"
    assert normalize_export_format("mkvmerge_txt") == "mkvmerge_txt"
    assert normalize_export_format(".txt(MKVMerge)") == "mkvmerge_txt"


def test_write_ffmpeg_chapter_file_end_times() -> None:
    chapters = [10.0, 20.0, 35.5]
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        write_ffmpeg_chapter_file(chapters, path, duration_sec=100.0)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        assert "START=10000" in text
        assert "END=20000" in text
        assert "START=20000" in text
        assert "END=35500" in text
        assert "START=35500" in text
        assert "END=100000" in text
    finally:
        os.unlink(path)


def test_write_mkvmerge_simple_chapters() -> None:
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        write_mkvmerge_simple_chapters([3661.5], path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        assert "CHAPTER01=01:01:01.500" in text
        assert "CHAPTER01NAME=Chapter 1" in text
    finally:
        os.unlink(path)


def test_build_remux_command_copy_for_mp4() -> None:
    from export_utils import build_remux_with_metadata_command

    cmd = build_remux_with_metadata_command(
        r"C:\videos\clip.mp4",
        r"C:\meta\ch.txt",
        r"C:\out\out.mp4",
    )
    assert "-c" in cmd and "copy" in cmd
    assert "libx264" not in cmd
