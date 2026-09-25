"""Discovery goals (L4, the owner's "more curious"): something new to go and see is always on offer.

Once Mimo has a home of its own (after first_shelter), these goals are open whenever there is
something of their kind to find within DISCOVERY_REACH blocks of home and (L4a final fix wave, I4)
their trip has a target now (`has_target`); the reach grows with the land Mimo has walked
(curiosity.trip_reach), and each trip has spots on the way to what it looks for farther out
(curiosity.toward), a walk at a time. They repeat (goals.Goal.repeat): each counts only what Mimo
discovers after it was set, and is on offer again once reached. Their rules score rises with
curiosity (backend.survival.curiosity): 30 plus seven tenths of it, and RESTLESS_PULL more once Mimo
is restless and (I4) its trip has a target, so a restless pet's dawn choice turns from its routine
to a discovery even past the current goal's lead -- but never to one it can do nothing for: with
far_hills always valid and the pull applied regardless, a pet picked a stuck discovery goal, idled
about a day, set it aside and picked it again.
- new_land, "See new lands": set foot in a biome it has never seen (memory_knowledge "biome").
- new_creature, "Meet a new creature": meet a kind of creature it has never met ("creature").
- cave, "Look into a cave": look into a cave mouth or sinkhole it has not seen (a "cave" landmark).
- water, "Follow the water": find a lake it does not know (a water place).
- far_hills, "Map the far hills": set foot on FAR_PATCHES patches of ground it never walked,
  farther than FAR_FROM blocks from home (needs a home it built, so go_home reaches it from there;
  I4: ground it never walked counts as far land to head for, not ground it walked a day before).

Each has a trip of its own (backend.survival.trips), wanted only while its goal is Mimo's goal,
reaching DISCOVERY_REACH blocks from home: "look for new land" (a biome it has never seen is
sure), "look for a creature it has never met" (a biome where one lives), "look into a cave" (the
cave mouths and sinkholes it has not looked into, as life_goals' iron trip looks into them),
"follow the water" (lake ground with no water it knows within 16 blocks) and "walk the far hills"
(new ground past FAR_FROM, hills first). A trip ends on the find its goal counts. The "wander"
trip (curiosity's) serves them all (GOAL_NAMES: this module registers it again with them).
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, biome_at, terrain_height
from backend.survival.creatures.kinds import land_kinds
from backend.survival.curiosity import (
    NEW_PATCHES, RESTLESS, biome_words, meet_creatures, new_patches, seen, toward, trip_reach, unwalked, value_of,
)
from backend.survival.foraging import fishing_spots
from backend.survival.goals import Goal, Milestone, register_goal
from backend.survival.life_goals import (
    HILLS, iron_look, looked_into, opening_spots, opening_words, openings_near, whole,
)
from backend.survival.home import built_home
from backend.survival.home import home_place as home_of  # L4a final fix wave, I1: the one home lookup
from backend.survival.memory import PATCH, patch_of, remember
from backend.survival.situation import Situation
from backend.survival.steps import label
from backend.survival.trips import REASONS, Find, Reason, register_reason, targets

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

DISCOVERY_REACH = 90.0  # blocks from home the goals look and their trips go (I4: curiosity.trip_reach grows it)
SAMPLE_STEP = 16  # blocks between the columns sampled for biomes within reach
RESTLESS_PULL = 100.0
FAR_FROM = 48.0
FAR_PATCHES = 12
WATER_NEAR = 16.0
LAKE_SAMPLES = ((0, 0), (6, 0), (-6, 0), (0, 6), (0, -6))
GOAL_NAMES = ("new_land", "new_creature", "cave", "water", "far_hills")


def since(s: Situation, name: str) -> float | None:
    """When `name` became Mimo's goal, or None while it is not."""
    goal = s.brain.get("goal") or {}
    return goal.get("since") if goal.get("name") == name else None


def learned_since(s: Situation, fact: str, at: float | None) -> list[str]:
    if at is None or s.db is None:
        return []
    rows = s.db.execute("SELECT subject FROM memory_knowledge WHERE fact=? AND learned_at>=? ORDER BY learned_at",
                        (fact, at)).fetchall()
    return [row[0] for row in rows]


