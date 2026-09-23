"""One survival tick: bring the active life's world up to now.

The worker calls `tick_life` about once a second. A longer gap (a laptop that slept) is
caught up in steps of at most 60 game seconds, so a pet can starve while nobody watches.
Until the brain arrives (M3) Mimo stands where it hatched and only follows the interim
sleep rule: sleep when exhausted or at night, wake rested after dawn.
"""

from __future__ import annotations

import sqlite3
import time

from backend.services.block_table import material_in
from backend.services.worldgen import biome_at
from backend.survival.clock import DAY_SECONDS, clock_at, is_night, time_scale
from backend.survival.registry import LifeRegistry
from backend.survival.vitals import (
    EXHAUSTED_BELOW, FIRE_REACH, FREEZING_BELOW, WARM_BLOCKS, Surroundings, is_sheltered, near_warm_block,
    step_vitals,
)
from backend.survival.world import SurvivalWorld, log_event, placed_near, read_state, write_state

MAX_STEP_SECONDS = 60.0
WAKE_ENERGY = 95.0
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


def update_sleep(state: dict, night: bool, at: float, events: list[Event]) -> None:
    """The interim rule: sleep when exhausted or at night; wake once rested and it is not night."""
    energy = state["vitals"]["energy"]
    if state["status"] == "sleeping":
        if energy >= WAKE_ENERGY and not night:
            state["status"] = "idle"
            state["last_thought"] = "Good morning. I feel rested."
            events.append((at, "wake", f"{state['name']} woke up."))
    elif night or energy < EXHAUSTED_BELOW:
        state["status"] = "sleeping"
        state["last_thought"] = ("It's dark. Time to curl up and sleep." if night
                                 else "I'm too tired to keep my eyes open.")
        events.append((at, "sleep", f"{state['name']} fell asleep."))


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


def advance_world(world: SurvivalWorld, timestamp: float, scale: float) -> dict:
    """Catch the world up to `timestamp` in one transaction and return the saved state."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None or timestamp <= state["last_tick_at"]:
            return state
        surroundings = surroundings_at(db, world.seed, state["position"])
        events: list[Event] = []
        cursor = state["last_tick_at"]
        remaining = (timestamp - cursor) * scale
        while remaining > 1e-9:
            step = min(MAX_STEP_SECONDS, remaining)
            night = is_night(clock_at(state["born_at"], cursor, scale)["phase"])
            update_sleep(state, night, cursor, events)
            last_hello = state["last_hello_at"] or state["born_at"]
            before = state["vitals"]
            state["vitals"], cause = step_vitals(
                before, step, night=night, activity="sleeping" if state["status"] == "sleeping" else "idle",
                surroundings=surroundings, lonely=(cursor - last_hello) * scale > DAY_SECONDS)
            cursor += step / scale
            remaining -= step
            note_crossings(state, before, cursor, events)
            if cause:
                day = clock_at(state["born_at"], cursor, scale)["day_number"]
                state.update(status="dead", died_at=cursor, cause=cause)
                events.append((cursor, "death", f"{state['name']} died of {CAUSE_TEXT[cause]} on day {day}."))
                break
        state["last_tick_at"] = state["died_at"] if state["died_at"] is not None else timestamp
        write_state(db, state)
        for at, kind, text in events:
            log_event(db, at, kind, text)
        return state


def tick_life(registry: LifeRegistry, timestamp: float | None = None, scale: float | None = None) -> dict | None:
    """Advance the active life and archive it if it died. Returns its state, or None if no pet is alive."""
    life = registry.active_life()
    if life is None:
        return None
    timestamp = time.time() if timestamp is None else timestamp
    scale = time_scale() if scale is None else scale
    state = advance_world(SurvivalWorld(registry.world_path(life)), timestamp, scale)
    if state["died_at"] is not None:
        registry.mark_dead(life["id"], state["died_at"], state["cause"])
    return state
