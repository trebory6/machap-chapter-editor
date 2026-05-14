"""Parse scan time window strings into (start_sec, end_sec) pairs."""

from __future__ import annotations

import logging
import re
from typing import Final

logger = logging.getLogger(__name__)

# Literal default for Scan Time Windows: 5s after start through (duration − 30s).
# The ``$END-HH:MM:SS`` tail is “seconds before file end” expressed as a time-of-day
# offset (here 30 seconds → ``00:00:30``).
DEFAULT_SCAN_WINDOW_LIST_TEXT: Final[str] = "00:00:05-$END-00:00:30"

_END_ANCHOR = re.compile(r"-\$END-", re.IGNORECASE)


def _hms_to_seconds(t: str) -> float:
    parts = t.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid time format: '{t}' (expected HH:MM:SS)")
    hours, minutes, seconds = map(int, parts)
    return float(hours * 3600 + minutes * 60 + seconds)


def parse_time_range_list(time_string: str) -> list[tuple[float, float]]:
    """
    Parse comma-separated ranges. Each range is ``HH:MM:SS-HH:MM:SS``
    (24h clock, integer seconds in each component).

    Whitespace around commas and hyphens is tolerated. Invalid segments are skipped.
    Ranges using ``-$END-`` must be resolved with ``expand_scan_time_windows``.
    """
    if not time_string or not time_string.strip():
        return []

    ranges: list[tuple[float, float]] = []
    for pair in time_string.split(","):
        pair = pair.strip()
        if not pair or _END_ANCHOR.search(pair):
            continue
        if "-" not in pair:
            continue
        start_str, end_str = pair.split("-", 1)
        try:
            start = _hms_to_seconds(start_str)
            end = _hms_to_seconds(end_str)
            if start < end:
                ranges.append((start, end))
        except (ValueError, TypeError) as e:
            logger.warning("Failed to parse time range %r: %s", pair, e)
    return ranges


def expand_scan_time_windows(time_string: str, duration_sec: float) -> list[tuple[float, float]]:
    """
    Parse scan window text into ``(start_sec, end_sec)`` pairs.

    Supports fixed ranges ``HH:MM:SS-HH:MM:SS`` and duration-relative ends
    ``HH:MM:SS-$END-HH:MM:SS`` where the part after ``$END`` is the offset *before*
    the end of the file (same ``HH:MM:SS`` integer parsing as fixed times).

    When ``duration_sec`` is unknown (<= 0), ``-$END-`` segments are skipped.
    """
    if not time_string or not time_string.strip():
        return []

    out: list[tuple[float, float]] = []
    for pair in time_string.split(","):
        pair = pair.strip()
        if not pair:
            continue
        m = _END_ANCHOR.search(pair)
        if m:
            start_str = pair[: m.start()].strip()
            offset_str = pair[m.end() :].strip()
            try:
                start = _hms_to_seconds(start_str)
                trim = _hms_to_seconds(offset_str)
            except (ValueError, TypeError) as e:
                logger.warning("Failed to parse $END time range %r: %s", pair, e)
                continue
            if duration_sec <= 0:
                continue
            end = duration_sec - trim
            if start < end:
                out.append((start, end))
            continue
        if "-" not in pair:
            continue
        start_str, end_str = pair.split("-", 1)
        try:
            start = _hms_to_seconds(start_str)
            end = _hms_to_seconds(end_str)
            if start < end:
                out.append((start, end))
        except (ValueError, TypeError) as e:
            logger.warning("Failed to parse time range %r: %s", pair, e)
    return out
