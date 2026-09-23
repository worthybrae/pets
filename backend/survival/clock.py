"""The world clock. One game day is 3,600 game seconds and starts at dawn when a life is born.

MIMO_TIME_SCALE (default 1) sets how many game seconds pass per real second. It exists for
manual testing; automated tests pass the scale in directly.
"""

from __future__ import annotations

import math
import os

DAY_SECONDS = 3600.0
PHASES: tuple[tuple[str, float, float], ...] = (
    ("dawn", 0.0, 180.0),
    ("day", 180.0, 2220.0),
    ("dusk", 2220.0, 2400.0),
    ("night", 2400.0, 3420.0),
    ("pre_dawn", 3420.0, 3600.0),
)
# Night and pre-dawn together are the 20 dark minutes. Dusk still counts as day.
NIGHT_PHASES = frozenset({"night", "pre_dawn"})


def time_scale() -> float:
    """Game seconds per real second from MIMO_TIME_SCALE. Missing or invalid values mean 1."""
    try:
        scale = float(os.environ.get("MIMO_TIME_SCALE", "1"))
    except ValueError:
        return 1.0
    return scale if math.isfinite(scale) and scale > 0 else 1.0


def phase_at(seconds_into_day: float) -> str:
    seconds = seconds_into_day % DAY_SECONDS
    for name, start, end in PHASES:
        if start <= seconds < end:
            return name
    return PHASES[-1][0]


def is_night(phase: str) -> bool:
    return phase in NIGHT_PHASES


def clock_at(born_at: float, timestamp: float, scale: float = 1.0) -> dict:
    """Day number (from 1), seconds into the day, time of day (0-1) and phase."""
    elapsed = max(0.0, timestamp - born_at) * scale
    seconds = elapsed % DAY_SECONDS
    return {
        "day_number": int(elapsed // DAY_SECONDS) + 1,
        "seconds_into_day": seconds,
        "time_of_day": seconds / DAY_SECONDS,
        "phase": phase_at(seconds),
        "day_seconds": DAY_SECONDS,
        "time_scale": scale,
    }
