"""Vitals: pure rules for how health, hunger, warmth, energy, air and mood change.

All values run 0-100 and every rate is per game second. `step_vitals` advances one step
(the tick module keeps steps at 60 game seconds or less) and reads its conditions at the
start of the step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.services.blocks import is_solid

VITAL_NAMES = ("health", "hunger", "warmth", "energy", "air", "mood")
START_VITALS = {"health": 100.0, "hunger": 100.0, "warmth": 100.0, "energy": 100.0, "air": 100.0, "mood": 70.0}

HUNGER_IDLE = 0.014
WORK_HUNGER_MULTIPLIER = 1.5
ENERGY_IDLE = 0.008
ENERGY_WORK = 0.03
ENERGY_SLEEP = 0.2
ENERGY_BED = 0.35
WARMTH_RATE = 0.5
AIR_DRAIN = 10.0
AIR_RECOVER = 25.0
STARVING_DAMAGE = 1 / 30
FREEZING_DAMAGE = 1 / 15
DROWNING_DAMAGE = 2.0
HEAL_RATE = 1 / 60  # L2: 1 health a game minute while fed and warm
MOOD_RATE = 0.01
FREEZING_BELOW = 20.0
EXHAUSTED_BELOW = 10.0
SHELTER_BONUS = 45.0
SHELTER_REACH = 4
FIRE_REACH = 4
WARM_BLOCKS = ("campfire", "furnace")
ACTIVITIES = ("idle", "working", "sleeping", "sleeping_in_bed")
# When several kinds of damage land in the killing step, the largest wins; ties go to the first here.
CAUSE_ORDER = ("drowning", "cold", "starvation")
HORIZONTAL = ((1, 0), (-1, 0), (0, 1), (0, -1))

MaterialAt = Callable[[int, int, int], str]


@dataclass(frozen=True)
class Surroundings:
    """What the world around Mimo's cell says. The tick computes it once per tick."""

    biome: str = "meadow"
    sheltered: bool = False
    near_fire: bool = False
    head_in_water: bool = False


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def approach(value: float, target: float, max_change: float) -> float:
    if value < target:
        return min(target, value + max_change)
    return max(target, value - max_change)


def target_warmth(night: bool, biome: str, sheltered: bool, near_fire: bool) -> float:
    if near_fire:
        return 100.0
    if biome == "alpine":
        base = -20.0 if night else 40.0
    else:
        base = 30.0 if night else 100.0
    return min(100.0, base + (SHELTER_BONUS if sheltered else 0.0))


def mood_target(vitals: dict, lonely: bool) -> float:
    """Where mood drifts: up when fed and warm, down when starving, freezing, hurt or alone."""
    target = 60.0
    if vitals["hunger"] > 60 and vitals["warmth"] > 50:
        target += 20
    if vitals["hunger"] <= 0:
        target -= 30
    if vitals["warmth"] < FREEZING_BELOW:
        target -= 25
    if vitals["health"] < 50:
        target -= 15
    if lonely:
        target -= 10
    return clamp(target)


def step_vitals(vitals: dict, seconds: float, *, night: bool, activity: str,
                surroundings: Surroundings, lonely: bool = False) -> tuple[dict, str | None]:
    """Advance vitals by `seconds` game seconds. Returns the new vitals and a cause of death, if any."""
    if activity not in ACTIVITIES:
        raise ValueError(f"Unknown activity: {activity}")
    working = activity == "working"
    sleeping = activity in ("sleeping", "sleeping_in_bed")
    damage = {
        "starvation": STARVING_DAMAGE * seconds if vitals["hunger"] <= 0 else 0.0,
        "cold": FREEZING_DAMAGE * seconds if vitals["warmth"] < FREEZING_BELOW else 0.0,
        "drowning": DROWNING_DAMAGE * seconds if surroundings.head_in_water and vitals["air"] <= 0 else 0.0,
    }
    hurt = any(amount > 0 for amount in damage.values())
    healing = HEAL_RATE * seconds if vitals["hunger"] > 60 and vitals["warmth"] > 50 and not hurt else 0.0
    if sleeping:
        energy_change = (ENERGY_BED if activity == "sleeping_in_bed" else ENERGY_SLEEP) * seconds
    else:
        energy_change = -(ENERGY_WORK if working else ENERGY_IDLE) * seconds
    hunger_rate = HUNGER_IDLE * (WORK_HUNGER_MULTIPLIER if working else 1.0)
    air_change = -AIR_DRAIN * seconds if surroundings.head_in_water else AIR_RECOVER * seconds
    warmth_target = target_warmth(night, surroundings.biome, surroundings.sheltered, surroundings.near_fire)
    result = {
        "health": clamp(vitals["health"] + healing - sum(damage.values())),
        "hunger": clamp(vitals["hunger"] - hunger_rate * seconds),
        "warmth": clamp(approach(vitals["warmth"], warmth_target, WARMTH_RATE * seconds)),
        "energy": clamp(vitals["energy"] + energy_change),
        "air": clamp(vitals["air"] + air_change),
        "mood": clamp(approach(vitals["mood"], mood_target(vitals, lonely), MOOD_RATE * seconds)),
    }
    cause = None
    if result["health"] <= 0 and hurt:
        cause = max(CAUSE_ORDER, key=lambda name: (damage[name], -CAUSE_ORDER.index(name)))
    return result, cause


def is_sheltered(material_at: MaterialAt, x: int, y: int, z: int) -> bool:
    """A roof within 4 cells above Mimo's cell and a wall within 4 cells on at least 3 sides.

    (x, y, z) is the cell Mimo stands in. Natural overhangs and caves count.
    """
    if not any(is_solid(material_at(x, y + dy, z)) for dy in range(1, SHELTER_REACH + 1)):
        return False
    walls = sum(1 for dx, dz in HORIZONTAL
                if any(is_solid(material_at(x + dx * step, y, z + dz * step)) for step in range(1, SHELTER_REACH + 1)))
    return walls >= 3


def near_warm_block(placed: list[tuple[int, int, int, str]], x: int, y: int, z: int) -> bool:
    """True when a placed campfire or furnace is within 4 cells of Mimo's cell on every axis."""
    return any(material in WARM_BLOCKS and max(abs(bx - x), abs(by - y), abs(bz - z)) <= FIRE_REACH
               for bx, by, bz, material in placed)
