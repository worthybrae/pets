"""Wall-clock budget checks that hold on a busy machine (L2 final fix wave).

One timed run's mean flaked when the machine was loaded, and the first run in a process is cold
(about 20 ms a slice where later runs take 12). `best_mean` runs a measurement up to `tries` times
and returns the lowest mean, stopping at the first run under `budget`. The check itself stays: a
real regression is over budget on every run, while a passing load spike is not.

The creature budget these tests hold is 20 ms per slice: one 60-game-second catch-up transaction
(tick.MAX_STEP_SECONDS), which near a hostile is 60 one-second fight steps plus its final call. At
the worker's live 1x cadence (a transaction a real second) the same creatures cost about 1.3 ms a
real second.
"""

from __future__ import annotations

import gc
import math
from typing import Callable

TRIES = 3


def best_mean(measure: Callable[[], list[float]], budget: float, tries: int = TRIES) -> float:
    """The lowest mean of `measure()`'s timings over up to `tries` runs, stopping under `budget`."""
    best = math.inf
    for _ in range(tries):
        gc.collect()  # garbage left by earlier tests is not this code's cost
        timings = measure()
        best = min(best, sum(timings) / len(timings))
        if best < budget:
            break
    return best
