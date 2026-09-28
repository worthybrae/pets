"""W2: the wool cloak, the hearth and smoked meat ("Recipes, blocks and the winter goal" of the Wild World spec).

- The wool cloak (5 wool at a crafting table, crafting.RECIPES) sits in a slot of its own, not armor
  (harm.SLOTS "cloak"), and is worn by carrying it: CLOAK_WARMTH warmer (the tick's Surroundings.cloak), once a
  wild pet knows `wild:cloak` (wild.cloaked). make_cloak (work band: 55 plus a tenth of caution, by day) makes one
  with a crafting table it places and mines back, as make_gear does, once Mimo knows the cloak, has none and
  carries the wool; while it wants one, CLOAK_WOOL wool stay on hand (storage.KEEPS_MORE) and come back out of
  the chest when it holds them (storage.TAKES_MORE).
- The hearth (8 cobblestone and a campfire at a crafting table) is a block: glow and light 13, warm like a furnace
  (vitals.WARM_BLOCKS), a fire to cook and smoke at (crafting.FIRES, steps.WORKSTATIONS), and it never goes out in
  the rain. build_hearth (work band, HEARTH_SCORE, by day, while the winter goal wants one) puts it in the home's
  room, in the front corner nearest home's cell (two walls beside it, clear of the way in), which the home claims
  already.
- Smoked meat: the `smoke` step (SMOKE_SECONDS at a campfire or hearth) turns 1 raw meat and 1 stick into 1 smoked
  meat, which fills 20 hunger and never spoils (it is no PERISHABLE food). smoke_meat (work band, SMOKE_SCORE, by
  day) smokes the raw meat Mimo carries all through autumn, whatever its goal (the controller's ruling on the W2
  dry run), while winter wants more smoked meat (`smoke_wanted`), lighting a campfire as cook does.
Each is unlocked by its lesson (`wild:cloak`, `wild:hearth`, `wild:smoking`); a gentle pet knows them all.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.crafting import add_item, take_items
from backend.survival import storage
from backend.survival.carrying import crafts_fit
from backend.survival.cooking import FIRE_STAND, FIRE_TRAVEL, SPARED, station
from backend.survival.creatures.gear import gear_steps
from backend.survival.creatures.harm import SLOTS
from backend.survival.foraging import whole_walk
from backend.survival.goals import active
from backend.survival.grid import Cell
from backend.survival.home import home_structure
from backend.survival.purposes import HOME_RANGE, Purpose, register
from backend.survival.rain import relight_steps, roofed_first
from backend.survival.senses import near_failure
from backend.survival.situation import Situation
from backend.survival.steps import (
    FOOD, REACH, STATION_REACH, WORKSTATIONS, StepFailed, StepKind, as_cell, label, register_step, room_to_make,
    stations_near,
)
from backend.survival.structures import blueprint_of
from backend.survival.toolmaking import Short, make, station_spots
from backend.survival.wild import is_wild, unlocked
from backend.survival.winter_prep import GOAL, SMOKED_WANTED, WINTER_FOOD, hearth_home, held, preparing, winter_food

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

CLOAK_WOOL = 5
SMOKE_SECONDS = 20.0
SMOKABLE = ("raw_beef", "raw_mutton", "raw_chicken", "raw_rabbit")
SMOKE_FIRES = frozenset({"campfire", "hearth"})
HEARTH_SCORE = 60.0
SMOKE_SCORE = 65.0
SPARE_ABOVE = 50.0  # hunger from which a wild pet keeps the meat for smoking rather than cook it
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))

SLOTS["wool_cloak"] = "cloak"  # its own slot: never armor (spec resolution 22)


def winter_goal(s: Situation) -> bool:
    goal = active(s)
    return goal is not None and goal.name == GOAL


# The wool cloak ----------------------------------------------------------------------------------

def cloak_wanted(s: Situation) -> bool:
    return unlocked(s, "cloak") and held(s, "wool_cloak") == 0


def cloak_plan(s: Situation) -> list[dict] | None:
    if not cloak_wanted(s) or s.count("wool") < CLOAK_WOOL:
        return None
    return s.sensed("cloak_plan", lambda: gear_steps(s, ("wool_cloak",)))


def keep_wool(s: Situation, item: str) -> float:
    """storage.KEEPS_MORE: the cloak's wool stays on hand while Mimo wants a cloak."""
    return CLOAK_WOOL if item == "wool" and cloak_wanted(s) else 0.0


def wool_back(s: Situation) -> dict[str, int]:
    """storage.TAKES_MORE: the cloak's wool back out of the chest once Mimo's arms and chests hold enough."""
    if not cloak_wanted(s) or s.count("wool") >= CLOAK_WOOL or held(s, "wool") < CLOAK_WOOL:
        return {}
    return {"wool": CLOAK_WOOL - s.count("wool")}


