"""Deterministic terrain shared in shape with the preview's chunk generator.

The original clearing stays flat enough to preserve worlds created before seeds
were introduced. Everything beyond it comes from the saved 64-bit seed.
"""

from __future__ import annotations

import math
from functools import lru_cache

LEGACY_WORLD_SEED = "13897963875510148821"
LEGACY_RADIUS = 192
TRANSITION_WIDTH = 48
SEA_LEVEL = 2
MASK = 0xFFFFFFFF
WORLD_MIN_Y = -8
WORLD_MAX_Y = 119
HOME_RADIUS = 12
STEPPING_STONES = {(-3, 2), (-2, 1), (3, 2), (4, 1)}
HOME_FLOWERS = ((-8, 0, "flower_orange"), (-7, 1, "flower_pink"), (-2, -5, "flower_yellow"),
                (1, -6, "flower_pink"), (8, 1, "flower_orange"), (7, 5, "flower_yellow"),
                (-1, 7, "flower_pink"), (3, 7, "flower_orange"))


@lru_cache(maxsize=64)
def seed_parts(seed: str) -> tuple[int, int]:
    value = int(seed) & ((1 << 64) - 1)
    return value & MASK, value >> 32


def hash32(x: int, y: int, z: int, seed: str, channel: int = 0) -> int:
    low, high = seed_parts(seed)
    value = (low ^ (high * 0x9E3779B1) ^ (x * 0x85EBCA6B) ^
             (y * 0x27D4EB2F) ^ (z * 0xC2B2AE35) ^ (channel * 0x165667B1)) & MASK
    value = ((value ^ (value >> 16)) * 0x7FEB352D) & MASK
    value = ((value ^ (value >> 15)) * 0x846CA68B) & MASK
    return (value ^ (value >> 16)) & MASK


def smooth(value: float) -> float:
    return value * value * (3 - 2 * value)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def to_int32(value: int) -> int:
    value &= MASK
    return value - (1 << 32) if value >= 1 << 31 else value


def legacy_hash(x: int, z: int) -> int:
    """The viewer's `Math.abs((x * 73856093) ^ (z * 19349663))`, with JavaScript's int32 XOR."""
    return abs(to_int32(x * 73856093) ^ to_int32(z * 19349663))


def js_round(value: float) -> int:
    """JavaScript Math.round: halves round up, unlike Python's round()."""
    return math.floor(value + 0.5)


def noise2(x: float, z: float, scale: float, seed: str, channel: int) -> float:
    gx, gz = math.floor(x / scale), math.floor(z / scale)
    fx, fz = smooth(x / scale - gx), smooth(z / scale - gz)
    sample = lambda dx, dz: hash32(gx + dx, 0, gz + dz, seed, channel) / MASK * 2 - 1
    return lerp(lerp(sample(0, 0), sample(1, 0), fx),
                lerp(sample(0, 1), sample(1, 1), fx), fz)


def noise3(x: float, y: float, z: float, scale: float, seed: str, channel: int) -> float:
    gx, gy, gz = math.floor(x / scale), math.floor(y / scale), math.floor(z / scale)
    fx, fy, fz = smooth(x / scale - gx), smooth(y / scale - gy), smooth(z / scale - gz)
    sample = lambda dx, dy, dz: hash32(gx + dx, gy + dy, gz + dz, seed, channel) / MASK * 2 - 1
    a = lerp(lerp(sample(0, 0, 0), sample(1, 0, 0), fx),
             lerp(sample(0, 0, 1), sample(1, 0, 1), fx), fz)
    b = lerp(lerp(sample(0, 1, 0), sample(1, 1, 0), fx),
             lerp(sample(0, 1, 1), sample(1, 1, 1), fx), fz)
    return lerp(a, b, fy)


def legacy_height(x: int, z: int) -> int:
    if math.hypot(x, z) < 17 or math.hypot(x - 48, z) < 27:
        return 0
    wave = math.sin(x * 0.085) + math.cos(z * 0.075) + math.sin((x + z) * 0.037)
    return 3 if wave > 1.65 else 2 if wave > 1.15 else 1 if wave > 0.65 else 0


