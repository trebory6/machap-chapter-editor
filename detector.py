from __future__ import annotations

import re
import subprocess
import threading
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import timedelta

_FFMPEG_STATUS_TIME = re.compile(r"time=\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_OUT_TIME_US = re.compile(r"out_time_us=(\d+)")
_OUT_TIME_MS = re.compile(r"out_time_ms=(\d+)")


class BlackdetectError(Exception):
    """FFmpeg blackdetect failed or produced no usable output."""

    def __init__(self, message: str, *, returncode: int | None = None, stderr: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class BlackdetectCancelled(Exception):
    """User cancelled blackdetect while FFmpeg was running."""


def ffmpeg_status_time_seconds(line: str) -> float | None:
    """
    Best-effort decode timestamp from an FFmpeg progress line (stderr).

    Tries ``time=``, then ``out_time_us=`` / ``out_time_ms=`` (common when ``time=``
    is missing or ``N/A`` on some builds or filtergraphs).
    """
    m = _FFMPEG_STATUS_TIME.search(line)
    if m:
        hours, minutes = int(m.group(1)), int(m.group(2))
        sec = float(m.group(3))
        return float(hours * 3600 + minutes * 60 + sec)
    m = _OUT_TIME_US.search(line)
    if m:
        return int(m.group(1)) / 1_000_000.0
    m = _OUT_TIME_MS.search(line)
    if m:
        return int(m.group(1)) / 1000.0
    return None


def build_blackdetect_filter(
    min_black_seconds: float,
    ratio_black_pixels: float,
    black_pixel_threshold: float,
    max_analysis_width: int | None,
) -> str:
    """
    Build a video filter chain ending in ``blackdetect``.

    When ``max_analysis_width`` > 0, frames are downscaled (width capped, height
    proportional) before blackdetect. Timestamps in blackdetect output still refer
    to the timeline of the decoded segment.
    """
    bd = (
        f"blackdetect=d={min_black_seconds}:pic_th={ratio_black_pixels}:pix_th={black_pixel_threshold}"
    )
    if max_analysis_width is not None and max_analysis_width > 0:
        w = int(max_analysis_width)
        if w < 16:
            w = 16
        return f"scale='min({w}\\,iw)':-2,{bd}"
    return bd


def segment_scan_spans(duration: float, jobs: int, overlap: float) -> list[tuple[float, float]]:
    """
    Return ``(ss_start, length)`` pairs for parallel scans using ``-ss`` before ``-i``.

    Segments overlap by ``overlap`` seconds (except at file start) so blacks on
    chunk boundaries are not missed.
    """
    if jobs < 2 or duration <= 0:
        return [(0.0, duration)]

    chunk = duration / jobs
    spans: list[tuple[float, float]] = []
    for i in range(jobs):
        start = max(0.0, i * chunk - (overlap if i > 0 else 0.0))
        end = min(duration, (i + 1) * chunk + (overlap if i < jobs - 1 else 0.0))
        length = max(0.5, end - start)
        spans.append((start, length))
    return spans


def _parse_blackdetect_stderr(stderr: str) -> list[dict[str, float]]:
    black_events: list[dict[str, float]] = []
    for ln in stderr.splitlines():
        if "black_start" not in ln:
            continue
        parts = ln.split()
        event: dict[str, float] = {}
        for part in parts:
            if ":" not in part:
                continue
            key, _, value = part.partition(":")
            try:
                event[key] = float(value)
            except ValueError:
                continue
        if "black_start" in event and "black_duration" in event:
            black_events.append(event)
    return black_events


def _merge_overlapping_events(
    events: list[dict[str, float]],
    gap: float = 0.2,
) -> list[dict[str, float]]:
    if not events:
        return []
    ev = sorted(events, key=lambda e: e["black_start"])
    out: list[dict[str, float]] = [dict(ev[0])]
    for e in ev[1:]:
        if e["black_start"] - out[-1]["black_start"] <= gap:
            prev_end = out[-1]["black_start"] + out[-1].get("black_duration", 0)
            cur_end = e["black_start"] + e.get("black_duration", 0)
            if cur_end > prev_end:
                out[-1] = dict(e)
        else:
            out.append(dict(e))
    return out


def _ffmpeg_cmd(
    video_path: str,
    vf_filter: str,
    *,
    use_hwaccel: bool,
    ss_before_input: float | None = None,
    output_duration: float | None = None,
) -> list[str]:
    cmd: list[str] = ["ffmpeg"]
    if use_hwaccel:
        cmd += ["-hwaccel", "auto"]
    cmd += ["-hide_banner", "-stats_period", "1"]
    if ss_before_input is not None and ss_before_input > 0:
        cmd += ["-ss", f"{ss_before_input:.4f}"]
    cmd += ["-i", video_path]
    if output_duration is not None and output_duration > 0:
        cmd += ["-t", f"{output_duration:.4f}"]
    cmd += ["-vf", vf_filter, "-an", "-f", "null", "-"]
    return cmd


def _run_blackdetect_stream(
    cmd: list[str],
    cancel: Callable[[], bool],
    on_time_ratio: Callable[[float], None] | None,
    duration_for_ratio: float | None,
    *,
    active_procs: list[subprocess.Popen] | None = None,
    procs_lock: threading.Lock | None = None,
) -> str:
    """Run ffmpeg, stream stderr; return full stderr text. Raises on failure/cancel."""
    t0 = time.monotonic()
    last_ratio: list[float] = [0.0]
    idle = 0

    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    if active_procs is not None:
        if procs_lock is not None:
            with procs_lock:
                active_procs.append(proc)
        else:
            active_procs.append(proc)

    assert proc.stderr is not None
    stderr_parts: list[str] = []

    if on_time_ratio:
        on_time_ratio(0.0)
        last_ratio[0] = 0.0

    try:
        while True:
            if cancel():
                proc.kill()
                proc.wait(timeout=30)
                raise BlackdetectCancelled()

            line = proc.stderr.readline()
            if line:
                stderr_parts.append(line)
                if on_time_ratio and duration_for_ratio and duration_for_ratio > 0:
                    ts = ffmpeg_status_time_seconds(line)
                    if ts is not None:
                        r = min(1.0, max(0.0, ts / duration_for_ratio))
                        last_ratio[0] = max(last_ratio[0], r)
                        on_time_ratio(last_ratio[0])
            elif proc.poll() is not None:
                break
            else:
                idle += 1
                time.sleep(0.02)
                if (
                    on_time_ratio
                    and duration_for_ratio
                    and duration_for_ratio > 0
                    and idle % 40 == 0
                ):
                    # Wall-clock hint when FFmpeg emits few/no parseable progress lines
                    # (some Blu-ray / VC-1 / odd containers). Assume decode often runs well
                    # below realtime; keep this conservative so the bar does not race to 100%.
                    wall = time.monotonic() - t0
                    guess = min(0.92, wall / max(duration_for_ratio * 8.0, 30.0))
                    last_ratio[0] = max(last_ratio[0], guess)
                    on_time_ratio(last_ratio[0])
    except BlackdetectCancelled:
        raise
    except Exception:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
        raise
    finally:
        if active_procs is not None:
            if procs_lock is not None:
                with procs_lock:
                    try:
                        active_procs.remove(proc)
                    except ValueError:
                        pass
            else:
                try:
                    active_procs.remove(proc)
                except ValueError:
                    pass

    if proc.returncode is None:
        proc.wait(timeout=30)
    rc = proc.returncode or 0
    stderr = "".join(stderr_parts)

    if cancel():
        raise BlackdetectCancelled()

    if rc != 0:
        tail = stderr[-4000:]
        raise BlackdetectError(
            f"ffmpeg exited with code {rc}",
            returncode=rc,
            stderr=tail,
        )
    return stderr


def detect_black_frames(
    video_path: str,
    min_black_seconds: float = 0.4,
    ratio_black_pixels: float = 0.98,
    black_pixel_threshold: float = 0.08,
    window_list: list[tuple[float, float]] | None = None,
    *,
    max_analysis_width: int | None = 854,
    use_hwaccel: bool = False,
    parallel_jobs: int = 1,
    is_cancelled: Callable[[], bool] | None = None,
    on_time_ratio: Callable[[float], None] | None = None,
    duration_hint_sec: float | None = None,
) -> list[dict[str, float]]:
    """
    Run FFmpeg ``blackdetect``.

    ``max_analysis_width``: downscale before blackdetect (often modest gain; decode
    still runs at full resolution).

    ``use_hwaccel``: pass ``-hwaccel auto`` (can hang or stall on some Windows setups;
    default **False**). Parallel segment workers always use software decode.

    ``parallel_jobs`` > 1: run multiple FFmpeg processes on time slices using ``-ss``
    before ``-i`` (much faster on multi-core). Timestamps are shifted back to file
    time; seek is keyframe-aligned so positions can be off by up to ~1–2 GOPs near
    slice edges. Used for a **full-file** scan (no windows) or a **single**
    contiguous window (for example the default trim span). Multiple disjoint windows
    fall back to one sequential decode of the whole file. ``parallel_jobs`` 1 uses
    a single process; with exactly one window it still skips decode outside that span
    via ``-ss`` / ``-t`` when possible. While parallel workers run, overall progress
    is the mean of per-segment decode ratios (polled from the coordinator thread).
    """
    cancel = is_cancelled or (lambda: False)
    vf_filter = build_blackdetect_filter(
        min_black_seconds,
        ratio_black_pixels,
        black_pixel_threshold,
        max_analysis_width,
    )

    windows: list[tuple[float, float]] = list(window_list) if window_list else []
    single_span: tuple[float, float] | None = None
    if len(windows) == 1:
        w_lo, w_hi = windows[0]
        if w_hi > w_lo:
            single_span = (w_lo, w_hi)

    duration_sec = float(duration_hint_sec) if duration_hint_sec is not None else 0.0

    parallel_full_file = (
        parallel_jobs > 1
        and duration_sec >= 60.0
        and len(windows) == 0
    )
    parallel_in_span = (
        parallel_jobs > 1
        and duration_sec >= 60.0
        and single_span is not None
        and (single_span[1] - single_span[0]) >= 60.0
    )
    parallel_ok = parallel_full_file or parallel_in_span

    if not parallel_ok:
        ss_in: float | None = None
        t_out: float | None = None
        time_off = 0.0
        ratio_dur = duration_sec if duration_sec > 0 else None
        if single_span is not None and (single_span[1] - single_span[0]) > 0.5:
            w_lo, w_hi = single_span
            ss_in = w_lo
            t_out = w_hi - w_lo
            time_off = w_lo
            if ratio_dur is None or ratio_dur <= 0:
                ratio_dur = t_out
            else:
                ratio_dur = t_out
        cmd = _ffmpeg_cmd(
            video_path,
            vf_filter,
            use_hwaccel=use_hwaccel,
            ss_before_input=ss_in,
            output_duration=t_out,
        )
        stderr = _run_blackdetect_stream(
            cmd,
            cancel,
            on_time_ratio,
            ratio_dur,
        )
        black_events = _parse_blackdetect_stderr(stderr)
        for e in black_events:
            e["black_start"] = round(e["black_start"] + time_off, 4)
        if len(windows) > 1:
            black_events = [
                e
                for e in black_events
                if any(start <= e["black_start"] <= end for start, end in windows)
            ]
        elif len(windows) == 1:
            lo, hi = windows[0]
            black_events = [e for e in black_events if lo <= e["black_start"] <= hi]
        return black_events

    scan_lo = 0.0
    scan_span_len = duration_sec
    if parallel_in_span and single_span is not None:
        scan_lo, scan_hi = single_span
        scan_span_len = max(0.5, scan_hi - scan_lo)

    jobs = max(2, min(int(parallel_jobs), 16, max(2, int(scan_span_len / 30))))
    overlap = 4.0
    spans = segment_scan_spans(scan_span_len, jobs, overlap)
    active: list[subprocess.Popen] = []
    lock = threading.Lock()
    progress_slots = [0.0] * jobs
    progress_lock = threading.Lock()

    def make_local_cb(job_index: int):
        def local_progress(local_r: float) -> None:
            with progress_lock:
                progress_slots[job_index] = min(1.0, max(0.0, local_r))

        return local_progress

    def run_segment(job_index: int, span_start: float, seg_len: float) -> list[dict[str, float]]:
        if cancel():
            raise BlackdetectCancelled()
        abs_ss = scan_lo + span_start
        cmd = _ffmpeg_cmd(
            video_path,
            vf_filter,
            use_hwaccel=False,
            ss_before_input=abs_ss,
            output_duration=seg_len,
        )

        stderr = _run_blackdetect_stream(
            cmd,
            cancel,
            on_time_ratio=make_local_cb(job_index),
            duration_for_ratio=seg_len,
            active_procs=active,
            procs_lock=lock,
        )
        events = _parse_blackdetect_stderr(stderr)
        for e in events:
            e["black_start"] = round(e["black_start"] + abs_ss, 4)
        return events

    all_events: list[dict[str, float]] = []
    if on_time_ratio:
        on_time_ratio(0.0)

    try:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            future_list = [
                pool.submit(run_segment, i, spans[i][0], spans[i][1]) for i in range(jobs)
            ]
            fut_to_idx = {fut: i for i, fut in enumerate(future_list)}
            pending = set(future_list)
            while pending:
                if cancel():
                    with lock:
                        for p in list(active):
                            if p.poll() is None:
                                p.kill()
                    raise BlackdetectCancelled()
                if on_time_ratio:
                    with progress_lock:
                        agg = sum(progress_slots) / jobs
                    on_time_ratio(min(0.99, agg))
                finished, pending = wait(
                    pending, timeout=0.25, return_when=FIRST_COMPLETED
                )
                for fut in finished:
                    jidx = fut_to_idx[fut]
                    all_events.extend(fut.result())
                    with progress_lock:
                        progress_slots[jidx] = 1.0
                    if on_time_ratio:
                        with progress_lock:
                            agg = sum(progress_slots) / jobs
                        on_time_ratio(min(0.99, agg))
            if on_time_ratio:
                on_time_ratio(1.0)
    except BlackdetectCancelled:
        with lock:
            for p in list(active):
                if p.poll() is None:
                    p.kill()
        raise

    merged = _merge_overlapping_events(all_events, gap=0.25)
    if windows:
        merged = [
            e
            for e in merged
            if any(start <= e["black_start"] <= end for start, end in windows)
        ]
    return merged


def format_timestamp(seconds: float) -> str:
    """Convert float seconds to HH:MM:SS.mmm format."""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{milliseconds:03}"
