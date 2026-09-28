"""cook: turn raw food into better food.

- Raw fish (8 hunger) cooks into cooked fish (30) in 5 s at a lit campfire or furnace within 6
  blocks, and so does the raw meat hunting brings (L1): beef (8 to 35), mutton (8 to 30),
  chicken and rabbit (6 to 25). With no fire that close, Mimo places a campfire or furnace it
  carries beside it (in a niche it digs when it is below the surface, as toolmaking does), or
  first crafts a campfire from 2 logs and 3 sticks; failing both, it walks to a fire within 32
  blocks and cooks there next batch. A fire within 4 blocks of where a step just failed is left
  alone for a while (senses.near_failure).
- Three wheat bake into bread (25) at a crafting table, like craft_tools does it.
W1: a wild pet cooks raw food only once it knows `wild:cooking`, and makes or puts down a campfire only
once it knows `wild:fire` (backend.survival.wild): before that it cooks at a furnace it carries or finds, and
bakes bread as ever.
W2: a campfire the rain put out that stands within reach is lit again (one stick) before another is put down,
and a pet that knows `wild:rain` puts its fire under a roof when one is in reach (backend.survival.rain).
A station or fire the plan placed is mined back into Mimo's inventory at the end. Those steps
are kept (`keep`), so a new choice does not leave the station behind. cook is offered while
there is raw food it can cook now, with room to carry what it makes, and scores in the needs band.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.services.crafting import COOKING, FIRES
from backend.survival.carrying import crafts_fit
from backend.survival.grid import Cell
from backend.survival.once import log_once
from backend.survival.foraging import whole_walk
from backend.survival.purposes import Purpose, register
from backend.survival.rain import relight_steps, roofed_first
from backend.survival.senses import near_failure
from backend.survival.situation import Situation
from backend.survival.steps import STATION_REACH, WORKSTATIONS
from backend.survival.toolmaking import Short, make, place_station, station_spots
from backend.survival.spoilage import turning
from backend.survival.wild import knows, unlocked

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

RAW_FOODS = tuple(sorted(COOKING))
FIRE_TRAVEL = 32.0
FIRE_STAND = 2.0
BREAD_WHEAT = 3


def made(inventory: dict, item: str) -> list[dict] | None:
    """The craft steps that make one `item` from `inventory` (which they then change), or None when
    they cannot, or when something they make would not fit in Mimo's arms (carrying.crafts_fit)."""
    trial, steps = dict(inventory), []
    try:
        make(trial, item, 1, steps)
    except Short:
        return None
    if not crafts_fit(inventory, steps):
        return None
    inventory.clear()
    inventory.update(trial)
    return steps


def station(inventory: dict, name: str, spots: list[tuple[Cell, bool]], steps: list[dict], placed: list[Cell],
            carried: tuple[str, ...]) -> bool:
    """Place a carried station (the first of `carried`), or make `name` and place it, in the next
    station spot (toolmaking.station_spots). False when there is no spot or nothing to place."""
    if not spots:
        return False
    block = next((item for item in carried if inventory.get(item, 0) > 0), None)
    if block is None:
        crafting = made(inventory, name)
        if crafting is None:
            return False
        steps.extend(crafting)
        block = name
    placed.append(place_station(spots, block, steps))
    inventory[block] -= 1
    return True


def light_fire(s: Situation, inventory: dict, spots, steps: list[dict], placed: list[Cell]) -> bool:
    """Put down a fire to cook on: a carried campfire or furnace, or a campfire made now; W1: a wild pet that
    does not know `wild:fire` only puts down a furnace it carries."""
    if unlocked(s, "fire"):
        return station(inventory, "campfire", spots, steps, placed, ("campfire", "furnace"))  # W2: never a hearth
    return inventory.get("furnace", 0) > 0 and station(inventory, "furnace", spots, steps, placed, ("furnace",))


