"""Deterministic terrain shared in shape with the preview's chunk generator.

The original clearing stays flat enough to preserve worlds created before seeds
were introduced. Everything beyond it comes from the saved 64-bit seed.
"""

from __future__ import annotations

import math
import types
from collections.abc import Mapping
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
# Wild food on generated land: one berry bush per BUSH_RARITY meadow or forest-edge columns, one
# mushroom per MUSHROOM_RARITY forest columns and per CAVE_MUSHROOM_RARITY cave floor cells.
FOREST_EDGE = 0.16  # forest moisture below this is the forest's edge
BUSH_RARITY = 97
MUSHROOM_RARITY = 67
CAVE_MUSHROOM_RARITY = 29
# L3, the bigger world: taiga, swamp and birch forest, with their trees, plants, snow, ice, mud and
# pools. Heights never change, and the legacy clearing keeps exactly what it always had.
TAIGA_HEAT = -0.45  # colder than this is taiga
SWAMP_WET = 0.45  # wetter than this on low ground is swamp
SWAMP_TOP = SEA_LEVEL + 1  # swamps lie on ground no higher than this
BIRCH_HEAT = 0.3  # a forest warmer than this is a birch forest
PEAK = 15  # alpine ground this high is bare snow
TREE_RARITY = {"forest": 78, "birch_forest": 70, "taiga": 60, "swamp": 150}  # one tree per this many columns
MEADOW_TREES = 300
TREE_LOGS = {"oak": "oak_log", "birch": "birch_log", "spruce": "spruce_log"}
TREE_LEAVES = {"oak": "leaves", "birch": "birch_leaves", "spruce": "spruce_leaves"}
CANOPY_TOP = 7  # the highest leaf of any tree, above its ground
RIM_MARGIN = 3  # canopies reach at most this far; a trunk this close past the clearing's edge keeps
                # its pre-L3 rules, so its leaves never change a block the clearing already had
CACTUS_RARITY = 47
CANE_RARITY = 11  # on a shore; three times likelier in a swamp
DEAD_BUSH_RARITY = 53
FERN_RARITY = 5
FRUIT_RARITY = 421  # a pumpkin or melon patch, on meadow and forest grass
FRUIT_BIOMES = ("meadow", "forest", "birch_forest")
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
# L3 underground: bigger, taller caves, lakes and lava in them, seams of other stone, gold and diamond.
CAVE_SCALE = 13  # blocks across the cave network's noise (it was 11)
CAVE_STRETCH = 0.6  # the network's noise runs this much slower upward, so caves stand taller
CAVE_OPEN = 0.22  # the network is open above this (it was 0.27)
CAVE_ROOM = -0.15  # and its rooms are carved where the finer noise is above this (it was -0.12)
LAKE_LEVEL = -2  # in a lake region, cave cells this low are water
LAVA_LEVEL = -4  # in a lava region, the lowest cave cells (just above bedrock) are lava
GOLD_RARITY = 181  # stone cells per gold ore, at y 0 and below
GOLD_DEPTH = 0
DIAMOND_RARITY = 331  # stone cells per diamond ore, at y -3 and below
DIAMOND_DEPTH = -3
ASH_DEPTH = -2  # ashstone seams lie this deep and deeper
VARIANTS = ("granite", "andesite", "diorite")
# L3 on the surface: cave entrances open to the sky (sinkholes and hillside mouths), boulders, outcrops.
OPENING_REGION = 64  # blocks on a side; a region holds one entrance at most
MOUTH_LENGTH = 12
MOUTH_TRIES = 6  # spots a region tries for a hillside mouth
OUTCROP_GROUND = 8  # outcrops crown ground at least this high
BOULDERS = {"desert": "sandstone", "meadow": "andesite", "alpine": "stone"}  # else mossy cobblestone
OUTCROPS = {"desert": "sandstone", "taiga": "andesite", "birch_forest": "diorite", "alpine": "granite"}  # else stone
EMPTY_SPANS: Mapping[tuple[int, int], tuple[int, int]] = types.MappingProxyType({})


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
    if heat < TAIGA_HEAT:
        return "taiga"
    if moisture > SWAMP_WET and height <= SWAMP_TOP:
        return "swamp"
    if moisture > 0.08:
        return "birch_forest" if heat > BIRCH_HEAT else "forest"
    return "meadow"


