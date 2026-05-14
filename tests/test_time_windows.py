from time_windows import parse_time_range_list


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
