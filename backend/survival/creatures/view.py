"""What /api/mimo tells the viewer about creatures (spec L1, "API and viewer").

`creatures`: up to MOST_SHOWN creatures within 48 blocks of Mimo, nearest first: id, kind, the
cell it stands in (where its last move ends), heading, health as a fraction of its kind's, and
its state ("walking", "fleeing", "swimming", "grazing", "idle" or "dead"; a walk or flee that has
ended reads "idle"). Only when they are set: when it was last hurt (`hurt_at`: the flash,
knockback and health bar), when it died and what it dropped (`dead_at`, `drops`: the death puff)
and when a fish last leapt at Mimo's hook (`caught_at`). L2: a hostile kind says so
(`hostile`), its state may also be "chasing", "attacking" or "burning", and it tells when it last
struck Mimo (`struck_at`) and when it caught fire (`burning_at`). L3 final fix wave: an animal grown
from a creature seed says so (`tame`, only when set, for L4's herd). A creature that died more than
DEAD_KEEP seconds ago is left out.
`creature_moves`: the last move of each listed creature that ended within MOVE_WINDOW seconds,
with from, to, started and ends, and for a move longer than one block every cell it passes
(`cells`, [x, y, z] from `from` to `to`; a creature takes the same time over each), so the
viewer can replay it 1.5 s behind the server as it does Mimo's walks. A move that ended earlier
has nothing left to replay: the creature stands where it ended.
Reading never writes: the snapshot reads it on its read-only connection, in the same transaction as
the rest of the view, and a world from before L1 (an archive read without its schema update) has no
creatures.
"""

from __future__ import annotations

import math
import sqlite3

from backend.survival.creatures.kinds import kind_of
from backend.survival.creatures.simulate import DEAD_KEEP
from backend.survival.creatures.spawning import SIM_REACH
from backend.survival.creatures.table import Herd, dead

MOST_SHOWN = 32
MOVE_WINDOW = 3.0  # server seconds: the viewer draws 1.5 s behind and polls every second
MOVING = ("walking", "fleeing", "chasing")
WHEN_SET = ("hurt_at", "dead_at", "caught_at", "struck_at", "burning_at")


def state_of(creature: dict, now: float) -> str:
    pose = creature["state"].get("pose", "idle")
    path = creature["state"].get("path")
    if pose in MOVING and (not path or path[-1]["at"] <= now):
        return "idle"
    return pose


def point(entry: dict) -> dict:
    return {"x": int(round(entry["x"])), "y": int(round(entry["y"])), "z": int(round(entry["z"]))}


def creature_view(creature: dict, now: float) -> dict:
    kind = kind_of(creature["kind"])
    state = creature["state"]
    most = kind.health if kind is not None else max(creature["health"], 1.0)
    view = {"id": creature["id"], "kind": creature["kind"], "x": int(round(creature["x"])), "y": int(round(creature["y"])), "z": int(round(creature["z"])),
            "heading": round(creature["heading"], 1), "health": round(max(0.0, creature["health"]) / most, 1),
            "state": state_of(creature, now)}
    if kind is not None and kind.hostile:
        view["hostile"] = True
    if state.get("tame"):
        view["tame"] = True
    for key in WHEN_SET:
        if state.get(key) is not None:
            value = state[key]
            view[key] = round(value, 1) if isinstance(value, float) else value
    if state.get("drops"):
        view["drops"] = list(state["drops"])
    return view


def move_view(creature: dict) -> dict:
    path = creature["state"]["path"]
    move = {"id": creature["id"], "from": point(path[0]), "to": point(path[-1]), "started": round(path[0]["at"], 1),
            "ends": round(path[-1]["at"], 1)}
    if len(path) > 2:
        move["cells"] = [[int(entry["x"]), int(entry["y"]), int(entry["z"])] for entry in path]
    return move


def creatures_view(db: sqlite3.Connection, position: dict, now: float) -> dict:
    """The `creatures` and `creature_moves` fields of /api/mimo around `position`, read through `db`."""
    found = Herd(db).near(position["x"], position["z"], SIM_REACH)
    shown = [creature for creature in found
             if not dead(creature) or now - creature["state"].get("dead_at", now) <= DEAD_KEEP]
    shown.sort(key=lambda creature: (math.hypot(creature["x"] - position["x"], creature["z"] - position["z"]),
                                     creature["id"]))
    shown = shown[:MOST_SHOWN]
    moves = [move_view(creature) for creature in shown if creature["state"].get("path")
             and creature["state"]["path"][-1]["at"] >= now - MOVE_WINDOW]
    return {"creatures": [creature_view(creature, now) for creature in shown], "creature_moves": moves}
