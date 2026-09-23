"""M1's sleep rule as steps: the default mind's planner and the fallback when a planner crashes.

rest_plan sleeps at night or when exhausted, and otherwise waits (at most a minute) for
nightfall. The brain (backend.survival.brain) replaced M2's interim stand-in script.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival.clock import is_night
from backend.survival.vitals import EXHAUSTED_BELOW

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

NIGHTFALL = 2400.0
MAX_WAIT = 60.0


def rest_plan(state: dict, context: ActionContext, at: float) -> list[dict]:
    """Sleep at night or when exhausted; otherwise wait (at most a minute) for nightfall."""
    clock = context.clock_at(at)
    night = is_night(clock["phase"])
    if night or state["vitals"]["energy"] < EXHAUSTED_BELOW:
        thought = "It's dark. Time to curl up and sleep." if night else "I'm too tired to keep my eyes open."
        return [{"kind": "sleep", "thought": thought}]
    until_night = (NIGHTFALL - clock["seconds_into_day"]) / clock["time_scale"]
    return [{"kind": "wait", "seconds": max(1.0, min(MAX_WAIT, until_night))}]
