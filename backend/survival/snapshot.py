"""The JSON shapes the API returns for lives."""

from __future__ import annotations

import math
import sqlite3

from backend.services.block_table import blocks_seq
from backend.services.crafting import RECIPES
from backend.services.live_mimo import MimoStore
from backend.survival.actions import PATH_WINDOW
from backend.survival.care import care_remaining
from backend.survival.clock import clock_at
from backend.survival.memory import explored, nearest, places, structures
from backend.survival.registry import LifeRegistry
from backend.survival.world import ROUTINE_EVENTS, SurvivalWorld, read_state, recent_events

NOTABLE_LIMIT = 6
EVENTS_SHOWN = 12
DECAY_WINDOW = 10.0  # real seconds a decayed leaf is streamed for its puff
MAP_REACH = 96  # blocks each way (12 patches) of explored ground streamed for the minimap
VISITS_SHOWN = 9  # visits are capped in the stream (one digit): the viewer only needs "seen"

# The parts of the current step the viewer animates. The rest (reach, reached, segments) is the
# planner's bookkeeping.
ACTION_FIELDS = ("kind", "started_at", "ends_at", "path", "target", "block", "item", "recipe", "blocks")


def action_view(action: dict | None) -> dict | None:
    """The current step for the viewer, or None when Mimo is between steps."""
    if action is None:
        return None
    return {key: action[key] for key in ACTION_FIELDS if key in action}


def brain_view(brain: dict | None) -> dict:
    """What Mimo is up to: its purpose, a running reflex, who chose, and whether it is choosing.
    A world whose brain has not started yet is about to choose."""
    if brain is None:
        return {"purpose": None, "reflex": None, "picker": None, "choosing": True}
    return {"purpose": brain.get("purpose"), "reflex": brain.get("reflex"), "picker": brain.get("picker"),
            "choosing": brain.get("pending") is not None}


def replayable(recent: list[dict], now: float) -> list[dict]:
    """Finished steps for the viewer. A path is sent only while the viewer (about 1.5 s behind)
    can still replay it: steps that ended more than PATH_WINDOW seconds ago go without one."""
    return [entry if "path" not in entry or entry["ended_at"] >= now - PATH_WINDOW
            else {key: value for key, value in entry.items() if key != "path"} for entry in recent]


def recent_decays(decays: list[dict], now: float) -> list[dict]:
    """Leaves that decayed in the last DECAY_WINDOW real seconds, for the viewer's puffs. Older ones
    are left out, so a viewer that opens (or a long catch-up) does not puff them all at once."""
    return [decay for decay in decays if decay["at"] >= now - DECAY_WINDOW]


def life_row(life: dict, scale: float, now: float) -> dict:
    """A registry row for the viewer: no file path, plus days lived.

    Survival lives count game days (the clock's day number). The legacy life counts real days.
    """
    row = {key: value for key, value in life.items() if key != "db_path"}
    end = life["died_at"] if life["died_at"] is not None else now
    if life["kind"] == "legacy":
        row["days"] = max(1, math.ceil((end - life["born_at"]) / 86400))
    else:
        row["days"] = clock_at(life["born_at"], end, scale)["day_number"]
    return row


def notable(events: list[dict]) -> list[dict]:
    """A legacy life's notable events. Survival worlds select theirs in SQL (notable_events)."""
    return [event for event in events if event["kind"] not in ROUTINE_EVENTS][:NOTABLE_LIMIT]


def open_archive(registry: LifeRegistry, life: dict) -> MimoStore | SurvivalWorld:
    """A read-only view of any life's world."""
    path = registry.world_path(life)
    if life["kind"] == "legacy":
        return MimoStore(path, read_only=True)
    return SurvivalWorld(path, read_only=True)


def built_rows(db: sqlite3.Connection) -> list[dict]:
    """What Mimo built, oldest first: kind, name, status and anchor. A world from before M5 that
    is only read (an archive) has no structures table yet, and so built nothing."""
    try:
        found = structures(db)
    except sqlite3.OperationalError:
        return []
    return [{key: structure[key] for key in ("id", "kind", "name", "status", "x", "y", "z")} for structure in found]


