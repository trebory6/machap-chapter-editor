from time_windows import (
    DEFAULT_SCAN_WINDOW_LIST_TEXT,
    expand_scan_time_windows,
    parse_time_range_list,
)


def test_empty_and_whitespace() -> None:
    assert parse_time_range_list("") == []
    assert parse_time_range_list("   ") == []


def test_single_range() -> None:
    assert parse_time_range_list("00:01:00-00:02:00") == [(60.0, 120.0)]


def test_multiple_ranges() -> None:
    r = parse_time_range_list("00:00:00-00:00:01, 00:10:00-00:20:00")
    assert r == [(0.0, 1.0), (600.0, 1200.0)]


def test_split_only_first_hyphen() -> None:
    """End time must not be split on hyphens inside (not applicable for HH:MM:SS)."""
    assert parse_time_range_list("01:00:00-02:30:45") == [(3600.0, 9045.0)]


def test_invalid_skipped() -> None:
    assert parse_time_range_list("not-a-range,00:00:01-00:00:02") == [(1.0, 2.0)]


def test_reversed_or_equal_range_ignored() -> None:
    assert parse_time_range_list("00:02:00-00:01:00") == []
    assert parse_time_range_list("00:01:00-00:01:00") == []


def test_parse_skips_end_anchor_ranges() -> None:
    """Static parser ignores $END lines; use ``expand_scan_time_windows`` for those."""
    assert parse_time_range_list("00:00:05-$END-00:00:30") == []
    assert parse_time_range_list("00:00:05-$END-00:00:30,00:01:00-00:02:00") == [(60.0, 120.0)]


def test_expand_fixed_range_ignores_duration() -> None:
    assert expand_scan_time_windows("00:01:00-00:02:00", 0.0) == [(60.0, 120.0)]


def test_expand_default_window_text() -> None:
    assert DEFAULT_SCAN_WINDOW_LIST_TEXT == "00:00:05-$END-00:00:30"
    assert expand_scan_time_windows(DEFAULT_SCAN_WINDOW_LIST_TEXT, 600.0) == [(5.0, 570.0)]


def test_expand_end_anchor_case_insensitive() -> None:
    assert expand_scan_time_windows("00:00:05-$end-00:00:30", 100.0) == [(5.0, 70.0)]


def test_expand_skips_end_when_duration_unknown() -> None:
    assert expand_scan_time_windows("00:00:05-$END-00:00:30", 0.0) == []


def test_expand_invalid_window_dropped() -> None:
    """Start not strictly before computed end."""
    assert expand_scan_time_windows("00:00:05-$END-00:00:30", 32.0) == []
