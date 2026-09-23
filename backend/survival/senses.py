"""Looking around: what the world near Mimo offers.

Trees, wild plants and water come from worldgen (cheap, no block reads; the plants of a chunk
are worked out once and kept). Whether they are still there, ores and open cells are read
through a Grid, so Mimo's own edits count, and so do the trees and food that grew back.
"""

from __future__ import annotations

import math
from functools import lru_cache

from backend.services.worldgen import SEA_LEVEL, plant_at, terrain_height, trees_in_chunk
from backend.survival.grid import CHUNK, Cell, Grid
from backend.survival.steps import REACH

TREE_SEARCH = 24
TRUNK_HEIGHT = 4
LOG = "oak_log"
ORES = ("coal_ore", "iron_ore", "copper_ore")
FOOD_SIGHT = 24
WATER_SIGHT = 24
# Wild food Mimo can pick (block names; a mushroom's item has the same name).
PICKABLE = ("berry_bush_ripe", "brown_mushroom", "red_mushroom")
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
FAILED_REACH = 4.0


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
    """The logs still standing in the nearest tree worth trying, lowest first; [] when there is none.
    Trees grown from saplings count too: their logs are placed blocks."""
    x, _, z = here
    trunks: dict[tuple[int, int], set[Cell]] = {}
    for tx, tz, base in trees_near(seed, x, z, radius):
        trunks.setdefault((tx, tz), set()).update((tx, y, tz) for y in range(base + 1, base + TRUNK_HEIGHT + 1))
    for cell, _ in grid.placed_cells(x, z, radius, (LOG,)):
        trunks.setdefault((cell[0], cell[2]), set()).add(cell)
    best: tuple[float, tuple[int, int], list[Cell]] | None = None
    for (tx, tz), cells in trunks.items():
        if (tx, tz) in skip:
            continue
        logs = sorted((cell for cell in cells if grid.material(*cell) == LOG), key=lambda cell: cell[1])
        distance = math.hypot(tx - x, tz - z)
        if logs and (best is None or (distance, (tx, tz)) < best[:2]):
            best = (distance, (tx, tz), logs)
    return best[2] if best else []


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


@lru_cache(maxsize=4096)
def plants_in_chunk(cx: int, cz: int, seed: str) -> tuple[tuple[Cell, str], ...]:
    """Every natural surface plant (flowers, tall grass, berry bushes, mushrooms) rooted in a chunk."""
    found = []
    for x in range(cx * CHUNK, cx * CHUNK + CHUNK):
        for z in range(cz * CHUNK, cz * CHUNK + CHUNK):
            plant = plant_at(x, z, seed)
            if plant:
                found.append(((x, terrain_height(x, z, seed) + 1, z), plant))
    return tuple(found)


def natural_plants(seed: str, x: int, z: int, radius: float, kinds: tuple[str, ...]) -> list[Cell]:
    """Cells where worldgen grew one of `kinds` within `radius` blocks of (x, z)."""
    found = []
    for cx in range(math.floor((x - radius) / CHUNK), math.floor((x + radius) / CHUNK) + 1):
        for cz in range(math.floor((z - radius) / CHUNK), math.floor((z + radius) / CHUNK) + 1):
            found.extend(cell for cell, plant in plants_in_chunk(cx, cz, seed)
                         if plant in kinds and math.hypot(cell[0] - x, cell[2] - z) <= radius)
    return found


def by_distance(cells, here: Cell) -> list[Cell]:
    return sorted(cells, key=lambda cell: (math.dist(cell, here), cell))


def food_near(grid: Grid, seed: str, here: Cell, radius: float = FOOD_SIGHT, avoid=()) -> list[Cell]:
    """Ripe food Mimo can pick within `radius`, nearest first: wild bushes and mushrooms and the ones
    that grew back, as they stand now. Food in `avoid` (known to be poisonous) is left out."""
    x, _, z = here
    wanted = tuple(block for block in PICKABLE if block not in avoid)
    cells = set(natural_plants(seed, x, z, radius, PICKABLE))
    cells.update(cell for cell, _ in grid.placed_cells(x, z, radius, PICKABLE))
    return by_distance((cell for cell in cells if grid.material(*cell) in wanted), here)


def grass_near(grid: Grid, seed: str, here: Cell, radius: float) -> list[Cell]:
    """Wild tall grass still standing within `radius`, nearest first (breaking it may give seeds)."""
    x, _, z = here
    return by_distance((cell for cell in natural_plants(seed, x, z, radius, ("tall_grass",))
                        if grid.material(*cell) == "tall_grass"), here)


def shores_near(grid: Grid, seed: str, here: Cell, radius: float = WATER_SIGHT) -> list[tuple[Cell, Cell]]:
    """(cell to stand on, water cell within reach of it) along natural water within `radius`, the
    nearest standing cell first. Natural water lies where the ground is below sea level."""
    x, _, z = here
    reach = math.ceil(radius)
    found: dict[Cell, Cell] = {}
    for wx in range(x - reach, x + reach + 1):
        for wz in range(z - reach, z + reach + 1):
            if math.hypot(wx - x, wz - z) > radius or terrain_height(wx, wz, seed) >= SEA_LEVEL:
                continue
            water = (wx, SEA_LEVEL, wz)
            if not grid.water(water):
                continue
            for dx, dz in SIDES:
                ground = terrain_height(wx + dx, wz + dz, seed)
                stand = (wx + dx, ground + 1, wz + dz)
                if (ground >= SEA_LEVEL and stand not in found and math.dist(stand, water) <= REACH
                        and grid.standable(stand)):
                    found[stand] = water
    return [(stand, found[stand]) for stand in by_distance(found, here)]


def near_failure(state: dict, cell: Cell, radius: float = FAILED_REACH) -> bool:
    """A step failed lately within `radius` blocks (horizontally) of `cell`: somewhere Mimo could
    not get to, so the cells around it are left alone for a while too."""
    return any(math.hypot(cell[0] - x, cell[2] - z) <= radius for x, z in failed_columns(state))
