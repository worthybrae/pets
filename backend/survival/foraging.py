"""Food from the wild: forage and fish.

forage picks ripe berry bushes and mushrooms within 24 blocks, nearest first, up to 4 plants a
batch, until Mimo carries a game day's worth of food (60 hunger) or nothing ripe is left near.
With nothing ripe in sight it walks to a remembered food patch within 64 blocks that still had
ripe food, or was seen picked clean at least 2 game days ago (it has grown back since); a patch
it arrives at and finds nothing to pick at is remembered as picked clean then
(backend.survival.learning). Red mushrooms are picked too, until Mimo learns they are poisonous.

fish walks to the nearest shore within 24 blocks whose water still has fish (the 16x16 region's
stock) and fishes there, 3 catches a batch, until Mimo carries 4 fish, raw or cooked.

Both are day work, not offered at night, and both score in the needs band (purposes.py): the
hungrier Mimo is and the less food it carries, the higher. Their walks go all the way or not at
all (`whole`), and places within 4 blocks of where a step just failed are left alone for a while
(senses.near_failure).

L4a final fix wave, C1: food work (forage, fish and hunt, backend.survival.creatures.hunting) is
offered only while the food it brings would be kept or eaten, never left behind (`room_for_food`:
a stack is free, something Mimo carries gives way to food, carrying.gives_way, or Mimo is hungry
enough to eat what does not fit, carrying.eat_what_is_left). And a food patch Mimo goes back to lies
within FORAGE_REACH of home as well as of Mimo (backend.survival.home): with full arms leaving every
berry behind, each forage used to lead on to the next patch from where Mimo stood, 536 blocks out.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from backend.survival import nature
from backend.survival.carrying import full, gives_way
from backend.survival.clock import DAY_SECONDS
from backend.survival.grid import Cell
from backend.survival.home import from_home
from backend.survival.memory import cell_of
from backend.survival.once import log_once
from backend.survival.purposes import EAT_BELOW, HOME_RANGE, Purpose, foods, late_penalty, register, walk_to
from backend.survival.senses import FOOD_SIGHT, WATER_SIGHT, food_near, near_failure, shores_near
from backend.survival.situation import Situation
from backend.survival.steps import FOOD, REACH

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

FOOD_WANTED = 60.0  # hunger points of food Mimo likes to carry: about a game day's worth
PICKS_PER_BATCH = 4
FORAGE_BATCHES = 6
STAND = 2.0  # a walk to pick or tend something ends within this many blocks of it
PATCH_RANGE = 64.0
FORAGE_REACH = HOME_RANGE  # C1: a food patch Mimo goes back to lies this close to home too
PATCH_REACH = 3.0
REGROWN = 2 * DAY_SECONDS
FISH_GOAL = 4
CATCHES_PER_BATCH = 3
FISH_BATCHES = 4


def food_points(s: Situation) -> float:
    """Hunger the food Mimo carries would restore, leaving out food it knows is poisonous."""
    return sum(FOOD[item] * s.inventory[item] for item in foods(s.inventory, s.poisons))


# L4: more food a goal wants on hand, as functions of the Situation (backend.survival.larder adds
# the larder's while a full larder is Mimo's goal).
MORE_FOOD: list = []


def more_wanted(s: Situation) -> float:
    """What MORE_FOOD adds; one that crashes adds nothing (logged once; the final fix wave guards it
    like harm.ARMOR_WANTED and work.EAGER)."""
    total = 0.0
    for more in MORE_FOOD:
        try:
            total += float(more(s))
        except Exception as error:
            log_once(logger, "more food", error)
    return total


def food_need(s: Situation) -> float:
    return max(0.0, FOOD_WANTED + more_wanted(s) - food_points(s))


def hunger_score(s: Situation, base: float) -> float:
    """The needs-band score of food work: `base`, plus the food Mimo lacks and how hungry it is."""
    return base + food_need(s) / 3 + (100.0 - s.vitals["hunger"]) / 3 - late_penalty(s)


def room_for_food(s: Situation) -> bool:
    """C1: food Mimo gathers now would be kept or eaten, never left behind: a stack is free,
    something it carries gives way to food, or it is hungry enough (EAT_BELOW) to eat what does
    not fit on the spot."""
    return (not full(s.inventory) or bool(gives_way(s.inventory, "berries"))
            or s.vitals["hunger"] < EAT_BELOW)


def whole_walk(cell: Cell, reach: float = 0.0) -> dict:
    """A walk that goes all the way or fails at once (steps.start_walk): a route that only gets
    part of the way to food or water can drop Mimo into a pit it cannot climb out of. Only for
    targets within pathing.MAX_RANGE (96 blocks); food work never walks farther than 64."""
    return {**walk_to(cell, reach), "whole": True}


def reach_steps(s: Situation, jobs: list[tuple[Cell, list[dict]]]) -> list[dict]:
    """The steps of each (cell, steps) job in turn, walking close to the cell first only when it may
    be out of reach from where Mimo will be (a walk ends within STAND blocks of its target)."""
    steps, where, slack = [], s.here, 0.0
    for cell, work in jobs:
        if math.dist(where, cell) + slack > REACH:
            steps.append(whole_walk(cell, STAND))
            where, slack = cell, STAND
        steps.extend(work)
    return steps


# forage ----------------------------------------------------------------------------------------

def ripe_food(s: Situation) -> list[Cell]:
    """Ripe food within sight, nearest first, leaving out poison and places near a failed step."""
    def look() -> list[Cell]:
        return [cell for cell in food_near(s.grid, s.seed, s.here, FOOD_SIGHT, s.poisons)
                if not near_failure(s.state, cell)]
    return s.sensed("ripe_food", look)


def patch_worth_a_visit(s: Situation, place: dict) -> bool:
    data = place["data"]
    if data.get("ripe", 0) > 0:
        return True
    seen = data.get("seen_at")
    return seen is None or (s.at - seen) * s.scale >= REGROWN


def near_home(s: Situation, place: dict) -> bool:
    """C1: within FORAGE_REACH of home (anywhere before Mimo has one)."""
    away = from_home(s, place["x"], place["z"])
    return away is None or away <= FORAGE_REACH


def patches(s: Situation) -> list[dict]:
    """Remembered food patches beyond sight but within 64 blocks, and within FORAGE_REACH of home
    (C1), that are worth a visit, nearest first."""
    found = [place for place in s.places if place["kind"] == "food"
             and FOOD_SIGHT < s.distance(cell_of(place)) <= PATCH_RANGE and near_home(s, place)
             and patch_worth_a_visit(s, place)]
    return sorted(found, key=lambda place: s.distance(cell_of(place)))


def forage_valid(s: Situation) -> bool:
    return not s.night and food_need(s) > 0 and room_for_food(s) and bool(ripe_food(s) or patches(s))


def forage_facts(s: Situation) -> str:
    return (f"{len(ripe_food(s))} ripe plants within {FOOD_SIGHT} blocks, {len(patches(s))} food patches to "
            f"revisit, carrying {round(food_points(s))} hunger of food")


def plan_forage(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or food_need(s) <= 0 or s.brain["batches"] >= FORAGE_BATCHES or not room_for_food(s):
        return []
    ripe = ripe_food(s)
    if ripe:
        return reach_steps(s, [(cell, [{"kind": "pick", "target": list(cell)}]) for cell in ripe[:PICKS_PER_BATCH]])
    far = patches(s)
    return [whole_walk(cell_of(far[0]), PATCH_REACH)] if far else []


register(Purpose(
    "forage", "forage", "Pick ripe berries and mushrooms nearby, or go back to a food patch that grew again.",
    valid=forage_valid, facts=forage_facts, score=lambda s: hunger_score(s, 35.0), plan=plan_forage,
    thoughts=("Those berries look ripe.", "I'll gather something to eat.")))


# fish ------------------------------------------------------------------------------------------

def fish_carried(s: Situation) -> int:
    return s.count("raw_fish", "cooked_fish")


def fishing_spots(s: Situation) -> list[tuple[Cell, Cell]]:
    """(shore cell, water cell) within sight whose water still has fish, nearest shore first."""
    def look() -> list[tuple[Cell, Cell]]:
        return [(stand, water) for stand, water in shores_near(s.grid, s.seed, s.here, WATER_SIGHT)
                if nature.fish_stock(s.state, water) > 0 and not near_failure(s.state, stand)]
    return s.sensed("fishing_spots", look)


def fish_valid(s: Situation) -> bool:
    return not s.night and fish_carried(s) < FISH_GOAL and room_for_food(s) and bool(fishing_spots(s))


def fish_facts(s: Situation) -> str:
    stand, water = fishing_spots(s)[0]
    return (f"water {round(s.distance(stand))} blocks away with {nature.fish_stock(s.state, water)} fish left, "
            f"carrying {fish_carried(s)} fish")


def plan_fish(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or fish_carried(s) >= FISH_GOAL or s.brain["batches"] >= FISH_BATCHES or not room_for_food(s):
        return []
    spots = fishing_spots(s)
    if not spots:
        return []
    stand, water = spots[0]
    catches = min(CATCHES_PER_BATCH, FISH_GOAL - fish_carried(s))
    walk = [] if s.here == stand else [whole_walk(stand)]
    return walk + [{"kind": "fish", "target": list(water)} for _ in range(catches)]


register(Purpose(
    "fish", "fish", "Fish from the shore of nearby water; cooked fish is the most filling food.",
    valid=fish_valid, facts=fish_facts, score=lambda s: hunger_score(s, 25.0) + s.trait("patience") / 10,
    plan=plan_fish, thoughts=("Maybe the fish are biting.", "Fish would make a good meal.")))
