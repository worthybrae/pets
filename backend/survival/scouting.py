"""The needs Mimo explores for (L4), registered in backend.survival.trips.

- trees, "look for trees": Mimo is low on wood (under 3 logs' worth, when gather_wood hurries), or
  its home needs wood (a shelter it started waits for blocks, or a home of its own or a bigger one
  is its goal), it carries less than work.wood_goal, and no tree stands within 24 blocks, so
  gather_wood is not on offer. The more trees worldgen grew within 12 blocks of a spot that still
  stand on the grid, the likelier (3 or more is sure; fix round 1 -- worldgen never forgets a tree
  once it is cut, so a candidate is checked there too); a wood it found before is a spot of its
  own. Found once a tree stands in sight: remembered as a "grove" landmark with its wood ("Pip found birch
  trees."), and gather_wood follows. 45 plus a fifth of curiosity, as explore scored with no tree
  in sight before L4. It serves the goals wood is for: a home, iron tools and a bigger home.
- food, "look for food": Mimo carries less than half a day's food and no food work is on offer: no
  ripe plant or food patch to go back to, no fishing spot, no animal to hunt. Wild berry bushes and
  mushrooms (worldgen's plants, 2 within 10 blocks is sure) are likeliest, then water with fish,
  then grazing land. Found once food work is on offer again: ripe food is remembered as a food
  place, water as a water place, an animal's ground as a "pasture" landmark. It scores like food
  work (30, plus a third of the food Mimo lacks and a third of its hunger) and serves the full
  larder.

The goals' own reasons register with their goals (backend.survival.life_goals: iron, hides, a
creature seed, the map; backend.survival.homes: a site for a bigger home). Landmarks are places
(memory_places): "grove", "pasture", "cave" and "site", each one per so many blocks
(memory.SAME_PLACE). This module also tells the goals when explore advances one
(goals.ADVANCES): when a trip on offer serves it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.crafting import LOGS
from backend.services.worldgen import SEA_LEVEL, biome_at, terrain_height, tree_kind
from backend.survival.creatures.hunting import prey
from backend.survival.creatures.kinds import land_kinds
from backend.survival.creatures.moves import where
from backend.survival.exploring import FOOD_WORDS
from backend.survival.foraging import (
    FOOD_WANTED, fishing_spots, food_need, food_points, patches, ripe_food, room_for_food,
)
from backend.survival.building import building_need
from backend.survival.goals import ADVANCES
from backend.survival.memory import SAME_PLACE, cell_of, remember, update_place
from backend.survival.senses import PICKABLE, TREE_SEARCH, TRUNK_HEIGHT, natural_plants, trees_near
from backend.survival.situation import Situation
from backend.survival.steps import label
from backend.survival.trips import Find, Reason, register_reason, serving
from backend.survival.work import logs_to_chop, wood, wood_goal

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

GROVE = "grove"  # a landmark: trees Mimo found on a trip, the note says which wood
PASTURE = "pasture"  # a landmark: where Mimo found an animal, the note says which
SAME_PLACE.update({GROVE: (24.0, (GROVE,)), PASTURE: (24.0, (PASTURE,)), "cave": (16.0, ("cave",)),
                   "site": (16.0, ("site",))})
LOW_WOOD = 3.0  # logs' worth of wood below which Mimo goes looking for trees
HOME_GOALS = ("first_shelter", "better_home")  # goals whose blocks wood is
TREE_GROVE = 12  # blocks around a spot whose trees count
SURE_TREES = 3
FOOD_SHORT = FOOD_WANTED / 2  # hunger of food carried below which Mimo goes looking for more
PLANT_REACH = 10  # blocks around a spot whose wild food counts
SURE_PLANTS = 2
WATER_SAMPLES = ((0, 0), (8, 0), (-8, 0), (0, 8), (0, -8))


# trees -----------------------------------------------------------------------------------------

def trees_in_sight(s: Situation) -> bool:
    return s.sensed("trees in sight", lambda: bool(logs_to_chop(s)))


def trees_wanted(s: Situation) -> str | None:
    have = wood(s.inventory)
    if have >= wood_goal(s) or trees_in_sight(s):
        return None
    if have < LOW_WOOD:
        return "I am out of wood and no tree stands near"
    if building_need(s) > 0 or (s.brain.get("goal") or {}).get("name") in HOME_GOALS:
        return "my home needs wood and no tree stands near"
    return None


def standing_near(s: Situation, x: int, z: int, radius: int) -> list[tuple[int, int, int]]:
    """Worldgen's generated trees within `radius` of (x, z) that still have logs on the grid: fix
    round 1 -- worldgen never forgets a tree once it is cut, so a chopped grove must not keep
    scoring as sure (senses.standing_logs does the same check, from where Mimo stands)."""
    return [(tx, tz, base) for tx, tz, base in trees_near(s.seed, x, z, radius)
            if any(s.grid.material(tx, y, tz) in LOGS for y in range(base + 1, base + TRUNK_HEIGHT + 1))]


def trees_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    near = standing_near(s, x, z, TREE_GROVE)
    if not near:
        return 0.0, ""
    return min(1.0, len(near) / SURE_TREES), f"{tree_kind(near[0][0], near[0][1], s.seed)} trees"


def grove_spots(s: Situation) -> list[tuple[int, int, str]]:
    return [(place["x"], place["z"], f"the {place['note'] or 'oak'} trees it found") for place in s.places
            if place["kind"] == GROVE and s.distance(cell_of(place)) > TREE_SEARCH]


def trees_look(s: Situation, context: ActionContext) -> Find | None:
    logs = logs_to_chop(s)
    if not logs:
        return None
    x, y, z = logs[0]
    kind = tree_kind(x, z, s.seed)
    return Find(f"{kind} trees", True, remember(s.db, GROVE, (x, y, z), s.at, kind))


register_reason(Reason(
    "trees", "look for trees", trees_wanted, trees_value, lambda s: 45.0 + s.trait("curiosity") / 5,
    goals=("first_shelter", "iron_tools", "better_home"), spots=grove_spots, look=trees_look))


# food ------------------------------------------------------------------------------------------

def food_work(s: Situation) -> bool:
    """Food work would be on offer: ripe food or a food patch to go back to, fish, an animal."""
    return bool(ripe_food(s) or patches(s) or fishing_spots(s) or prey(s))


def food_wanted(s: Situation) -> str | None:
    """L4a final fix wave, C1: not while the food it found could only be left behind (full arms,
    nothing to give way to food and not hungry enough to eat it there: foraging.room_for_food)."""
    if food_points(s) >= FOOD_SHORT or food_need(s) <= 0 or not room_for_food(s) or food_work(s):
        return None
    if s.vitals["hunger"] < 50:
        return "I am hungry and no food is near"
    return "I carry little food and none is near"


def food_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    counts = {block: len(natural_plants(s.seed, x, z, PLANT_REACH, (block,))) for block in PICKABLE
              if block not in s.poisons}
    most = max(counts, key=lambda block: counts[block], default=None)
    if most is not None and counts[most] > 0:
        return min(1.0, sum(counts.values()) / SURE_PLANTS), FOOD_WORDS[most]
    if any(terrain_height(x + dx, z + dz, s.seed) < SEA_LEVEL for dx, dz in WATER_SAMPLES):
        return 0.5, "water with fish"
    if land_kinds(biome_at(x, z, s.seed)):
        return 0.3, "grazing land"
    return 0.0, ""


def food_look(s: Situation, context: ActionContext) -> Find | None:
    ripe = ripe_food(s)
    if ripe:
        new = remember(s.db, "food", ripe[0], s.at)
        if new:
            update_place(s.db, "food", ripe[0], {"ripe": len(ripe), "seen_at": s.at})
        return Find(FOOD_WORDS.get(s.grid.material(*ripe[0]), "wild food"), True, new)
    spots = fishing_spots(s)
    if spots:
        return Find("water with fish", True, remember(s.db, "water", spots[0][1], s.at))
    animals = prey(s)
    if animals:
        kind = animals[0]["kind"]
        new = remember(s.db, PASTURE, where(animals[0], s.at), s.at, kind)
        return Find(f"a {label(kind)} to hunt", True, new)
    return None


register_reason(Reason(
    "food", "look for food", food_wanted, food_value,
    lambda s: 30.0 + food_need(s) / 3 + (100.0 - s.vitals["hunger"]) / 3,
    goals=("full_larder",), look=food_look))


# explore and the goals -------------------------------------------------------------------------

ADVANCES["explore"] = lambda s, goal: serving(s, goal.name)
