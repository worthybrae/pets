"""One survival tick: bring the active life's world up to now.

The worker calls `tick_life` about once a second. A longer gap (a laptop that slept) is
caught up in steps of at most 60 game seconds, so a pet can starve while nobody watches.
Each step first runs Mimo's timed actions up to the step's start (backend.survival.actions),
then advances vitals with the activity and surroundings at that moment. A planner decides the
next steps whenever Mimo runs out: `rest_plan` (M1's sleep rule) unless the caller passes
another; the worker passes the interim `scripted_plan` until the brain arrives.
"""

from __future__ import annotations

import sqlite3
import time

from backend.services.block_table import material_in
from backend.services.worldgen import biome_at
from backend.survival.actions import ActionContext, Planner, activity_of, advance_actions, ensure_actions
from backend.survival.clock import DAY_SECONDS, clock_at, is_night, time_scale
from backend.survival.grid import world_grid
from backend.survival.registry import LifeRegistry
from backend.survival.script import rest_plan
from backend.survival.vitals import (
    FIRE_REACH, FREEZING_BELOW, WARM_BLOCKS, Surroundings, is_sheltered, near_warm_block, step_vitals,
)
from backend.survival.world import SurvivalWorld, log_event, placed_near, read_state, write_state

MAX_STEP_SECONDS = 60.0
HUNGRY_BELOW = 30.0
CAUSE_TEXT = {"starvation": "starvation", "cold": "the cold", "drowning": "drowning", "fall": "a fall"}

Event = tuple[float, str, str]


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


def advance_world(world: SurvivalWorld, timestamp: float, scale: float, planner: Planner = rest_plan) -> dict:
    """Catch the world up to `timestamp` in one transaction and return the saved state."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None or timestamp <= state["last_tick_at"]:
            return state
        ensure_actions(state)
        events: list[Event] = []
        context = ActionContext(grid=world_grid(db, world.seed), planner=planner, events=events,
                                clock_at=lambda at: clock_at(state["born_at"], at, scale))
        cursor = state["last_tick_at"]
        remaining = (timestamp - cursor) * scale
        while remaining > 1e-9:
            fell_at = advance_actions(state, context, cursor)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
                break
            step = min(MAX_STEP_SECONDS, remaining)
            night = is_night(clock_at(state["born_at"], cursor, scale)["phase"])
            last_hello = state["last_hello_at"] or state["born_at"]
            before = state["vitals"]
            state["vitals"], cause = step_vitals(
                before, step, night=night, activity=activity_of(state),
                surroundings=surroundings_at(db, world.seed, state["position"]),
                lonely=(cursor - last_hello) * scale > DAY_SECONDS)
            cursor += step / scale
            remaining -= step
            note_crossings(state, before, cursor, events)
            if cause:
                record_death(state, cause, cursor, scale, events)
                break
        if state["died_at"] is None:
            fell_at = advance_actions(state, context, timestamp)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
        state["last_tick_at"] = state["died_at"] if state["died_at"] is not None else timestamp
        write_state(db, state)
        for at, kind, text in sorted(events, key=lambda event: event[0]):
            log_event(db, at, kind, text)
        return state


def tick_life(registry: LifeRegistry, timestamp: float | None = None, scale: float | None = None,
              planner: Planner = rest_plan) -> dict | None:
    """Advance the active life and archive it if it died. Returns its state, or None if no pet is alive."""
    life = registry.active_life()
    if life is None:
        return None
    timestamp = time.time() if timestamp is None else timestamp
    scale = time_scale() if scale is None else scale
    state = advance_world(SurvivalWorld(registry.world_path(life)), timestamp, scale, planner)
    if state["died_at"] is not None:
        registry.mark_dead(life["id"], state["died_at"], state["cause"])
    return state
