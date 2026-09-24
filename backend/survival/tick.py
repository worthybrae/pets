"""One survival tick: bring the active life's world up to now.

The worker calls `tick_life` about once a second. A longer gap (a laptop that slept) is
caught up in steps of at most 60 game seconds, so a pet can starve while nobody watches. Each
step is its own transaction with its own path-search budget (`advance_world`), the way a fast
test run ticks, so a long catch-up is not one long write that locks the owner out, and a pet
catching up still walks, forages and gets home; between steps the worker lets its rules chooser
answer (`between`), so Mimo keeps choosing what to do, and a worker told to stop stops there
(`should_stop`) instead of running the rest of the gap first.
Each step first runs Mimo's timed actions up to the step's start (backend.survival.actions),
then advances vitals with the activity and surroundings at that moment. A `Mind` decides the
steps: its `plan` fills an empty queue (M1's `rest_plan` in the default `RESTING` mind), and its
optional hooks let a brain (backend.survival.brain) hear about finished steps (`observe`) and
notice each vitals step (`notice`). Minds never call a model here: the tick holds the world's
write transaction. After each chunk of actions the world regrows on its own
(backend.survival.renewal), whatever mind runs Mimo.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Callable

from backend.services.block_table import material_in
from backend.services.worldgen import biome_at
from backend.survival.actions import (
    ActionContext, Interrupt, Observe, Planner, activity_of, advance_actions, ensure_actions,
)
from backend.survival.clock import DAY_SECONDS, action_scale as action_scale_setting, clock_at, is_night, time_scale
from backend.survival.grid import world_grid
from backend.survival.once import log_once
from backend.survival.registry import LifeRegistry
from backend.survival.renewal import renew
from backend.survival.script import rest_plan
from backend.survival.vitals import (
    FIRE_REACH, FREEZING_BELOW, WARM_BLOCKS, Surroundings, is_sheltered, near_warm_block, step_vitals,
)
from backend.survival.world import SurvivalWorld, log_event, placed_near, read_state, write_state

logger = logging.getLogger(__name__)

MAX_STEP_SECONDS = 60.0
HUNGRY_BELOW = 30.0
CAUSE_TEXT = {"starvation": "starvation", "cold": "the cold", "drowning": "drowning", "fall": "a fall"}

Event = tuple[float, str, str]
# After each vitals step: (state, context, vitals before the step, surroundings, step start, step end).
Notice = Callable[[dict, ActionContext, dict, Surroundings, float, float], None]


@dataclass(frozen=True)
class Mind:
    """What runs Mimo inside a tick. `plan` fills an empty queue; the hooks are optional."""

    plan: Planner = rest_plan
    interrupt: Interrupt | None = None
    observe: Observe | None = None
    notice: Notice | None = None


RESTING = Mind()


def surroundings_at(db: sqlite3.Connection, seed: str, position: dict) -> Surroundings:
    x, y, z = round(position["x"]), round(position["y"]), round(position["z"])

    def material_at(cx: int, cy: int, cz: int) -> str:
        return material_in(db, cx, cy, cz, seed)

    return Surroundings(
        biome=biome_at(x, z, seed),
        sheltered=is_sheltered(material_at, x, y, z),
        near_fire=near_warm_block(placed_near(db, position, FIRE_REACH, WARM_BLOCKS), x, y, z),
        head_in_water=material_at(x, y, z) == "water",
    )


def note_crossings(state: dict, before: dict, at: float, events: list[Event]) -> None:
    after, name = state["vitals"], state["name"]
    if before["hunger"] >= HUNGRY_BELOW > after["hunger"]:
        state["last_thought"] = "My tummy is rumbling. I need food."
        events.append((at, "hungry", f"{name} is getting hungry."))
    if before["hunger"] > 0 >= after["hunger"]:
        state["last_thought"] = "I'm starving..."
        events.append((at, "starving", f"{name} is starving."))
    if before["warmth"] >= FREEZING_BELOW > after["warmth"]:
        state["last_thought"] = "I'm so cold."
        events.append((at, "freezing", f"{name} is freezing."))


def record_death(state: dict, cause: str, at: float, scale: float, events: list[Event]) -> None:
    """Mark Mimo dead at `at` and log it. The current step and the plan end with the life.

    A fatal fall can be discovered a catch-up step after the vitals (and any crossing, like
    "hungry") that already ran up to that step's cursor, so `at` can land before events already
    queued for it. Drop those: nothing should read as happening after Mimo died. Health already
    reads 0 by the time any cause is known (step_vitals or finish_fall got it there), so it is
    left alone.
    """
    events[:] = [event for event in events if event[0] <= at]
    day = clock_at(state["born_at"], at, scale)["day_number"]
    state.update(status="dead", died_at=at, cause=cause, action=None, queue=[])
    events.append((at, "death", f"{state['name']} died of {CAUSE_TEXT[cause]} on day {day}."))


def run_notice(mind: Mind, state: dict, context: ActionContext, before: dict, surroundings: Surroundings,
               since: float, at: float) -> None:
    """Call the mind's notice hook. A crashing hook is logged once and the tick goes on."""
    if mind.notice is None:
        return
    try:
        mind.notice(state, context, before, surroundings, since, at)
    except Exception as error:
        log_once(logger, "notice", error)


