"""Where a new life starts: 3,000-6,000 blocks from the origin, on dry grass or moss in a meadow
or forest, with a tree within 24 blocks. The search spirals outward from a random point."""

from __future__ import annotations

import math
import random
from typing import Iterator

from backend.services.blocks import is_replaceable
from backend.services.worldgen import SEA_LEVEL, biome_at, block_at, surface_material, terrain_height, trees_in_chunk

MIN_DISTANCE = 3000
MAX_DISTANCE = 6000
TREE_REACH = 24
SEARCH_STEP = 4
MAX_RINGS = 200
MAX_ATTEMPTS = 8
SPAWN_BIOMES = ("meadow", "forest")
SPAWN_SURFACES = ("grass", "moss")
CHUNK = 16


def tree_near(x: int, z: int, seed: str, reach: int = TREE_REACH) -> bool:
    for cx in range((x - reach) // CHUNK, (x + reach) // CHUNK + 1):
        for cz in range((z - reach) // CHUNK, (z + reach) // CHUNK + 1):
            if any(math.hypot(tx - x, tz - z) <= reach for tx, tz, _ in trees_in_chunk(cx, cz, seed)):
                return True
    return False


def spawn_fits(x: int, z: int, seed: str) -> bool:
    if not MIN_DISTANCE <= math.hypot(x, z) <= MAX_DISTANCE:
        return False
    height = terrain_height(x, z, seed)
    if height < SEA_LEVEL:
        return False
    if biome_at(x, z, seed) not in SPAWN_BIOMES or surface_material(x, z, seed) not in SPAWN_SURFACES:
        return False
    for y in (height + 1, height + 2):
        here = block_at(x, y, z, seed)
        if here == "water" or not is_replaceable(here):
            return False
    return tree_near(x, z, seed)


def ring_points(cx: int, cz: int, ring: int, step: int) -> Iterator[tuple[int, int]]:
    """Points on the square ring `ring` steps out from (cx, cz), each corner once."""
    if ring == 0:
        yield cx, cz
        return
    reach = ring * step
    for i in range(-ring, ring):
        yield cx + i * step, cz - reach
    for i in range(-ring, ring):
        yield cx + reach, cz + i * step
    for i in range(-ring, ring):
        yield cx - i * step, cz + reach
    for i in range(-ring, ring):
        yield cx - reach, cz - i * step


def find_spawn(seed: str, rng: random.Random) -> dict:
    """The cell Mimo stands in at birth: {"x", "y", "z"} with y one above the ground."""
    for _ in range(MAX_ATTEMPTS):
        angle = rng.uniform(0, 2 * math.pi)
        distance = rng.uniform(MIN_DISTANCE, MAX_DISTANCE)
        start_x, start_z = round(math.cos(angle) * distance), round(math.sin(angle) * distance)
        for ring in range(MAX_RINGS + 1):
            for x, z in ring_points(start_x, start_z, ring, SEARCH_STEP):
                if spawn_fits(x, z, seed):
                    return {"x": x, "y": terrain_height(x, z, seed) + 1, "z": z}
    raise RuntimeError("No spawn point fits this world seed")
