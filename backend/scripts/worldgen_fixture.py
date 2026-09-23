"""Write shared/worldgen-fixture.json: sampled cells both worldgen ports must agree on.

Run from the repo root after any worldgen change:

    python3 -m backend.scripts.worldgen_fixture
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from backend.services.worldgen import (
    LEGACY_WORLD_SEED, biome_at, block_at, plant_at, terrain_height, trees_in_chunk,
)

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "shared" / "worldgen-fixture.json"
GENERATED_SEED = "123456789123456789"
SEEDS = [LEGACY_WORLD_SEED, GENERATED_SEED]
LEGACY_CHUNKS = [(cx, cz) for cz in range(2, 12) for cx in range(2, 12)]
WILD_CHUNKS = [(cx, cz) for cz in range(-15, 15) for cx in range(16, 46)]
WILD_NEG_CHUNKS = [(cx, cz) for cz in range(-15, 15) for cx in range(-46, -16)]


def _trees(seed: str, chunks: list[tuple[int, int]], count: int,
           biome: str | None = None) -> list[tuple[int, int, int]]:
    found = []
    for cx, cz in chunks:
        for tree in trees_in_chunk(cx, cz, seed):
            if biome is None or biome_at(tree[0], tree[1], seed) == biome:
                found.append(tree)
                if len(found) == count:
                    return found
    return found


def _plants(seed: str, count: int) -> list[tuple[int, int]]:
    found = []
    for x in range(250, 900):
        for z in range(-40, 40, 3):
            if plant_at(x, z, seed):
                found.append((x, z))
                if len(found) == count:
                    return found
    return found


def _biome_patch(seed: str, biome: str) -> list[tuple[int, int, int]]:
    for x in range(250, 1250, 25):
        for z in range(-500, 500, 25):
            if biome_at(x, z, seed) == biome:
                return [(x + dx, y, z + dz) for dx in range(4) for dz in range(4)
                        for y in range(terrain_height(x + dx, z + dz, seed) - 2,
                                       terrain_height(x + dx, z + dz, seed) + 2)]
    return []


def sample_cells() -> list[tuple[str, int, int, int]]:
    """Home clearing, tree canopies, plants, rare biomes and random cells for both seeds."""
    cells = {(LEGACY_WORLD_SEED, x, y, z) for x in range(-12, 13) for z in range(-12, 13) for y in range(-2, 8)}
    rng = random.Random(7)
    for seed in SEEDS:
        trees = _trees(seed, LEGACY_CHUNKS, 3) + _trees(seed, WILD_CHUNKS, 3, "forest") + _trees(seed, WILD_NEG_CHUNKS, 3)
        for tx, tz, base in trees:
            cells |= {(seed, tx + dx, base + dy, tz + dz)
                      for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 8)}
        for x, z in _plants(seed, 20):
            height = terrain_height(x, z, seed)
            cells |= {(seed, x, height, z), (seed, x, height + 1, z)}
        for biome in ("desert", "alpine"):
            cells |= {(seed, x, y, z) for x, y, z in _biome_patch(seed, biome)}
        for _ in range(1500):
            cells.add((seed, rng.randint(-700, 700), rng.randint(-8, 40), rng.randint(-700, 700)))
    return sorted(cells, key=lambda cell: (SEEDS.index(cell[0]), cell[1], cell[2], cell[3]))


def build_fixture() -> dict:
    cells = sample_cells()
    names = [block_at(x, y, z, seed) for seed, x, y, z in cells]
    materials = sorted(set(names))
    index = {name: position for position, name in enumerate(materials)}
    return {
        "seeds": SEEDS,
        "materials": materials,
        "cells": [[SEEDS.index(seed), x, y, z, index[name]] for (seed, x, y, z), name in zip(cells, names)],
    }


def main() -> None:
    fixture = build_fixture()
    FIXTURE_PATH.write_text(json.dumps(fixture, separators=(",", ":")) + "\n")
    print(f"Wrote {len(fixture['cells'])} cells to {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