def found_since(s: Situation, kind: str, at: float | None) -> list[dict]:
    return [] if at is None else [place for place in s.places if place["kind"] == kind and place["found_at"] >= at]


def within_reach(s: Situation) -> list[tuple[int, int]]:
    """Columns every SAMPLE_STEP blocks within trip_reach of home (DISCOVERY_REACH until the land near
    home is walked, I4; none without a home)."""
    def look() -> list[tuple[int, int]]:
        home = home_of(s)
        if home is None:
            return []
        far = trip_reach(s)
        reach = int(far)
        return [(home["x"] + dx, home["z"] + dz) for dx in range(-reach, reach + 1, SAMPLE_STEP)
                for dz in range(-reach, reach + 1, SAMPLE_STEP) if math.hypot(dx, dz) <= far]
    return s.sensed("discovery samples", look)


def biomes_in_reach(s: Situation) -> set[str]:
    return s.sensed("biomes in reach", lambda: {biome_at(x, z, s.seed) for x, z in within_reach(s)})


def has_target(s: Situation, name: str) -> bool:
    """The goal's trip has somewhere to head now (I4): the goals are valid only then, and a restless
    pet's pull toward them counts only then -- far_hills was always valid and the restless pull
    applied with nothing to do, so a pet picked a stuck discovery goal, idled about a day, set it
    aside and picked it again."""
    reason = REASONS.get(name)
    return reason is not None and bool(targets(s, reason))


def pull(s: Situation, name: str) -> float:
    """A discovery goal's rules score: 30, seven tenths of curiosity, and RESTLESS_PULL once restless
    while its trip has somewhere to go (`has_target`)."""
    curiosity = value_of(s.brain)
    restless = curiosity >= RESTLESS and has_target(s, name)
    return 30.0 + 0.7 * curiosity + (RESTLESS_PULL if restless else 0.0)


def pull_of(name: str):
    return lambda s: pull(s, name)


def with_target(name: str, land):
    """The goal's validity: there is land of its kind within reach (`land`) and its trip has a target."""
    return lambda s: bool(land(s)) and has_target(s, name)


def goal_trip(name: str, why: str):
    """A trip wanted only while `name` is Mimo's goal."""
    def wanted(s: Situation) -> str | None:
        return why if since(s, name) is not None else None
    return wanted


def trip_found(s: Situation) -> float | None:
    return (s.brain.get("trip") or {}).get("since")


# new_land --------------------------------------------------------------------------------------

def unseen_biomes(s: Situation) -> set[str]:
    return biomes_in_reach(s) - seen(s, "biome")


register_goal(Goal(
    "new_land", "See new lands", "There is more to the world than home: land it has never seen lies near.",
    (Milestone("Set foot in a land it has never seen",
               lambda s: whole(bool(learned_since(s, "biome", since(s, "new_land")))), ("explore",)),),
    score=pull_of("new_land"), thought="I wonder what the land looks like over there.", after=("first_shelter",),
    valid=with_target("new_land", unseen_biomes), repeat=True))


def new_land_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    biome = biome_at(x, z, s.seed)
    return (1.0, f"{biome_words(biome)}, which it has never seen") if biome not in seen(s, "biome") else (0.0, "")


def new_land_look(s: Situation, context: ActionContext) -> Find | None:
    biomes = learned_since(s, "biome", trip_found(s))
    return Find(biome_words(biomes[-1]), True, new=False) if biomes else None


def new_land_spots(s: Situation) -> list[tuple[int, int, str]]:
    """On the way to the nearest land within reach whose biome Mimo never saw (I4)."""
    return toward(s, [(x, z, biome_words(biome_at(x, z, s.seed))) for x, z in within_reach(s)
                      if biome_at(x, z, s.seed) not in seen(s, "biome")])


register_reason(Reason(
    "new_land", "look for new land", goal_trip("new_land", "I want to see land I have never seen"), new_land_value,
    lambda s: 50.0, goals=("new_land",), spots=new_land_spots, look=new_land_look, reach=trip_reach))