def run_renewal(state: dict, context: ActionContext, at: float) -> None:
    """Let the world regrow up to `at` (backend.survival.renewal). A crash is logged once and the
    tick goes on."""
    try:
        renew(state, context, at)
    except Exception as error:
        log_once(logger, "renewal", error)


def advance_world(world: SurvivalWorld, timestamp: float, scale: float, mind: Mind = RESTING,
                  action_scale: float = 1.0) -> dict:
    """Catch the world up to `timestamp` in one transaction and return the saved state."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None or timestamp <= state["last_tick_at"]:
            return state
        ensure_actions(state)
        events: list[Event] = []
        context = ActionContext(grid=world_grid(db, world.seed), planner=mind.plan, events=events,
                                clock_at=lambda at: clock_at(state["born_at"], at, scale),
                                observe=mind.observe, db=db, action_scale=action_scale,
                                interrupt=mind.interrupt)
        cursor = state["last_tick_at"]
        remaining = (timestamp - cursor) * scale
        while remaining > 1e-9:
            fell_at = advance_actions(state, context, cursor)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
                break
            run_renewal(state, context, cursor)
            step = min(MAX_STEP_SECONDS, remaining)
            night = is_night(clock_at(state["born_at"], cursor, scale)["phase"])
            last_hello = state["last_hello_at"] or state["born_at"]
            before = state["vitals"]
            surroundings = surroundings_at(db, world.seed, state["position"])
            state["vitals"], cause = step_vitals(
                before, step, night=night, activity=activity_of(state), surroundings=surroundings,
                lonely=(cursor - last_hello) * scale > DAY_SECONDS)
            since = cursor
            cursor += step / scale
            remaining -= step
            note_crossings(state, before, cursor, events)
            if cause:
                record_death(state, cause, cursor, scale, events)
                break
            run_notice(mind, state, context, before, surroundings, since, cursor)
        if state["died_at"] is None:
            fell_at = advance_actions(state, context, timestamp)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
            else:
                run_renewal(state, context, timestamp)
        state["last_tick_at"] = state["died_at"] if state["died_at"] is not None else timestamp
        write_state(db, state)
        for at, kind, text in sorted(events, key=lambda event: event[0]):
            log_event(db, at, kind, text)
        return state


def tick_life(registry: LifeRegistry, timestamp: float | None = None, scale: float | None = None,
              mind: Mind = RESTING, action_scale: float | None = None,
              between: Callable[[float], None] | None = None,
              should_stop: Callable[[], bool] | None = None) -> dict | None:
    """Advance the active life and archive it if it died. Returns its state, or None if no pet is alive.

    A gap longer than one catch-up step (60 game seconds) is advanced one step per transaction,
    calling `between(at)` after a step only when a whole further step still remains (fix round 1:
    an ordinary tick's small leftover, such as the worker's ~1 s sleep running a hair past one
    step, must not itself wake the rules chooser) while Mimo lives. `should_stop()` is asked after
    each committed step that leaves more to catch up: when it says yes (the worker was told to
    stop), the catch-up ends there, and the next tick goes on from the last committed step."""
    life = registry.active_life()
    if life is None:
        return None
    timestamp = time.time() if timestamp is None else timestamp
    scale = time_scale() if scale is None else scale
    action_scale = action_scale_setting() if action_scale is None else action_scale
    world = SurvivalWorld(registry.world_path(life))
    at = world.state()["last_tick_at"]
    while True:
        at = min(timestamp, at + MAX_STEP_SECONDS / scale)
        state = advance_world(world, at, scale, mind, action_scale)
        if at >= timestamp or state["died_at"] is not None:
            break
        if should_stop is not None and should_stop():
            break
        if between is not None and timestamp - at >= MAX_STEP_SECONDS / scale:
            between(at)
    if state["died_at"] is not None:
        registry.mark_dead(life["id"], state["died_at"], state["cause"])
    return state
