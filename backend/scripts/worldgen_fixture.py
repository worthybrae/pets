"""Write shared/worldgen-fixture.json: sampled cells both worldgen ports must agree on.

Run from the repo root after any worldgen change:

    python3 -m backend.scripts.worldgen_fixture
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from backend.services.worldgen import (
    LEGACY_WORLD_SEED, SEA_LEVEL, biome_at, block_at, cave_plant, plant_at, plant_stack, region_openings,
    rocks_in_chunk, swamp_pool, terrain_height, tree_kind, trees_in_chunk,
)

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "shared" / "worldgen-fixture.json"
GENERATED_SEED = "123456789123456789"
SEEDS = [LEGACY_WORLD_SEED, GENERATED_SEED]
LEGACY_CHUNKS = [(cx, cz) for cz in range(2, 12) for cx in range(2, 12)]
WILD_CHUNKS = [(cx, cz) for cz in range(-15, 15) for cx in range(16, 46)]
WILD_NEG_CHUNKS = [(cx, cz) for cz in range(-15, 15) for cx in range(-46, -16)]
# Survival lives spawn 3,000-6,000 blocks out and may roam to the +/-30,000 limit.
FAR_CHUNKS = [(cx, cz) for cz in range(-8, 8) for cx in range(250, 270)]
FAR_LIMIT = 30000
WILD_FOOD = ("berry_bush_ripe", "brown_mushroom", "red_mushroom")
# L3: trees of each wood, the taller plants and fruit, swamp pools and frozen lakes.
KIND_CHUNKS = [(cx, cz) for cz in range(-30, 30) for cx in range(16, 80)]
STACKS = ("cactus", "sugar_cane", "dead_bush", "fern", "pumpkin", "melon")
NEW_BIOMES = ("taiga", "swamp", "birch_forest")
DEEP = ("gold_ore", "diamond_ore", "water", "lava", "gravel", "granite", "andesite", "diorite", "ashstone")


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


def _wild_food(seed: str, count: int) -> list[tuple[int, int]]:
    """Columns with a berry bush or a mushroom on generated land."""
    found = []
    for x in range(250, 1250):
        for z in range(-60, 60, 2):
            if plant_at(x, z, seed) in WILD_FOOD:
                found.append((x, z))
                if len(found) == count:
                    return found
    return found


def _cave_plants(seed: str, count: int) -> list[tuple[int, int, int]]:
    """Mushrooms on cave floors."""
    found = []
    for x in range(250, 700, 3):
        for z in range(-100, 100, 3):
            for y in range(-4, terrain_height(x, z, seed) - 2):
                if cave_plant(x, y, z, seed):
                    found.append((x, y, z))
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


def _kind_trees(seed: str, kind: str, count: int) -> list[tuple[int, int, int]]:
    """Generated trees of one wood (oak, birch or spruce)."""
    found = []
    for cx, cz in KIND_CHUNKS:
        for tree in trees_in_chunk(cx, cz, seed):
            if tree_kind(tree[0], tree[1], seed) == kind:
                found.append(tree)
                if len(found) == count:
                    return found
    return found


def _features(seed: str, count: int) -> list[tuple[int, int]]:
    """Columns with each of the taller plants and fruit, a swamp pool or a frozen lake, `count` of each."""
    seen: dict[str, int] = {}
    found = []
    for x in range(250, 1250):
        for z in range(-60, 60, 2):
            stack = plant_stack(x, z, seed)
            kind = stack[0] if stack and stack[0] in STACKS else None
            if kind is None and swamp_pool(x, z, seed):
                kind = "pool"
            elif kind is None and terrain_height(x, z, seed) < SEA_LEVEL and biome_at(x, z, seed) == "taiga":
                kind = "ice"
            if kind is not None and seen.get(kind, 0) < count:
                seen[kind] = seen.get(kind, 0) + 1
                found.append((x, z))
                if len(seen) == len(STACKS) + 2 and all(value == count for value in seen.values()):
                    return found
    return found


def _deep(seed: str, count: int) -> list[tuple[int, int, int]]:
    """Underground cells of gold, diamond, a cave lake, lava and each kind of stone, `count` of each."""
    seen: dict[str, int] = {}
    found = []
    for x in range(250, 700, 3):
        for z in range(-100, 100, 3):
            for y in range(-4, terrain_height(x, z, seed) - 2):
                block = block_at(x, y, z, seed)
                if block in DEEP and seen.get(block, 0) < count:
                    seen[block] = seen.get(block, 0) + 1
                    found.append((x, y, z))
                    if len(seen) == len(DEEP) and all(value == count for value in seen.values()):
                        return found
    return found


def _entrances(seed: str, count: int) -> list[dict]:
    """The carved columns of `count` sinkholes and `count` hillside mouths."""
    found, seen = [], {}
    for rx in range(4, 40):
        for rz in range(-20, 20):
            kind, spans = region_openings(rx, rz, seed)
            if kind and seen.get(kind, 0) < count:
                seen[kind] = seen.get(kind, 0) + 1
                found.append(spans)
    return found


def _rocks(seed: str, count: int) -> list[tuple[int, int]]:
    """The middle columns of `count` boulders and `count` outcrops."""
    found, seen = [], {}
    for cx in range(16, 120):
        for cz in range(-40, 40):
            for x, z, kind, _, _ in rocks_in_chunk(cx, cz, seed):
                if seen.get(kind, 0) < count:
                    seen[kind] = seen.get(kind, 0) + 1
                    found.append((x, z))
    return found


def sample_cells() -> list[tuple[str, int, int, int]]:
    """Home clearing, tree canopies, plants, rare biomes and random cells for both seeds."""
    cells = {(LEGACY_WORLD_SEED, x, y, z) for x in range(-12, 13) for z in range(-12, 13) for y in range(-2, 8)}
    rng = random.Random(7)
    for seed in SEEDS:
        trees = _trees(seed, LEGACY_CHUNKS, 3) + _trees(seed, WILD_CHUNKS, 3, "forest") + _trees(seed, WILD_NEG_CHUNKS, 3)
        for tx, tz, base in trees:
            cells |= {(seed, tx + dx, base + dy, tz + dz)
                      for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 8)}
        for x, z in _plants(seed, 20) + _wild_food(seed, 40):
            height = terrain_height(x, z, seed)
            cells |= {(seed, x, height, z), (seed, x, height + 1, z)}
        for x, y, z in _cave_plants(seed, 12):
            cells |= {(seed, x, y, z), (seed, x, y - 1, z)}
        for biome in ("desert", "alpine") + NEW_BIOMES:
            cells |= {(seed, x, y, z) for x, y, z in _biome_patch(seed, biome)}
        for kind in ("oak", "birch", "spruce"):
            for tx, tz, base in _kind_trees(seed, kind, 2):
                cells |= {(seed, tx + dx, base + dy, tz + dz)
                          for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 9)}
        for spans in _entrances(seed, 2):
            for (x, z), (low, _) in spans.items():
                cells |= {(seed, x, y, z) for y in range(low - 1, terrain_height(x, z, seed) + 2)}
        for rx, rz in _rocks(seed, 3):
            cells |= {(seed, rx + dx, terrain_height(rx + dx, rz + dz, seed) + dy, rz + dz)
                      for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 5)}
        for x, y, z in _deep(seed, 3):
            cells |= {(seed, x + dx, y + dy, z + dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)}
        for x, z in _features(seed, 3):
            height = terrain_height(x, z, seed)
            cells |= {(seed, x, height + dy, z) for dy in range(-2, 5)}
        for _ in range(1500):
            cells.add((seed, rng.randint(-700, 700), rng.randint(-8, 40), rng.randint(-700, 700)))
    far = random.Random(11)
    for seed in SEEDS:
        for tx, tz, base in _trees(seed, FAR_CHUNKS, 2):
            cells |= {(seed, tx + dx, base + dy, tz + dz)
                      for dx in range(-3, 4) for dz in range(-3, 4) for dy in range(0, 8)}
        for _ in range(600):
            x = far.choice((-1, 1)) * far.randint(2500, FAR_LIMIT)
            z = far.randint(-FAR_LIMIT, FAR_LIMIT)
            cells.add((seed, x, far.randint(-8, terrain_height(x, z, seed) + 8), z))
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