# new_creature ----------------------------------------------------------------------------------

def unmet(s: Situation, biome: str) -> list[str]:
    return [kind.name for kind in land_kinds(biome) if kind.name not in seen(s, "creature")]


register_goal(Goal(
    "new_creature", "Meet a new creature", "Other creatures live in other lands: meeting them is half the fun.",
    (Milestone("Meet a creature it has never met",
               lambda s: whole(bool(learned_since(s, "creature", since(s, "new_creature")))), ("explore",)),),
    score=pull_of("new_creature"), thought="Who else lives out there?", after=("first_shelter",),
    valid=with_target("new_creature", lambda s: any(unmet(s, biome) for biome in biomes_in_reach(s))), repeat=True))


def new_creature_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    biome = biome_at(x, z, s.seed)
    kinds = unmet(s, biome)
    return (1.0, f"{biome_words(biome)}, where {label(kinds[0])}s live") if kinds else (0.0, "")


def new_creature_look(s: Situation, context: ActionContext) -> Find | None:
    meet_creatures(s.state, context, s.at)
    kinds = learned_since(s, "creature", trip_found(s))
    return Find(f"a {label(kinds[-1])}", True, new=False) if kinds else None


def new_creature_spots(s: Situation) -> list[tuple[int, int, str]]:
    """On the way to the nearest land within reach where creatures Mimo never met live (I4)."""
    found = []
    for x, z in within_reach(s):
        biome = biome_at(x, z, s.seed)
        kinds = unmet(s, biome)
        if kinds:
            found.append((x, z, f"{biome_words(biome)}, where {label(kinds[0])}s live"))
    return toward(s, found)


register_reason(Reason(
    "new_creature", "look for a creature it has never met",
    goal_trip("new_creature", "I want to meet a creature I have never met"), new_creature_value, lambda s: 50.0,
    goals=("new_creature",), spots=new_creature_spots, look=new_creature_look, reach=trip_reach))


# cave ------------------------------------------------------------------------------------------

def unlooked_openings(s: Situation) -> list[tuple[str, int, int]]:
    home = home_of(s)
    if home is None:
        return []
    return [opening for opening in openings_near(s.seed, home["x"], home["z"], trip_reach(s))
            if not looked_into(s, opening[1], opening[2])]


register_goal(Goal(
    "cave", "Look into a cave", "Cave mouths and sinkholes lead under the world: what is down there?",
    (Milestone("Look into a cave mouth or sinkhole",
               lambda s: whole(bool(found_since(s, "cave", since(s, "cave")))), ("explore",)),),
    score=pull_of("cave"), thought="That dark hole in the hill... I have to see.", after=("first_shelter",),
    valid=with_target("cave", unlooked_openings), repeat=True))


def cave_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    for kind, ox, oz in openings_near(s.seed, x, z, 12):
        if not looked_into(s, ox, oz):
            return 1.0, opening_words(kind)
    return (0.3, "hills") if terrain_height(x, z, s.seed) >= HILLS else (0.0, "")


def cave_look(s: Situation, context: ActionContext) -> Find | None:
    find = iron_look(s, context)
    return None if find is None else Find(find.words, True, find.new)


def cave_spots(s: Situation) -> list[tuple[int, int, str]]:
    """The openings near Mimo it has not looked into (as the iron trip's), and (I4) on the way to the
    nearest ones farther out within reach."""
    return opening_spots(s) + toward(s, [(ox, oz, opening_words(kind)) for kind, ox, oz in unlooked_openings(s)])


register_reason(Reason(
    "cave", "look into a cave", goal_trip("cave", "I want to see what is under the world"), cave_value,
    lambda s: 50.0, goals=("cave",), spots=cave_spots, look=cave_look, reach=trip_reach))


# water -----------------------------------------------------------------------------------------

def lake_at(s: Situation, x: int, z: int) -> bool:
    return any(terrain_height(x + dx, z + dz, s.seed) < SEA_LEVEL for dx, dz in LAKE_SAMPLES)


