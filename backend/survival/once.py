"""Log a crash once per distinct error instead of on every tick.

The worker ticks every second, so an error that repeats (a planner that keeps crashing on the
same state, a model endpoint that stays down) would otherwise fill the log. `log_once` writes the
traceback the first time each (where, error type, message) happens and stays quiet for repeats.
"""

from __future__ import annotations

import logging

SEEN_LIMIT = 256
_seen: dict[str, None] = {}


def log_once(logger: logging.Logger, where: str, error: BaseException) -> bool:
    """Log `error` with its traceback the first time it happens `where`. Returns True when it logged."""
    key = f"{where}|{type(error).__name__}: {error}"
    if key in _seen:
        return False
    _seen[key] = None
    if len(_seen) > SEEN_LIMIT:
        del _seen[next(iter(_seen))]
    logger.error("%s crashed: %s", where, error, exc_info=error)
    return True


def forget_logged() -> None:
    """Forget every logged error. Tests call it so one test's errors do not silence another's."""
    _seen.clear()
