"""Vitals: pure rules for how health, hunger, warmth, energy, air and mood change.

All values run 0-100 and every rate is per game second. `step_vitals` advances one step
(the tick module keeps steps at 60 game seconds or less) and reads its conditions at the
start of the step.

W1: a wild pet's ailments (backend.survival.ailments) change a step through `Ailing`: a sickness or a
festering wound drains health (the cause "sickness" when it is the largest damage of the killing step),
no health regenerates while Mimo is sick or wounded, a tummy ache drains hunger and a chill energy half
again as fast, and mood's target falls.

W2: the season sets the warmth Mimo drifts toward outdoors (SEASON_WARMTH, by day and by night; spring's is
today's), the mountains stay 60 colder by day and 50 by night, falling snow takes SNOW_CHILL more off outdoors,
a shelter adds 45, a wool cloak CLOAK_WARMTH, and a fire, furnace or hearth within 4 blocks sets 100.
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
# W2: outdoor warmth by season, (by day, by night), before shelter, cloak and fire (backend.survival.sky).
SEASON_WARMTH = {"spring": (100.0, 30.0), "summer": (100.0, 45.0), "autumn": (85.0, 20.0), "winter": (45.0, -10.0)}
ALPINE_DAY, ALPINE_NIGHT = 60.0, 50.0  # the mountains are this much colder
SNOW_CHILL = 10.0  # falling snow, outdoors
CLOAK_WARMTH = 20.0  # a wool cloak
# When several kinds of damage land in the killing step, the largest wins; ties go to the first here.
CAUSE_ORDER = ("drowning", "cold", "starvation", "sickness")  # W1: sickness
HORIZONTAL = ((1, 0), (-1, 0), (0, 1), (0, -1))

MaterialAt = Callable[[int, int, int], str]


@dataclass(frozen=True)
class Surroundings:
    """What the world around Mimo's cell says. The tick computes it once per tick."""

    biome: str = "meadow"
    sheltered: bool = False
    near_fire: bool = False
    head_in_water: bool = False
    season: str = "spring"  # W2
    snowing: bool = False
    cloak: bool = False


@dataclass(frozen=True)
class Ailing:
    """W1: what Mimo's ailments do to its vitals this step (backend.survival.ailments.ailing)."""

    drain: float = 0.0  # health a game second a sickness or festering wound takes (cause "sickness")
    hunger: float = 1.0  # hunger drains this many times as fast (a tummy ache)
    energy: float = 1.0  # energy drains this many times as fast while awake (a chill)
    heals: bool = True  # whether health regenerates at all (not while sick or wounded)
    mood: float = 0.0  # how far mood's target falls


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def approach(value: float, target: float, max_change: float) -> float:
    if value < target:
        return min(target, value + max_change)
    return max(target, value - max_change)


def target_warmth(night: bool, biome: str, sheltered: bool, near_fire: bool, season: str = "spring",
                  snowing: bool = False, cloak: bool = False) -> float:
    if near_fire:
        return 100.0
    day, dark = SEASON_WARMTH.get(season, SEASON_WARMTH["spring"])
    base = dark if night else day
    if biome == "alpine":
        base -= ALPINE_NIGHT if night else ALPINE_DAY
    if snowing and not sheltered:
        base -= SNOW_CHILL
    return min(100.0, base + (SHELTER_BONUS if sheltered else 0.0) + (CLOAK_WARMTH if cloak else 0.0))


def mood_target(vitals: dict, lonely: bool, ailing: float = 0.0) -> float:
    """Where mood drifts: up when fed and warm, down when starving, freezing, hurt or alone; W1: `ailing`
    lower while Mimo is sick or its wound festers."""
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
    return clamp(target - ailing)


def step_vitals(vitals: dict, seconds: float, *, night: bool, activity: str,
                surroundings: Surroundings, lonely: bool = False, ailing: Ailing | None = None) -> tuple[dict, str | None]:
    """Advance vitals by `seconds` game seconds. Returns the new vitals and a cause of death, if any."""
    ailing = ailing or Ailing()
    if activity not in ACTIVITIES:
        raise ValueError(f"Unknown activity: {activity}")
    working = activity == "working"
    sleeping = activity in ("sleeping", "sleeping_in_bed")
    damage = {
        "starvation": STARVING_DAMAGE * seconds if vitals["hunger"] <= 0 else 0.0,
        "cold": FREEZING_DAMAGE * seconds if vitals["warmth"] < FREEZING_BELOW else 0.0,
        "drowning": DROWNING_DAMAGE * seconds if surroundings.head_in_water and vitals["air"] <= 0 else 0.0,
        "sickness": ailing.drain * seconds,
    }
    hurt = any(amount > 0 for amount in damage.values())
    fed_and_warm = vitals["hunger"] > 60 and vitals["warmth"] > 50
    healing = HEAL_RATE * seconds if fed_and_warm and not hurt and ailing.heals else 0.0
    if sleeping:
        energy_change = (ENERGY_BED if activity == "sleeping_in_bed" else ENERGY_SLEEP) * seconds
    else:
        energy_change = -(ENERGY_WORK if working else ENERGY_IDLE) * ailing.energy * seconds
    hunger_rate = HUNGER_IDLE * (WORK_HUNGER_MULTIPLIER if working else 1.0) * ailing.hunger
    air_change = -AIR_DRAIN * seconds if surroundings.head_in_water else AIR_RECOVER * seconds
    warmth_target = target_warmth(night, surroundings.biome, surroundings.sheltered, surroundings.near_fire,
                                  surroundings.season, surroundings.snowing, surroundings.cloak)
    result = {
        "health": clamp(vitals["health"] + healing - sum(damage.values())),
        "hunger": clamp(vitals["hunger"] - hunger_rate * seconds),
        "warmth": clamp(approach(vitals["warmth"], warmth_target, WARMTH_RATE * seconds)),
        "energy": clamp(vitals["energy"] + energy_change),
        "air": clamp(vitals["air"] + air_change),
        "mood": clamp(approach(vitals["mood"], mood_target(vitals, lonely, ailing.mood), MOOD_RATE * seconds)),
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