logger = logging.getLogger(__name__)
# W2: functions of the Situation giving the raw foods cook leaves alone now (backend.survival.winter_gear: the meat a
# wild pet smokes for the winter instead). One that crashes spares nothing (logged once).
SPARED: list = []


def spared(s: Situation) -> frozenset[str]:
    found: set[str] = set()
    for spare in SPARED:
        try:
            found.update(spare(s))
        except Exception as error:
            log_once(logger, "cook spared", error)
    return frozenset(found)


def cook_plan(s: Situation) -> list[dict] | None:
    """The steps that cook the raw food Mimo carries (but what SPARED leaves alone), or None when it cannot cook any
    now."""
    inventory = dict(s.inventory)
    x, _, z = s.here
    near = s.grid.placed_near(x, z, STATION_REACH, WORKSTATIONS)
    spots = roofed_first(s, station_spots(s))
    steps: list[dict] = []
    placed: list[Cell] = []
    left = spared(s)
    raw = ([(item, inventory[item]) for item in RAW_FOODS if inventory.get(item, 0) > 0 and item not in left]
           if unlocked(s, "cooking") else [])
    relit = relight_steps(s, STATION_REACH) if raw and not near.intersection(FIRES) and unlocked(s, "fire") else []
    if relit:
        steps.extend(relit)
        inventory["sticks"] -= 1
    elif raw and not near.intersection(FIRES) and not light_fire(s, inventory, spots, steps, placed):
        fires = sorted((found for found in s.grid.placed_cells(x, z, FIRE_TRAVEL, FIRES)
                        if not near_failure(s.state, found[0])), key=lambda found: s.distance(found[0]))
        if fires:
            return [whole_walk(fires[0][0], FIRE_STAND)]
        raw = []
    steps.extend({"kind": "cook", "item": item} for item, count in raw for _ in range(count))
    loaves = inventory.get("wheat", 0) // BREAD_WHEAT
    if loaves and "crafting_table" not in near and not station(inventory, "crafting_table", spots, steps, placed,
                                                                ("crafting_table",)):
        loaves = 0
    steps.extend({"kind": "craft", "recipe": "bread"} for _ in range(loaves))
    if not raw and not loaves:
        return None
    steps.extend({"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(placed))
    return steps if crafts_fit(s.inventory, steps) else None


def cooks_raw(s: Situation) -> bool:
    """W1's final fix wave: Mimo can cook the raw food it carries now, at a fire near, one it puts down or one it
    walks to (`cook_plan`), once a Situation. A wild pet taught cooking leaves raw food out of a meal only then
    (backend.survival.meals): one that cannot cook it eats it raw, with its risk, as an untaught pet does."""
    def look() -> bool:
        if not any(s.inventory.get(item, 0) > 0 for item in RAW_FOODS):
            return False
        return any(step["kind"] in ("cook", "walk") for step in cook_plan(s) or [])  # a walk: to a fire, to cook
    return s.sensed("cooks raw", look)


def plan_cook(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 1:
        return []
    return cook_plan(s) or []


KEEPING_LIFT = 20.0  # W1: a pet that knows keeping cooks raw food before it turns


def cook_score(s: Situation) -> float:
    servings = s.count(*RAW_FOODS) + s.count("wheat") // BREAD_WHEAT
    lift = KEEPING_LIFT if knows(s, "keeping") and turning(s.state, RAW_FOODS) else 0.0
    return min(80.0, 50.0 + (100.0 - s.vitals["hunger"]) / 4 + 5.0 * servings + lift)


register(Purpose(
    "cook", "cook", "Cook raw fish and meat at a fire and bake wheat into bread; cooked food fills far more.",
    valid=lambda s: cook_plan(s) is not None,
    facts=lambda s: f"carrying {s.count(*RAW_FOODS)} raw fish and meat and {s.count('wheat')} wheat",
    score=cook_score, plan=plan_cook,
    thoughts=("Cooked fish tastes so much better.", "Let's get a fire going and cook.")))
