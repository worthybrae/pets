"""Looking around: what the world near Mimo offers.

Trees come from worldgen (cheap, no block reads). Whether their logs still stand, ores and open
cells are read through a Grid, so Mimo's own edits count.
"""

from __future__ import annotations

import math

from backend.services.worldgen import trees_in_chunk
from backend.survival.grid import CHUNK

TREE_SEARCH = 24


def trees_near(seed: str, x: int, z: int, radius: int) -> list[tuple[int, int, int]]:
    """Generated trees (trunk x, trunk z, ground height) within `radius` blocks of (x, z)."""
    found = []
    for cx in range((x - radius) // CHUNK, (x + radius) // CHUNK + 1):
        for cz in range((z - radius) // CHUNK, (z + radius) // CHUNK + 1):
            found.extend(tree for tree in trees_in_chunk(cx, cz, seed)
                         if math.hypot(tree[0] - x, tree[1] - z) <= radius)
    return found