def built_view(world: SurvivalWorld) -> list[dict]:
    with world.connect() as db:
        return built_rows(db)


def here_of(state: dict) -> tuple[int, int, int]:
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def explored_view(db: sqlite3.Connection, state: dict) -> list[list[int]]:
    """[rx, rz, visits] for each 8x8 patch Mimo visited within 12 patches (96 blocks) of it, at most
    625, visits capped at 9, for the minimap's fog of war: under 9 KB even 6,000 blocks out."""
    found = explored(db, here_of(state), MAP_REACH)
    return [[rx, rz, min(visits, VISITS_SHOWN)] for (rx, rz), (visits, _) in sorted(found.items())]


def landmarks_view(db: sqlite3.Connection, state: dict) -> list[dict]:
    """Home and the nearest farm within 96 blocks, as {kind, x, y, z}, for the minimap. A world
    from before M3 read as an archive remembers none."""
    here = here_of(state)
    try:
        home = places(db, ("home",))
        farms = places(db, ("farm",), around=here, reach=MAP_REACH)
    except sqlite3.OperationalError:
        return []
    shown = home[:1] + [farm for farm in [nearest(farms, here, ("farm",), MAP_REACH)] if farm is not None]
    return [{key: place[key] for key in ("kind", "x", "y", "z")} for place in shown]


def survival_view(world: SurvivalWorld, now: float, scale: float) -> dict:
    """A survival world's state. A dead life's clock stops at its death. Everything is read in one
    read-only transaction, so the state, events, blocks and memory agree."""
    with world.connect() as db:
        db.execute("BEGIN")
        state = read_state(db)
        events = recent_events(db, EVENTS_SHOWN)
        seq = blocks_seq(db)
        built = built_rows(db)
        ground = explored_view(db, state)
        landmarks = landmarks_view(db, state)
    at = state["died_at"] if state["died_at"] is not None else now
    return {
        "clock": clock_at(state["born_at"], at, scale),
        "vitals": {name: round(value, 2) for name, value in state["vitals"].items()},
        "position": state["position"],
        "status": state["status"],
        "last_thought": state["last_thought"],
        "events": events,
        "inventory": state["inventory"],
        "recipes": RECIPES,
        "blocks_seq": seq,
        "care": care_remaining(state, now),
        "world_seed": state["world_seed"],
        "last_tick_at": state["last_tick_at"],
        "server_time": now,
        "died_at": state["died_at"],
        "cause": state["cause"],
        # Worlds from before M2 have no action fields until their first tick.
        "action": action_view(state.get("action")),
        "recent_actions": replayable(state.get("recent_actions", []), now),
        # Leaves that decayed lately ({x, y, z, at}), so the viewer can show a puff as each goes.
        "decays": recent_decays(state.get("decays", []), now),
        # M5: what Mimo built, and what its chests hold ({"x,y,z": {item: count}}).
        "structures": built,
        "chests": state.get("chests", {}),
        # Where Mimo has been ([rx, rz, visits] per 8x8 patch near it) and its home and farm, for
        # the minimap.
        "explored": ground,
        "landmarks": landmarks,
        **brain_view(state.get("brain")),
    }


def alive_snapshot(life: dict, world: SurvivalWorld, now: float, scale: float) -> dict:
    return {"phase": "alive", "life": life_row(life, scale, now), **survival_view(world, now, scale)}


def life_detail(registry: LifeRegistry, life: dict, scale: float, now: float) -> dict:
    """One life's row, notable events and final state (the legacy snapshot shape for life 1)."""
    archive = open_archive(registry, life)
    if isinstance(archive, MimoStore):
        state = archive.snapshot()
        events = notable(state["events"])
    else:
        state = survival_view(archive, now, scale)
        events = archive.notable_events(NOTABLE_LIMIT)
    return {"life": life_row(life, scale, now), "notable_events": events, "state": state}


def life_summary(registry: LifeRegistry, life: dict, scale: float, now: float) -> dict:
    detail = life_detail(registry, life, scale, now)
    return {**detail["life"], "notable_events": detail["notable_events"]}