@lru_cache(maxsize=131072)
def surface_material(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    biome = biome_at(x, z, seed)
    if biome == "desert":
        return "sand"
    height = terrain_height(x, z, seed)
    if height < SEA_LEVEL and math.hypot(x, z) > LEGACY_RADIUS:
        return "gravel" if noise2(x, z, 10, seed, 87) > -0.1 else "sand"  # lake and river beds
    if biome == "alpine":
        if height >= PEAK:
            return "snow_block"
        return "gravel" if noise2(x, z, 9, seed, 89) > 0.35 else "snow"  # scree
    if biome == "forest" and hash32(x, 0, z, seed, 6) % 7 == 0:
        return "moss"
    if biome == "taiga":
        if noise2(x, z, 11, seed, 89) > 0.5:
            return "gravel"
        if noise2(x, z, 9, seed, 18) > 0.15:
            return "snow"
    if biome == "swamp" and noise2(x, z, 7, seed, 19) > 0.05:
        return "mud"
    if shore(x, z, seed) and noise2(x, z, 7, seed, 88) > 0.3:
        return "gravel"
    return "grass"


@lru_cache(maxsize=131072)
def shore(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
    """Land level with the lakes right beside one (never in the legacy clearing)."""
    return (math.hypot(x, z) > LEGACY_RADIUS and terrain_height(x, z, seed) == SEA_LEVEL
            and any(terrain_height(x + dx, z + dz, seed) < SEA_LEVEL for dx, dz in SIDES))


@lru_cache(maxsize=131072)
def swamp_pool(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
    """A shallow swamp pool: one block of water where swamp ground lies level with the lakes."""
    return (terrain_height(x, z, seed) == SEA_LEVEL and biome_at(x, z, seed) == "swamp"
            and noise2(x, z, 6, seed, 20) > 0.1)


def cave_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
    if math.hypot(x, z) <= LEGACY_RADIUS or y <= -5 or y >= terrain_height(x, z, seed) - 2:
        return False
    return (noise3(x, y * CAVE_STRETCH, z, CAVE_SCALE, seed, 7) > CAVE_OPEN
            and noise3(x, y, z, 6, seed, 8) > CAVE_ROOM)


def cave_fill(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """What fills an open cave cell: water low down in a lake region, lava on the lowest floor of a
    lava region, else air."""
    if y <= LAKE_LEVEL and noise2(x, z, 40, seed, 27) > 0.3:
        return "water"
    if y == LAVA_LEVEL and noise2(x, z, 32, seed, 28) > 0.25:
        return "lava"
    return "air"


def gravel_floor(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
    """Gravel in patches on cave floors: the rock right under an open cave cell of air."""
    return noise2(x, z, 8, seed, 90) > 0.1 and cave_at(x, y + 1, z, seed) and cave_fill(x, y + 1, z, seed) == "air"


def stone_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """The rock of a solid cell underground: ashstone in deep seams, blobs of granite, andesite or
    diorite (one kind to a blob region), else stone."""
    if y <= ASH_DEPTH and noise3(x, y, z, 9, seed, 29) > 0.35:
        return "ashstone"
    if noise3(x, y, z, 8, seed, 80) > 0.38:
        return VARIANTS[hash32(x // 24, y // 8, z // 24, seed, 81) % len(VARIANTS)]
    return "stone"


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


@lru_cache(maxsize=4096)
def region_openings(rx: int, rz: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, Mapping[tuple[int, int], tuple[int, int]]]:
    """The cave entrance of a 64x64 region, if it has one: its kind ("sinkhole", "mouth", or "" for
    none) and the span of air it carves in each of its columns, {(x, z): (lowest y, highest y)}. Two
    regions in eight try for a sinkhole and three for a hillside mouth (at up to 6 spots, the first on
    a slope); none near the legacy clearing or by the water. The mapping is read-only, since the cache
    hands the same object to every caller."""
    x0, z0 = rx * OPENING_REGION, rz * OPENING_REGION
    if math.hypot(x0 + 32, z0 + 32) <= LEGACY_RADIUS + OPENING_REGION:
        return "", EMPTY_SPANS
    roll = hash32(rx, 0, rz, seed, 82)
    if roll % 8 < 2:
        cx, cz = x0 + 12 + (roll >> 8) % 40, z0 + 12 + (roll >> 16) % 40
        ground = terrain_height(cx, cz, seed)
        spans = _sinkhole(cx, cz, ground, seed) if ground > SEA_LEVEL else {}
        return ("sinkhole" if spans else ""), types.MappingProxyType(spans)
    if roll % 8 < 5:
        for attempt in range(MOUTH_TRIES):
            spot = hash32(rx, attempt, rz, seed, 86)
            cx, cz = x0 + 12 + spot % 40, z0 + 12 + (spot >> 8) % 40
            ground = terrain_height(cx, cz, seed)
            spans = _mouth(cx, cz, ground, seed) if ground > SEA_LEVEL else {}
            if spans:
                return "mouth", types.MappingProxyType(spans)
    return "", EMPTY_SPANS


def _sinkhole(cx: int, cz: int, ground: int, seed: str) -> dict:
    """A round shaft five across from the surface down 9 to 13 blocks (never below y -3); none next
    to water."""
    bottom = max(-3, ground - 9 - hash32(cx, 1, cz, seed, 83) % 5)
    spans = {}
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            if dx * dx + dz * dz <= 5:
                top = terrain_height(cx + dx, cz + dz, seed)
                if top <= SEA_LEVEL:
                    return {}
                spans[(cx + dx, cz + dz)] = (bottom, top)
    return spans


def _mouth(cx: int, cz: int, ground: int, seed: str) -> dict:
    """A tunnel into a hillside from the foot of its steepest rise (the ground 8 blocks on is higher):
    2 wide, up to 3 tall, its floor sinking a block every 2 for 12 blocks; open to the sky at first,
    roofed further in. None where no side rises."""
    best = None
    for dx, dz in SIDES:
        rise = terrain_height(cx + 8 * dx, cz + 8 * dz, seed) - ground
        if rise >= 1 and (best is None or rise > best[0]):
            best = (rise, dx, dz)
    if best is None:
        return {}
    _, dx, dz = best
    spans = {}
    for step in range(MOUTH_LENGTH):
        floor = ground + 1 - step // 2
        for side in (0, 1):
            x, z = cx + step * dx - side * dz, cz + step * dz + side * dx
            height = terrain_height(x, z, seed)
            top = min(floor + 2, height)
            if top >= floor and height > SEA_LEVEL:
                spans[(x, z)] = (floor, top)
    return spans


def opening(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[int, int] | None:
    """The span of air (lowest y, highest y) a cave entrance carves in the column, or None."""
    return region_openings(x // OPENING_REGION, z // OPENING_REGION, seed)[1].get((x, z))


def surface_opened(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> bool:
    """A cave entrance took the column's ground cell: it is open to the sky there."""
    span = opening(x, z, seed)
    return span is not None and span[1] == terrain_height(x, z, seed)


@lru_cache(maxsize=4096)
def rocks_in_chunk(cx: int, cz: int, seed: str = LEGACY_WORLD_SEED) -> tuple[tuple[int, int, str, int, str], ...]:
    """The boulder or outcrop of a chunk, if it has one: (x, z, kind, size, block) of its middle
    column. An outcrop (size 3) crowns a hill 8 or more high in a third of such chunks; a boulder (size
    1 or 2) sits in a quarter of the others. Neither leaves its chunk, stands in water or tops a hole."""
    x0, z0 = cx * 16, cz * 16
    if math.hypot(x0 + 8, z0 + 8) <= LEGACY_RADIUS + 16:
        return ()
    roll = hash32(cx, 0, cz, seed, 84)
    x, z = x0 + 3 + roll % 10, z0 + 3 + (roll >> 8) % 10
    ground = terrain_height(x, z, seed)
    if ground <= SEA_LEVEL or swamp_pool(x, z, seed) or surface_opened(x, z, seed):
        return ()
    biome, pick = biome_at(x, z, seed), (roll >> 16) % 12
    if ground >= OUTCROP_GROUND and pick < 4:
        return ((x, z, "outcrop", 3, OUTCROPS.get(biome, "stone")),)
    if pick >= 9:
        return ((x, z, "boulder", 1 + (roll >> 24) % 2, BOULDERS.get(biome, "mossy_cobblestone")),)
    return ()


@lru_cache(maxsize=131072)
def rock_column(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
    """The block of the boulder or outcrop standing on a column and the y of its top, or None. Each
    column of a rock rests on its own ground, so none floats: a boulder is a low dome, an outcrop a
    jagged crag of pillars 1 to 3 high. A column with a tree, water or an opened surface has no rock
    (a roofed mouth column, its surface intact, can still carry one)."""
    for rx, rz, kind, size, block in rocks_in_chunk(x // 16, z // 16, seed):
        dx, dz = x - rx, z - rz
        if kind == "boulder":
            layers = sum(1 for dy in range(1, size + 1)
                         if dx * dx + dz * dz + (dy - 0.5) * (dy - 0.5) * 1.6 <= (size + 0.5) * (size + 0.5))
        elif dx * dx + dz * dz <= size * size and ((dx, dz) == (0, 0) or hash32(x, 3, z, seed, 85) % 3 != 0):
            layers = 1 + hash32(x, 2, z, seed, 85) % 3
        else:
            layers = 0
        ground = terrain_height(x, z, seed)
        if (layers and ground >= SEA_LEVEL and not swamp_pool(x, z, seed) and not surface_opened(x, z, seed)
                and tree_base(x, z, seed) is None):
            return block, ground + layers
    return None


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
        if y > SEA_LEVEL:
            return "air"
        return "ice" if y == SEA_LEVEL and biome_at(x, z, seed) == "taiga" else "water"
    span = opening(x, z, seed)
    if span is not None and span[0] <= y <= span[1]:
        return "air"
    if y == height:
        return "water" if swamp_pool(x, z, seed) else surface_material(x, z, seed)
    if y >= height - 2:
        biome = biome_at(x, z, seed)
        return "sand" if biome == "desert" else "mud" if biome == "swamp" and y == height - 1 else "dirt"
    if cave_at(x, y, z, seed):
        return cave_fill(x, y, z, seed)
    ore = hash32(x, y, z, seed, 9)
    if ore % 97 == 0:
        return "iron_ore"
    if ore % 61 == 0:
        return "coal_ore"
    if ore % 151 == 0:
        return "copper_ore"
    if ore % GOLD_RARITY == 0 and y <= GOLD_DEPTH:
        return "gold_ore"
    if ore % DIAMOND_RARITY == 0 and y <= DIAMOND_DEPTH:
        return "diamond_ore"
    if gravel_floor(x, y, z, seed):
        return "gravel"
    return stone_at(x, y, z, seed)


def _decoration_column(x: int, z: int, seed: str, rim: bool = False) -> bool:
    """Columns where the viewer has always allowed trees and flowers. `rim` is a trunk within
    RIM_MARGIN of the legacy clearing's edge: it skips the swamp-pool exclusion L3 added, so it grows
    exactly where it would have before L3 (its canopy can reach inside the clearing)."""
    if not (3 <= x % 16 <= 12 and 3 <= z % 16 <= 12) or math.hypot(x, z) < 17:
        return False
    if terrain_height(x, z, seed) < SEA_LEVEL or biome_at(x, z, seed) in ("desert", "alpine"):
        return False
    if surface_opened(x, z, seed) or (swamp_pool(x, z, seed) and not rim):
        return False
    mx, mz = x % 13, z % 13
    return not (min(mx, 13 - mx) < 5 and min(mz, 13 - mz) < 5)


def _legacy_forest(x: int, z: int, seed: str) -> bool:
    """Whether (x, z) was forest under the pre-L3 biome_at (moisture above 0.08, neither desert nor
    alpine): desert and alpine are unchanged by L3, so this only needs the old moisture check."""
    return biome_at(x, z, seed) not in ("desert", "alpine") and noise2(x, z, 160, seed, 5) > 0.08


def tree_base(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> int | None:
    """Ground height under a tree trunk at (x, z), or None when no tree grows there."""
    rim = math.hypot(x, z) <= LEGACY_RADIUS + RIM_MARGIN
    if not _decoration_column(x, z, seed, rim):
        return None
    if math.hypot(x, z) <= LEGACY_RADIUS:
        grows = legacy_hash(x, z) % 257 == 0
    elif rim:
        grows = hash32(x, 0, z, seed, 12) % (78 if _legacy_forest(x, z, seed) else 300) == 0
    else:
        grows = hash32(x, 0, z, seed, 12) % TREE_RARITY.get(biome_at(x, z, seed), MEADOW_TREES) == 0
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


@lru_cache(maxsize=65536)
def tree_kind(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """The wood of the tree rooted at (x, z): oak within RIM_MARGIN of the legacy clearing (its canopy
    can reach inside), spruce in the taiga, birch in a birch forest (one in five an oak), now and then
    a birch in a forest, else oak."""
    if math.hypot(x, z) <= LEGACY_RADIUS + RIM_MARGIN:
        return "oak"
    biome = biome_at(x, z, seed)
    roll = hash32(x, 0, z, seed, 21) % 10
    if biome == "taiga":
        return "spruce"
    if biome == "birch_forest":
        return "oak" if roll < 2 else "birch"
    return "birch" if biome == "forest" and roll == 0 else "oak"


def leaf_of(kind: str, dx: int, dy: int, dz: int) -> bool:
    """The canopy of a tree of `kind` relative to its trunk's ground cell: oak's (is_leaf), a slim
    birch crown from 4 to 7 above the ground, or a spruce cone from 3 to 7. The trunk wins where they
    meet."""
    ax, az = abs(dx), abs(dz)
    if kind == "birch":
        if dy in (4, 5):
            return ax + az <= 2
        return (dy == 6 and ax + az <= 1) or (dy == 7 and ax + az == 0)
    if kind == "spruce":
        if dy == 3:
            return ax <= 2 and az <= 2 and ax + az <= 3
        if dy in (4, 6):
            return ax + az <= 1
        if dy == 5:
            return ax + az <= 2
        return dy == 7 and ax + az == 0
    return is_leaf(dx, dy, dz)


def tree_block(x: int, y: int, z: int, seed: str) -> str | None:
    """A trunk (of any tree in the chunk) first, then the leaves of the first tree whose canopy has
    the cell."""
    trees = trees_in_chunk(x // 16, z // 16, seed)
    for tx, tz, base in trees:
        if x == tx and z == tz and base < y <= base + 4:
            return TREE_LOGS[tree_kind(tx, tz, seed)]
    for tx, tz, base in trees:
        kind = tree_kind(tx, tz, seed)
        if leaf_of(kind, x - tx, y - base, z - tz):
            return TREE_LEAVES[kind]
    return None


def wild_food(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """A ripe berry bush (meadows and forest edges, oak or birch) or a mushroom (either forest's
    floor) on generated land. The legacy clearing keeps exactly the plants it always had."""
    if math.hypot(x, z) <= LEGACY_RADIUS:
        return None
    biome = biome_at(x, z, seed)
    wooded = biome in ("forest", "birch_forest")
    if biome == "meadow" or (wooded and noise2(x, z, 160, seed, 5) < FOREST_EDGE):
        if hash32(x, 0, z, seed, 15) % BUSH_RARITY == 0:
            return "berry_bush_ripe"
    if wooded:
        roll = hash32(x, 0, z, seed, 16)
        if roll % MUSHROOM_RARITY == 0:
            return "red_mushroom" if roll // MUSHROOM_RARITY % 3 == 0 else "brown_mushroom"
    return None


def cave_plant(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """A mushroom on a cave floor: an open cave cell of air with solid rock (or bedrock) under it,
    never where an entrance carved the cell below to air."""
    roll = hash32(x, y, z, seed, 17)
    if roll % CAVE_MUSHROOM_RARITY != 0:
        return None
    if not cave_at(x, y, z, seed) or cave_at(x, y - 1, z, seed) or cave_fill(x, y, z, seed) != "air":
        return None
    span = opening(x, z, seed)
    if span is not None and span[0] <= y - 1 <= span[1]:
        return None
    return "red_mushroom" if roll // CAVE_MUSHROOM_RARITY % 3 == 0 else "brown_mushroom"


def tall_plant(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
    """A cactus in the desert, or sugar cane on a shore right beside a lake (not in a swamp pool), with
    how many blocks high it stands (1 to 3). None in the legacy clearing."""
    if math.hypot(x, z) <= LEGACY_RADIUS:
        return None
    biome = biome_at(x, z, seed)
    if biome == "desert":
        roll = hash32(x, 0, z, seed, 25)
        return ("cactus", 1 + roll // CACTUS_RARITY % 3) if roll % CACTUS_RARITY == 0 else None
    if biome not in ("meadow", "forest", "birch_forest", "swamp") or not shore(x, z, seed) or swamp_pool(x, z, seed):
        return None
    rarity = CANE_RARITY // 3 if biome == "swamp" else CANE_RARITY
    roll = hash32(x, 0, z, seed, 26)
    return ("sugar_cane", 1 + roll // rarity % 3) if roll % rarity == 0 else None


@lru_cache(maxsize=131072)
def plant_stack(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> tuple[str, int] | None:
    """What grows on top of the terrain at (x, z) and how many blocks high: a flower, wild food, tall
    grass, a fern, a dead bush, a pumpkin or a melon stand one high, a cactus or sugar cane 1 to 3."""
    if math.hypot(x, z) <= HOME_RADIUS or surface_opened(x, z, seed) or rock_column(x, z, seed):
        return None
    surface = surface_material(x, z, seed)
    if _decoration_column(x, z, seed):
        if tree_base(x, z, seed) is not None:
            return None
        if hash32(x, 0, z, seed, 13) % 97 == 0 and surface in ("grass", "moss"):
            return ("flower_orange" if legacy_hash(x + 1, z) % 2 else "flower_yellow"), 1
    if math.hypot(x, z) > LEGACY_RADIUS and terrain_height(x, z, seed) < SEA_LEVEL:
        return None
    tall = tall_plant(x, z, seed)
    if tall:
        return tall
    biome = biome_at(x, z, seed)
    if surface == "sand":
        dead = biome == "desert" and hash32(x, 0, z, seed, 22) % DEAD_BUSH_RARITY == 0
        return ("dead_bush", 1) if dead else None
    if surface not in ("grass", "moss", "mud") or swamp_pool(x, z, seed):
        return None
    food = wild_food(x, z, seed)
    if food:
        return food, 1
    if biome == "taiga" and hash32(x, 0, z, seed, 23) % FERN_RARITY == 0:
        return "fern", 1
    if biome in FRUIT_BIOMES and math.hypot(x, z) > LEGACY_RADIUS:
        roll = hash32(x, 0, z, seed, 24)
        if roll % FRUIT_RARITY == 0:
            return ("pumpkin" if roll // FRUIT_RARITY % 2 == 0 else "melon"), 1
    rarity = 11 if biome == "swamp" else 19
    return ("tall_grass", 1) if hash32(x, 0, z, seed, 14) % rarity == 0 else None


def plant_at(x: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """The plant (or fruit) growing on top of the terrain at (x, z): the base of plant_stack."""
    stack = plant_stack(x, z, seed)
    return stack[0] if stack else None


def decoration_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str | None:
    """Blocks that grow or stand on the terrain, or on a cave floor. Precedence: home, trunk,
    leaves, rock, plant."""
    home = HOME_BLOCKS.get((x, y, z))
    if home:
        return home
    tree = tree_block(x, y, z, seed)
    if tree:
        return tree
    height = terrain_height(x, z, seed)
    rock = rock_column(x, z, seed) if y > height else None
    if rock is not None:
        return rock[0] if y <= rock[1] else None
    if height < y <= height + 3:
        stack = plant_stack(x, z, seed)
        return stack[0] if stack and y <= height + stack[1] else None
    if y < height - 2:
        return cave_plant(x, y, z, seed)
    return None


def block_at(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    """The natural block at any cell: terrain first, then decorations in air."""
    terrain = terrain_block(x, y, z, seed)
    if terrain != "air":
        return terrain
    return decoration_at(x, y, z, seed) or "air"


# Older callers use this name.
base_material = block_at
