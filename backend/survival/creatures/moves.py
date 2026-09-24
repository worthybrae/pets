"""How creatures move: greedy one-block steps by the Grid's rules, seeded rolls, and where one is.

There is no path search. A creature steps to one of its 4 neighbours at a time by the rules
Mimo's paths follow (backend.survival.pathing.moves: level, one up with headroom, or down at most
3). A land creature never steps onto water (a cell whose floor is water), and a fish only ever
moves from water cell to water cell. Each move is a short timed path, like Mimo's walks, so the
viewer can replay it: the creature's row holds the cell the move ends in, and `where` says where
it is along the way at any moment. Chance comes from `roll`, fixed by the world seed, the
creature, its turn and a channel, so a world always does the same thing.
"""

from __future__ import annotations

import math

from backend.services.worldgen import hash32
from backend.survival.creatures.table import cell_of
from backend.survival.grid import Cell, Grid
from backend.survival.pathing import moves

WATER_SIDES = ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0))


def roll(seed: str, number: int, turn: int, channel: int) -> float:
    """A number in [0, 1) fixed by the world seed, the creature's id, its turn and the channel."""
    return hash32(number, turn, 0, seed, channel) / 4294967296


def steps(grid: Grid, cell: Cell, water: bool) -> list[Cell]:
    """The cells a creature can step to from `cell`: water cells around a fish, else the cells Mimo
    could walk to in one move that are not on the water."""
    if water:
        x, y, z = cell
        return [(x + dx, y + dy, z + dz) for dx, dy, dz in WATER_SIDES if grid.water((x + dx, y + dy, z + dz))]
    return [step for step in moves(grid, cell) if not grid.swimming(step)]


def timed(start: Cell, cells: list[Cell], at: float, seconds: float) -> list[dict]:
    """The start and each cell after it with the server time the creature gets there."""
    path = [{"x": start[0], "y": start[1], "z": start[2], "at": round(at, 3)}]
    for number, cell in enumerate(cells, start=1):
        path.append({"x": cell[0], "y": cell[1], "z": cell[2], "at": round(at + number * seconds, 3)})
    return path


def where(creature: dict, at: float) -> Cell:
    """The cell a creature is in at `at`: the last cell of its move reached by then (the move's
    first cell before it starts), or where it stands when it has no move."""
    path = creature["state"].get("path")
    if not path:
        return cell_of(creature)
    spot = path[0]
    for entry in path:
        if entry["at"] <= at:
            spot = entry
    return spot["x"], spot["y"], spot["z"]


def heading(start: Cell, end: Cell, fallback: float) -> float:
    """Radians around +y from `start` toward `end` (0 faces +z, as in the viewer), or `fallback`."""
    dx, dz = end[0] - start[0], end[2] - start[2]
    return fallback if dx == 0 and dz == 0 else math.atan2(dx, dz)


def move(creature: dict, cells: list[Cell], at: float, seconds: float, pose: str) -> float:
    """Start a move through `cells` from where the creature is at `at`, `seconds` per block, in
    `pose`. The row moves to the last cell at once; returns when the move ends."""
    start = where(creature, at)
    path = timed(start, cells, at, seconds)
    end = cells[-1] if cells else start
    creature["x"], creature["y"], creature["z"] = map(float, end)
    before = cells[-2] if len(cells) > 1 else start
    creature["heading"] = heading(before, end, creature["heading"])
    creature["state"].update(path=path, pose=pose)
    return path[-1]["at"]
