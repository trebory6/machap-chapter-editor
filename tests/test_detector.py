from detector import (
    build_blackdetect_filter,
    ffmpeg_status_time_seconds,
    segment_scan_spans,
)


def test_ffmpeg_status_time_seconds() -> None:
    assert ffmpeg_status_time_seconds("frame= 100 fps=25 q=-0.0 size= 0kB time=00:01:02.34") == (
        62.34
    )
    assert ffmpeg_status_time_seconds("no time here") is None


def test_build_blackdetect_filter_full_res() -> None:
    f = build_blackdetect_filter(0.4, 0.98, 0.08, None)
    assert f.startswith("blackdetect=")
    assert "scale" not in f


def test_build_blackdetect_filter_scaled() -> None:
    f = build_blackdetect_filter(0.4, 0.98, 0.08, 854)
    assert "scale=" in f
    assert "min(854\\,iw)" in f
    assert "blackdetect=d=0.4" in f


def test_segment_scan_spans_cover_duration() -> None:
    spans = segment_scan_spans(1000.0, 4, 4.0)
    assert len(spans) == 4
    assert spans[0][0] == 0.0
    last_start, last_len = spans[-1]
    assert last_start + last_len >= 1000.0 - 0.01
