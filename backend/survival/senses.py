"""Looking around: what the world near Mimo offers.

Trees come from worldgen (cheap, no block reads). Whether their logs still stand, ores and open
cells are read through a Grid, so Mimo's own edits count.
"""

from __future__ import annotations

import math

from backend.services.worldgen import trees_in_chunk
from backend.survival.grid import CHUNK, Cell, Grid

TREE_SEARCH = 24
TRUNK_HEIGHT = 4
LOG = "oak_log"
ORES = ("coal_ore", "iron_ore", "copper_ore")


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
    columns = set()
    for entry in state.get("recent_actions", []):
        target = entry.get("target")
        if entry.get("result") == "failed" and isinstance(target, dict) and "x" in target and "z" in target:
            columns.add((target["x"], target["z"]))
    return columns


def standing_logs(grid: Grid, seed: str, here: Cell, skip: set[tuple[int, int]] | frozenset = frozenset(),
                  radius: int = TREE_SEARCH) -> list[Cell]:
    """The logs still standing in the nearest tree worth trying, lowest first; [] when there is none."""
    x, _, z = here
    best: tuple[float, list[Cell]] | None = None
    for tx, tz, base in trees_near(seed, x, z, radius):
        if (tx, tz) in skip:
            continue
        logs = [(tx, y, tz) for y in range(base + 1, base + TRUNK_HEIGHT + 1) if grid.material(tx, y, tz) == LOG]
        distance = math.hypot(tx - x, tz - z)
        if logs and (best is None or distance < best[0]):
            best = (distance, logs)
    return best[1] if best else []


def ores_around(grid: Grid, cell: Cell) -> list[tuple[Cell, str]]:
    """Ore blocks among the 26 cells around `cell`: what mining it uncovered."""
    x, y, z = cell
    found = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if dx == dy == dz == 0:
                    continue
                near = (x + dx, y + dy, z + dz)
                material = grid.material(*near)
                if material in ORES:
                    found.append((near, material))
    return found
