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


def base_material(x: int, y: int, z: int, seed: str = LEGACY_WORLD_SEED) -> str:
    if y <= -5:
        return "bedrock"
    height = terrain_height(x, z, seed)
    if math.hypot(x, z) <= LEGACY_RADIUS:
        if -4 <= y < -1:
            ore_seed = abs(x * 31 + z * 17 + y * 101)
            return "iron_ore" if ore_seed % 37 == 0 else "coal_ore" if ore_seed % 19 == 0 else "stone"
        if y == -1:
            return "dirt"
        if y == 0 and ((x + 5) / 3.2) ** 2 + ((z - 4) / 2.4) ** 2 < 1:
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