def known_water(s: Situation, x: int, z: int) -> bool:
    return any(place["kind"] == "water" and math.hypot(place["x"] - x, place["z"] - z) <= WATER_NEAR
               for place in s.places)


def lakes(s: Situation) -> list[tuple[int, int]]:
    """The sampled columns within reach of home on a lake Mimo does not know."""
    return s.sensed("lakes in reach", lambda: [(x, z) for x, z in within_reach(s)
                                               if lake_at(s, x, z) and not known_water(s, x, z)])


register_goal(Goal(
    "water", "Follow the water", "Lakes and streams bring fish, reeds and new shores.",
    (Milestone("Find water it does not know",
               lambda s: whole(bool(found_since(s, "water", since(s, "water")))), ("explore",)),),
    score=pull_of("water"), thought="I can hear water somewhere.", after=("first_shelter",),
    valid=with_target("water", lambda s: lakes(s)), repeat=True))


def water_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    return (1.0, "a lake") if lake_at(s, x, z) and not known_water(s, x, z) else (0.0, "")


def water_look(s: Situation, context: ActionContext) -> Find | None:
    for stand, water in fishing_spots(s) or []:
        if not known_water(s, water[0], water[2]):
            return Find("water it did not know", True, remember(s.db, "water", water, s.at))
    return None


def water_spots(s: Situation) -> list[tuple[int, int, str]]:
    """On the way to the nearest lake within reach it does not know, to its shore (I4)."""
    return toward(s, [(x, z, "a lake") for x, z in lakes(s)], short=WATER_NEAR / 2)


register_reason(Reason(
    "water", "follow the water", goal_trip("water", "I want to find water I do not know"), water_value,
    lambda s: 50.0, goals=("water",), spots=water_spots, look=water_look, reach=trip_reach))


# far_hills -------------------------------------------------------------------------------------

def far_walked(s: Situation) -> int:
    """Patches farther than FAR_FROM from home walked only since the goal was set."""
    at, home = since(s, "far_hills"), home_of(s)
    if at is None or home is None or s.db is None:
        return 0
    rows = s.db.execute("SELECT rx, rz FROM memory_explored WHERE visits=1 AND last_at>=?", (at,)).fetchall()
    return sum(1 for rx, rz in rows
               if math.hypot(rx * PATCH + PATCH / 2 - home["x"], rz * PATCH + PATCH / 2 - home["z"]) > FAR_FROM)


register_goal(Goal(
    "far_hills", "Map the far hills", "Past the land around home lie hills it has only seen from afar.",
    (Milestone(f"Walk {FAR_PATCHES} patches of far ground", lambda s: far_walked(s) / FAR_PATCHES, ("explore",)),),
    score=pull_of("far_hills"), thought="Those far hills are calling.", after=("first_shelter",),
    valid=with_target("far_hills", built_home), repeat=True))


def far_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    """Far ground Mimo never walked (I4: ground walked a day before read as new enough by novelty,
    and walking it again counted nothing toward the goal)."""
    home = home_of(s)
    if home is None or math.hypot(x - home["x"], z - home["z"]) <= FAR_FROM:
        return 0.0, ""
    fresh = new_patches(s, patch_of(x, z))
    if fresh < NEW_PATCHES:
        return 0.0, ""
    return (fresh / 9, "far hills") if terrain_height(x, z, s.seed) >= HILLS else (fresh / 9 * 0.7, "far land")


def far_spots(s: Situation) -> list[tuple[int, int, str]]:
    """On the way to the nearest ground it never walked farther than FAR_FROM from home, within reach (I4)."""
    return toward(s, [(x, z, "far land it never walked") for x, z in unwalked(s, FAR_FROM)])


register_reason(Reason(
    "far_hills", "walk the far hills", goal_trip("far_hills", "I want to see the land past the hills"), far_value,
    lambda s: 50.0, goals=("far_hills",), spots=far_spots, reach=trip_reach))


# The wander trip (backend.survival.curiosity) serves every discovery goal.
register_reason(replace(REASONS["wander"], goals=GOAL_NAMES))
