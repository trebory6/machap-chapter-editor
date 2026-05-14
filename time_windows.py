"""Parse scan time window strings into (start_sec, end_sec) pairs."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def parse_time_range_list(time_string: str) -> list[tuple[float, float]]:
    """
    Parse comma-separated ranges. Each range is ``HH:MM:SS-HH:MM:SS``
    (24h clock, integer seconds in each component).

    Whitespace around commas and hyphens is tolerated. Invalid segments are skipped.
    """
    if not time_string or not time_string.strip():
        return []

    def hms_to_seconds(t: str) -> float:
        parts = t.strip().split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid time format: '{t}' (expected HH:MM:SS)")
        hours, minutes, seconds = map(int, parts)
        return float(hours * 3600 + minutes * 60 + seconds)

    ranges: list[tuple[float, float]] = []
    for pair in time_string.split(","):
        pair = pair.strip()
        if "-" not in pair:
            continue
        start_str, end_str = pair.split("-", 1)
        try:
            start = hms_to_seconds(start_str)
            end = hms_to_seconds(end_str)
            if start < end:
                ranges.append((start, end))
        except (ValueError, TypeError) as e:
            logger.warning("Failed to parse time range %r: %s", pair, e)
    return ranges
