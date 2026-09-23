"""A stand-in plan until the brain arrives. M3 replaces this module with purposes and a planner.

rest_plan is M1's rule as steps: sleep at night or when exhausted, otherwise wait for nightfall.
scripted_plan gives Mimo something to do by day: walk to the nearest tree within 24 blocks,
chop its logs from the bottom up and craft them into planks, and walk out to look for more
trees when none is near.
"""

from __future__ import annotations

import math

from backend.services.worldgen import terrain_height, trees_in_chunk
from backend.survival.clock import is_night
from backend.survival.grid import CHUNK, Cell, Grid
from backend.survival.steps import as_cell
from backend.survival.vitals import EXHAUSTED_BELOW

NIGHTFALL = 2400.0
MAX_WAIT = 60.0
TREE_SEARCH = 24
TRUNK_HEIGHT = 4
LOG = "oak_log"
# Close enough to the lowest log that the top one (3 higher) stays within reach on level ground.
STAND_REACH = 2.0
WANDER_DISTANCE = 48
WANDER_REACH = 3.0
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def rest_plan(state: dict, grid: Grid, at: float, clock: dict) -> list[dict]:
    """Sleep at night or when exhausted; otherwise wait (at most a minute) for nightfall."""
    night = is_night(clock["phase"])
    if night or state["vitals"]["energy"] < EXHAUSTED_BELOW:
        thought = "It's dark. Time to curl up and sleep." if night else "I'm too tired to keep my eyes open."
        return [{"kind": "sleep", "thought": thought}]
    until_night = (NIGHTFALL - clock["seconds_into_day"]) / clock["time_scale"]
    return [{"kind": "wait", "seconds": max(1.0, min(MAX_WAIT, until_night))}]


def trees_near(seed: str, x: int, z: int, radius: int) -> list[tuple[int, int, int]]:
    """Generated trees (trunk x, trunk z, ground height) within `radius` blocks of (x, z)."""
    found = []
    for cx in range((x - radius) // CHUNK, (x + radius) // CHUNK + 1):
        for cz in range((z - radius) // CHUNK, (z + radius) // CHUNK + 1):
            found.extend(tree for tree in trees_in_chunk(cx, cz, seed)
                         if math.hypot(tree[0] - x, tree[1] - z) <= radius)
    return found


def failed_columns(state: dict) -> set[tuple[int, int]]:
    """Columns where a recent step failed. Their trees are left alone while the failure is recent."""
    return {(entry["target"]["x"], entry["target"]["z"]) for entry in state["recent_actions"]
            if entry["result"] == "failed" and "target" in entry}


def standing_logs(grid: Grid, state: dict) -> list[Cell]:
    """The logs left in the nearest tree worth trying, lowest first, or [] when there is none."""
    x, _, z = as_cell(state["position"])
    skip = failed_columns(state)
    best: tuple[float, list[Cell]] | None = None
    for tx, tz, base in trees_near(state["world_seed"], x, z, TREE_SEARCH):
        if (tx, tz) in skip:
            continue
        logs = [(tx, y, tz) for y in range(base + 1, base + TRUNK_HEIGHT + 1) if grid.material(tx, y, tz) == LOG]
        distance = math.hypot(tx - x, tz - z)
        if logs and (best is None or distance < best[0]):
            best = (distance, logs)
    return best[1] if best else []


def wander_target(state: dict, clock: dict) -> list[int]:
    """A spot 48 blocks away, in a direction that changes each game day."""
    x, _, z = as_cell(state["position"])
    dx, dz = DIRECTIONS[clock["day_number"] % len(DIRECTIONS)]
    tx, tz = x + dx * WANDER_DISTANCE, z + dz * WANDER_DISTANCE
    return [tx, terrain_height(tx, tz, state["world_seed"]) + 1, tz]


def scripted_plan(state: dict, grid: Grid, at: float, clock: dict) -> list[dict]:
    """By day: planks from logs, else chop the nearest tree, else look further out. Rest as rest_plan."""
    rest = rest_plan(state, grid, at, clock)
    if rest[0]["kind"] == "sleep":
        return rest
    if state["inventory"].get(LOG, 0) > 0:
        return [{"kind": "craft", "recipe": "planks", "thought": "Logs make good planks."}]
    logs = standing_logs(grid, state)
    if logs:
        return [{"kind": "walk", "target": list(logs[0]), "reach": STAND_REACH, "thought": "That tree has good wood."},
                *({"kind": "mine", "target": list(log)} for log in logs)]
    return [{"kind": "walk", "target": wander_target(state, clock), "reach": WANDER_REACH,
             "thought": "No trees here. I'll look further out."}]