def plan_cloak(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] > 0:
        return []
    return list(cloak_plan(s) or [])


register(Purpose(
    "make_cloak", "make a wool cloak", "Make a wool cloak from five wool at a crafting table: it keeps you warm.",
    valid=lambda s: not s.night and cloak_plan(s) is not None,
    facts=lambda s: f"carrying {s.count('wool')} wool; five make a cloak",
    score=lambda s: 55.0 + s.trait("caution") / 10, plan=plan_cloak,
    thoughts=("A warm cloak for the cold days.", "Five wool, one cloak.")))


# The hearth --------------------------------------------------------------------------------------

def hearth_spot(s: Situation) -> Cell | None:
    """The room cell of Mimo's home the hearth goes in: one with walls on two sides (a front corner, clear of
    the way in and of the bed and chest corners), the nearest home's cell; None when none is free."""
    structure = home_structure(s)
    if structure is None or structure["status"] != "done":
        return None
    blueprint = blueprint_of(structure)
    walls = {planned.cell for planned in blueprint.parts("wall")}
    level = blueprint.anchor[1]
    corners = [planned.cell for planned in blueprint.parts("room") if planned.cell[1] == level
               and sum((planned.cell[0] + dx, level, planned.cell[2] + dz) in walls for dx, dz in SIDES) >= 2
               and s.grid.material(*planned.cell) == "air"]
    return min(corners, key=lambda cell: (math.dist(cell, blueprint.anchor), cell)) if corners else None


def hearth_plan(s: Situation) -> list[dict] | None:
    """Make the hearth when Mimo carries none, walk home and put it in its corner; None when it cannot now."""
    def look() -> list[dict] | None:
        if not (winter_goal(s) and unlocked(s, "hearth")) or hearth_home(s):
            return None
        spot = hearth_spot(s)
        if spot is None:
            return None
        blueprint = blueprint_of(home_structure(s))
        if s.distance(blueprint.anchor) > HOME_RANGE:
            return None
        steps: list[dict] = []
        if s.count("hearth") < 1:
            crafting = gear_steps(s, ("hearth",))
            if crafting is None:
                return None
            steps.extend(crafting)
        if s.here not in blueprint.stands or math.dist(s.here, spot) > REACH:
            steps.append(whole_walk(blueprint.anchor))
        return steps + [{"kind": "place", "target": list(spot), "block": "hearth"}]
    return s.sensed("hearth_plan", look)


def plan_hearth(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] > 0:
        return []
    return list(hearth_plan(s) or [])


register(Purpose(
    "build_hearth", "build a hearth", "Build a stone hearth in the corner of home: it keeps the home warm all winter.",
    valid=lambda s: not s.night and hearth_plan(s) is not None,
    facts=lambda s: f"{s.count('cobblestone')} cobblestone carried; a hearth takes 8 and a campfire",
    score=lambda s: HEARTH_SCORE, plan=plan_hearth,
    thoughts=("A hearth will keep the cold out.", "Stone and fire: a hearth for the winter.")))


# Smoked meat -------------------------------------------------------------------------------------

def smoke_fire(grid, state: dict) -> bool:
    return bool(stations_near(grid, as_cell(state["position"])).intersection(SMOKE_FIRES))


def smoked(inventory: dict, item: str) -> dict:
    """`inventory` once 1 of `item` and a stick are smoked into 1 smoked meat."""
    after = take_items(inventory, {item: 1, "sticks": 1})
    add_item(after, "smoked_meat")
    return after


def start_smoke(spec: dict, state: dict, grid, at: float, scale: float) -> dict:
    item = spec["item"]
    if item not in SMOKABLE:
        raise StepFailed(f"{label(item)} cannot be smoked")
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to smoke", "missing_item")
    if state["inventory"].get("sticks", 0) < 1:
        raise StepFailed("no stick to smoke it over", "missing_item")
    if not smoke_fire(grid, state):
        raise StepFailed("no fire to smoke it over", "missing_item")
    room_to_make(state["inventory"], smoked(dict(state["inventory"]), item), "smoked_meat")
    return {"kind": "smoke", "started_at": at, "ends_at": round(at + SMOKE_SECONDS / scale, 3), "item": item}


def finish_smoke(step: dict, state: dict, grid, at: float) -> tuple[str, str]:
    if not smoke_fire(grid, state):
        raise StepFailed("the fire went out", "missing_item")
    state["inventory"] = smoked(state["inventory"], step["item"])
    return "smoke", f"{state['name']} smoked {label(step['item'])}."