@lru_cache(maxsize=131072)
def terrain_height(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> int:
    radius = math.hypot(x, z)
    if radius <= LEGACY_RADIUS:
        return legacy_height(x, z)
    broad = noise2(x, z, 96, seed, 1) * 6
    detail = noise2(x, z, 32, seed, 2) * 2
    ridge = max(0, noise2(x, z, 72, seed, 3)) ** 2 * 10
    generated = max(0, min(18, math.floor(3.5 + broad + detail + ridge)))
    if radius >= LEGACY_RADIUS + TRANSITION_WIDTH:
        return generated
    blend = smooth((radius - LEGACY_RADIUS) / TRANSITION_WIDTH)
    return math.floor(legacy_height(x, z) * (1 - blend) + generated * blend + 0.5)


@lru_cache(maxsize=131072)
def biome_at(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    if math.hypot(x, z) <= LEGACY_RADIUS:
        return "meadow"
    height = terrain_height(x, z, seed)
    if height >= 11:
        return "alpine"
    heat = noise2(x, z, 160, seed, 4)
    moisture = noise2(x, z, 160, seed, 5)
    if heat > 0.08 and moisture < -0.12:
        return "desert"
    if moisture > 0.08:
        return "forest"
    return "meadow"


def surface_material(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    biome = biome_at(x, z, seed)
    if biome == "desert":
        return "sand"
    if biome == "alpine":
        return "snow"
    if biome == "forest" and hash32(x, 0, z, seed, 6) % 7 == 0:
        return "moss"
    return "grass"


def cave_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
    if math.hypot(x, z) <= LEGACY_RADIUS or y <= -5 or y >= terrain_height(x, z, seed) - 2:
        return False
    return noise3(x, y, z, 11, seed, 7) > 0.27 and noise3(x, y, z, 5, seed, 8) > -0.12


def in_pond(x: int, z: int) -> bool:
    return ((x + 5) / 3.2) ** 2 + ((z - 4) / 2.4) ** 2 < 1


def home_ground(x: int, y: int, z: int) -> str | None:
    """Ground of Mimo's original home island, or None outside it."""
    distance = math.hypot(x, z)
    if distance > 10.4 + (legacy_hash(x, z) % 5) * 0.16:
        return None
    if y == 0:
        if 4 <= x <= 7 and -6 <= z <= -3:
            return "dirt_path"
        if (x, z) in STEPPING_STONES:
            return "dirt_path"
        if in_pond(x, z):
            return "water"
        shore = ((x + 5) / 4.2) ** 2 + ((z - 4) / 3.4) ** 2 < 1
        if shore or distance > 9.3:
            return "sand"
        walkway = 0 <= x <= 6 and abs(z + js_round(x * 0.55)) <= 0.6
        return "dirt_path" if walkway else "grass"
    if y == -1:
        return "sand" if distance > 9 else "dirt"
    if y == -2 and distance < 9.1:
        return "dirt"
    return None


def _home_blocks() -> dict[tuple[int, int, int], str]:
    """The cottage, big tree and flowers that used to exist only in the viewer."""
    blocks: dict[tuple[int, int, int], str] = {}
    for x in range(4, 8):
        for z in range(-6, -2):
            for y in range(1, 4):
                wall = x in (4, 7) or z in (-6, -3)
                door = x == 5 and z == -3 and y <= 2
                if wall and not door:
                    blocks[(x, y, z)] = "plaster"
    blocks[(5, 2, -6)] = "glass"
    blocks[(6, 2, -6)] = "glass"
    for x in range(3, 9):
        for z in range(-7, -1):
            blocks[(x, 4, z)] = "roof_tile"
            if 3 < x < 8 and -7 < z < -2:
                blocks[(x, 5, z)] = "roof_tile"
    for x in range(-8, -3):
        for z in range(-6, -1):
            spread = abs(x + 6) + abs(z + 4)
            if spread > 3:
                continue
            blocks[(x, 5, z)] = "leaves"
            if spread <= 2:
                blocks[(x, 6, z)] = "leaves"
    blocks[(-6, 7, -4)] = "leaves"
    for y in range(1, 6):
        blocks[(-6, y, -4)] = "oak_log"
    for x, z, flower in HOME_FLOWERS:
        blocks[(x, 1, z)] = flower
    return blocks


HOME_BLOCKS = _home_blocks()


def terrain_block(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """Terrain, water, caves and ores, before trees and plants are added."""
    if y <= -5:
        return "bedrock"
    height = terrain_height(x, z, seed)
    if math.hypot(x, z) <= LEGACY_RADIUS:
        home = home_ground(x, y, z)
        if home:
            return home
        if -4 <= y < -1:
            ore_seed = abs(x * 31 + z * 17 + y * 101)
            return "iron_ore" if ore_seed % 37 == 0 else "coal_ore" if ore_seed % 19 == 0 else "stone"
        if y == -1:
            return "dirt"
        if y == 0 and in_pond(x, z):
            return "water"
        if y == height:
            return "grass"
        if 0 <= y < height:
            return "dirt" if y >= height - 1 else "stone"
        return "air"
    if y > height:
        return "water" if y <= SEA_LEVEL else "air"
    if y == height:
        return surface_material(x, z, seed)
    if y >= height - 2:
        return "sand" if biome_at(x, z, seed) == "desert" else "dirt"
    if cave_at(x, y, z, seed):
        return "air"
    ore = hash32(x, y, z, seed, 9)
    if ore % 97 == 0:
        return "iron_ore"
    if ore % 61 == 0:
        return "coal_ore"
    if ore % 151 == 0:
        return "copper_ore"
    return "stone"


def _decoration_column(x: int, z: int, seed: str) -> bool:
    """Columns where the viewer has always allowed trees and flowers."""
    if not (3 <= x % 16 <= 12 and 3 <= z % 16 <= 12) or math.hypot(x, z) < 17:
        return False
    if terrain_height(x, z, seed) < SEA_LEVEL or biome_at(x, z, seed) in ("desert", "alpine"):
        return False
    mx, mz = x % 13, z % 13
    return not (min(mx, 13 - mx) < 5 and min(mz, 13 - mz) < 5)


def tree_base(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> int | None:
    """Ground height under a tree trunk at (x, z), or None when no tree grows there."""
    if not _decoration_column(x, z, seed):
        return None
    if math.hypot(x, z) <= LEGACY_RADIUS:
        grows = legacy_hash(x, z) % 257 == 0
    else:
        grows = hash32(x, 0, z, seed, 12) % (78 if biome_at(x, z, seed) == "forest" else 300) == 0
    return terrain_height(x, z, seed) if grows else None


@lru_cache(maxsize=4096)
def trees_in_chunk(cx: int, cz: int, seed: str = LEGACY_WORLD_SEED) -> tuple[tuple[int, int, int], ...]:
    """(x, z, ground height) of every tree rooted in a 16×16 chunk. Canopies never leave the chunk."""
    trees = []
    for x in range(cx * 16 + 3, cx * 16 + 13):
        for z in range(cz * 16 + 3, cz * 16 + 13):
            base = tree_base(x, z, seed)
            if base is not None:
                trees.append((x, z, base))
    return tuple(trees)


def is_leaf(dx: int, dy: int, dz: int) -> bool:
    """Canopy shape relative to a trunk's ground cell; dy counts up from the ground."""
    dx, dz = abs(dx), abs(dz)
    if dy == 5:
        return dx <= 2 and dz <= 2 and dx + dz <= 3
    return dy == 6 and dx + dz < 2


def tree_block(x: int, y: int, z: int, seed: str) -> str | None:
    trees = trees_in_chunk(x // 16, z // 16, seed)
    if any(x == tx and z == tz and base < y <= base + 4 for tx, tz, base in trees):
        return "oak_log"
    if any(is_leaf(x - tx, y - base, z - tz) for tx, tz, base in trees):
        return "leaves"
    return None


def plant_at(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """Flower or tall grass growing on top of the terrain at (x, z)."""
    if math.hypot(x, z) <= HOME_RADIUS:
        return None
    if _decoration_column(x, z, seed):
        if tree_base(x, z, seed) is not None:
            return None
        if hash32(x, 0, z, seed, 13) % 97 == 0:
            return "flower_orange" if legacy_hash(x + 1, z) % 2 else "flower_yellow"
    if math.hypot(x, z) > LEGACY_RADIUS and terrain_height(x, z, seed) < SEA_LEVEL:
        return None
    if surface_material(x, z, seed) not in ("grass", "moss"):
        return None
    return "tall_grass" if hash32(x, 0, z, seed, 14) % 19 == 0 else None


def decoration_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """Blocks that grow or stand on the terrain. Precedence: home, trunk, leaves, plant."""
    home = HOME_BLOCKS.get((x, y, z))
    if home:
        return home
    tree = tree_block(x, y, z, seed)
    if tree:
        return tree
    if y == terrain_height(x, z, seed) + 1:
        return plant_at(x, z, seed)
    return None


def block_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """The natural block at any cell: terrain first, then decorations in air."""
    terrain = terrain_block(x, y, z, seed)
    if terrain != "air":
        return terrain
    return decoration_at(x, y, z, seed) or "air"


# Older callers use this name.
base_material = block_at