register_step(StepKind("smoke", start_smoke, finish_smoke, "cooking", string_field="item"))


def smoke_wanted(s: Situation) -> int:
    """Smoked meat the winter goal wants now: up to SMOKED_WANTED held, and for a wild pet as much again as its chests'
    winter food falls short (its cooked meat spoils before winter day 5 unless stored in the last days of autumn,
    and smoked meat never does: on the gate's fourth run taught pets smoked once or twice a life and four of six
    chests held under WINTER_FOOD on a winter's first day)."""
    if not (preparing(s) and unlocked(s, "smoking")):  # all autumn, whatever the goal (the W2 dry run's ruling)
        return 0
    wanted = SMOKED_WANTED - held(s, "smoked_meat")
    if is_wild(s.state):
        wanted = max(wanted, math.ceil(max(0.0, WINTER_FOOD - winter_food(s)) / FOOD["smoked_meat"]))
    return max(0, wanted)


def spare_meat(s: Situation) -> tuple[str, ...]:
    """cooking.SPARED: a wild pet that is not hungry leaves the meat the winter goal wants smoked uncooked, while it
    can smoke it now (raw meat it cannot smoke is cooked before it spoils)."""
    if not is_wild(s.state) or s.vitals["hunger"] < SPARE_ABOVE or smoke_plan(s) is None:
        return ()
    return SMOKABLE


def has_sticks(inventory: dict) -> bool:
    """A stick carried, or one Mimo can make from what it carries."""
    try:
        make(inventory, "sticks", 1, [])
    except Short:
        return False
    return True


def smoke_plan(s: Situation) -> list[dict] | None:
    """Smoke the raw meat Mimo carries at a fire within reach (relit, or a campfire it puts down and picks up
    after), while the winter goal wants more smoked meat (`smoke_wanted`); None when it cannot now."""
    def look() -> list[dict] | None:
        wanted = smoke_wanted(s)
        if wanted <= 0:
            return None
        raw = [item for item in SMOKABLE if s.count(item) > 0]
        if not raw:
            return None
        inventory, steps, placed = dict(s.inventory), [], []
        if not has_sticks(dict(inventory)):
            return None
        x, _, z = s.here
        if not s.grid.placed_near(x, z, STATION_REACH, WORKSTATIONS).intersection(SMOKE_FIRES):
            relit = relight_steps(s, STATION_REACH) if unlocked(s, "fire") else []
            if relit:
                steps.extend(relit)
                inventory["sticks"] -= 1
            elif not (unlocked(s, "fire")
                      and station(inventory, "campfire", roofed_first(s, station_spots(s)), steps, placed, ("campfire",))):
                fires = sorted((found for found in s.grid.placed_cells(x, z, FIRE_TRAVEL, SMOKE_FIRES)
                                if not near_failure(s.state, found[0])), key=lambda found: s.distance(found[0]))
                return [whole_walk(fires[0][0], FIRE_STAND)] if fires else None  # to a fire it has, as cook does
        need = min(wanted, sum(s.count(item) for item in raw))
        if inventory.get("sticks", 0) < need:  # a stick each, made from planks or logs (on the gate's taught runs a pet
            try:                                # carrying twelve raw meats in autumn had no stick and smoked none)
                make(inventory, "sticks", need, steps)
            except Short:
                pass
        for item in raw:
            while wanted > 0 and inventory.get(item, 0) > 0 and inventory.get("sticks", 0) > 0:
                steps.append({"kind": "smoke", "item": item})
                inventory[item] -= 1
                inventory["sticks"] -= 1
                wanted -= 1
        if not any(step["kind"] == "smoke" for step in steps):
            return None
        steps.extend({"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(placed))
        return steps if crafts_fit(s.inventory, steps) else None
    return s.sensed("smoke_plan", look)


def plan_smoke(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] > 0:
        return []
    return list(smoke_plan(s) or [])


register(Purpose(
    "smoke_meat", "smoke meat", "Smoke raw meat over a fire with a stick each: smoked meat keeps all winter.",
    valid=lambda s: not s.night and smoke_plan(s) is not None,
    facts=lambda s: f"{held(s, 'smoked_meat')} of {SMOKED_WANTED} smoked meat; {s.count(*SMOKABLE)} raw meat carried",
    score=lambda s: SMOKE_SCORE, plan=plan_smoke,
    thoughts=("Smoked meat will keep all winter.", "A little smoke, and this meat will last.")))

storage.KEEPS_MORE.append(keep_wool)
storage.TAKES_MORE.append(wool_back)
SPARED.append(spare_meat)
