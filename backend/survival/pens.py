"""build_pen and stock_pen: a fence ring by home for the animals Mimo grows from creature seeds
(spec L3: "farm purposes may plant them near home once a pen exists (a fence ring)").

build_pen lays out a pen once Mimo has a finished home, stands within 64 blocks of it and carries
a creature seed: a 5x5 ring of 16 fences around 3x3 of grass, on flat untouched ground near home
with a walkway of standable ground all round it (`design_pen`). L4a final fix wave, I1: the pen is
always home's (backend.survival.home): the site is looked for by home however far Mimo walked, a
pen counts as Mimo's only within home.YARD of home, and none is started while Mimo is out past
HOME_RANGE (a seed found on a trip 80 blocks out used to start a second pen there). The pen is a
structure (kind "pen") that claims its fences and its inside (structures.start), so no plan digs,
tills or builds there and no wild animal wanders in; it is done when the last fence stands
(building.finish_if_built). Mimo
makes the fences (4 planks and 2 sticks make 3, any wood) and places them standing on the walkway,
never inside, 8 a batch. Nothing can stand on a fence or step over one (grid.supported), so what
grows inside stays there. It is offered while Mimo can make every fence still missing, and is day
work: 45 plus a tenth of diligence and a twentieth of creativity.

stock_pen, a farm purpose, plants creature seeds on the pen's open grass from the walkway while
the pen holds fewer than PEN_ANIMALS animals and sprouts; a game day later each sprout is a tame
animal (backend.survival.creatures.seeds). The seeds wait in the chest at home (storage.KEEP keeps
none on hand), so it first takes out what it needs -- from any chest Mimo built, home's own first
(the final fix wave: an old home's chest still holds the seeds stored there before a bigger home
took over), walking into each chest's shelter as build_storage does. Day work: 50 plus a tenth of
patience.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.blocks import is_replaceable
from backend.survival.blueprints import Blueprint, Planned, Survey
from backend.survival.building import site_center
from backend.survival.carrying import crafts_fit
from backend.survival.creatures.seeds import SEED, SPROUT
from backend.survival.creatures.table import cell_of as creature_cell
from backend.survival.creatures.table import dead
from backend.survival.foraging import whole_walk
from backend.survival.grid import Cell, Grid
from backend.survival.home import YARD, by_home, from_home, home_structure
from backend.survival.purposes import HOME_RANGE, Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import REACH
from backend.survival.storage import chest_contents, chests_built
from backend.survival.structures import blueprint_of, clearing, start, todo
from backend.survival.toolmaking import Short, make

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

PEN_SIZE = 5  # fences on a side
PEN_ANIMALS = 3  # animals and sprouts a pen holds before Mimo plants more
FENCES_PER_BATCH = 8
PEN_BATCHES = 6
SITE_REACH = 10  # blocks from home's surface a pen's corner may lie


def design_pen(grid: Grid, center: Cell, owner: str, reach: int = SITE_REACH) -> Blueprint | None:
    """The nearest pen site to `center` (a cell Mimo stands in): a PEN_SIZE square of untouched
    ground at one height, grass inside, with every column of the walkway round it firm and within
    a block of that height. None when no site fits."""
    survey = Survey(grid, center[1] - 1)
    cx, _, cz = center
    spots = sorted(((math.hypot(dx, dz), dx, dz) for dx in range(-reach, reach + 1) for dz in range(-reach, reach + 1)
                    if math.hypot(dx, dz) <= reach))
    for _, dx, dz in spots:
        ox, oz = cx + dx - PEN_SIZE // 2, cz + dz - PEN_SIZE // 2
        floor = survey.height(ox, oz)
        if floor is None:
            continue
        square = [(ox + i, oz + j) for i in range(PEN_SIZE) for j in range(PEN_SIZE)]
        if any(survey.height(x, z) != floor for x, z in square):
            continue
        inside = [(x, z) for x, z in square if ox < x < ox + PEN_SIZE - 1 and oz < z < oz + PEN_SIZE - 1]
        if any(grid.material(x, floor, z) != "grass" for x, z in inside):
            continue
        walkway = [(ox + i, oz + j) for i in range(-1, PEN_SIZE + 1) for j in range(-1, PEN_SIZE + 1)
                   if i in (-1, PEN_SIZE) or j in (-1, PEN_SIZE)]
        grounds = [survey.height(x, z) for x, z in walkway]
        if any(ground is None or abs(ground - floor) > 1 for ground in grounds):
            continue
        cells = tuple(Planned((x, floor + 1, z), "fence", "fence") for x, z in square if (x, z) not in inside)
        cells += tuple(Planned((x, floor + 1, z), "pen", "air") for x, z in inside)
        stands = tuple((x, ground + 1, z) for (x, z), ground in zip(walkway, grounds))
        return Blueprint("pen", f"{owner}'s pen", (ox + PEN_SIZE // 2, floor + 1, oz + PEN_SIZE // 2), cells, stands,
                         style={"size": [PEN_SIZE, PEN_SIZE]})
    return None


def current_pen(s: Situation) -> dict | None:
    """The newest pen by home (home.YARD), wherever Mimo stands."""
    near = by_home(s, "pen", YARD)
    return near[-1] if near else None


def near_home(s: Situation) -> bool:
    """Mimo stands within HOME_RANGE of home: pen work is done by home, not on a trip."""
    away = from_home(s, s.here[0], s.here[2])
    return away is not None and away <= HOME_RANGE


def home_done(s: Situation) -> bool:
    """Fix round 1: home, not `current_shelter`'s newest shelter, which is a second one still
    rising while a bigger home is under way."""
    shelter = home_structure(s)
    return shelter is not None and shelter["status"] == "done"


def pen_design(s: Situation) -> Blueprint | None:
    return s.sensed("pen_design", lambda: design_pen(s.grid, site_center(s), s.state["name"]))


def fences_left(s: Situation, blueprint: Blueprint) -> list[Cell]:
    return [planned.cell for planned in todo(s.grid, blueprint, ("fence",))]


def fence_supply(s: Situation, wanted: int) -> tuple[list[dict], int]:
    """Craft steps making fences (3 at a time) until Mimo has `wanted`, or as many as it can with
    room to carry them, and how many it will then carry."""
    inventory, steps = dict(s.inventory), []
    while inventory.get("fence", 0) < wanted:
        trial, more = dict(inventory), []
        try:
            make(trial, "fence", inventory.get("fence", 0) + 1, more)
        except Short:
            break
        if not crafts_fit(s.inventory, steps + more):
            break
        inventory, steps = trial, steps + more
    return steps, inventory.get("fence", 0)


def inside(blueprint: Blueprint, cell: Cell) -> bool:
    return any(planned.cell[0] == cell[0] and planned.cell[2] == cell[2] for planned in blueprint.parts("pen"))


def seeds_at_hand(s: Situation) -> int:
    """Creature seeds Mimo carries or keeps in any chest it built (storage.chests_built)."""
    return s.count(SEED) + sum(chest_contents(s, cell).get(SEED, 0) for cell, _ in chests_built(s))


def from_walkway(s: Situation, blueprint: Blueprint, jobs: list[tuple[Cell, list[dict]]],
                 at: Cell | None = None) -> list[dict]:
    """Each job's steps, walking first to the walkway cell nearest Mimo that reaches the job's cell
    whenever it is out of reach from where Mimo will be (`at`, where it stands unless given), or
    Mimo stands inside the pen."""
    steps, at = [], at or s.here
    for cell, work in jobs:
        if math.dist(at, cell) > REACH or inside(blueprint, at):
            stands = [stand for stand in blueprint.stands if math.dist(stand, cell) <= REACH]
            if not stands:
                continue
            at = min(stands, key=lambda stand: (math.dist(stand, at), stand))
            steps.append(whole_walk(at))
        steps.extend(work)
    return steps


# build_pen ---------------------------------------------------------------------------------------

def build_valid(s: Situation) -> bool:
    if s.night or not home_done(s) or not near_home(s) or seeds_at_hand(s) < 1:
        return False
    pen = current_pen(s)
    if pen is not None:
        left = fences_left(s, blueprint_of(pen))
        return pen["status"] == "building" and bool(left) and fence_supply(s, min(len(left), FENCES_PER_BATCH))[1] > 0
    return pen_design(s) is not None and fence_supply(s, 4 * (PEN_SIZE - 1))[1] >= 4 * (PEN_SIZE - 1)


def plan_build_pen(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= PEN_BATCHES or s.db is None or not near_home(s):
        return []
    pen = current_pen(s)
    if pen is None:
        design = pen_design(s)
        if design is None:
            return []
        start(s.db, s.grid, design, s.at)
        blueprint = design
    else:
        blueprint = blueprint_of(pen)
    left = fences_left(s, blueprint)[:FENCES_PER_BATCH]
    crafting, have = fence_supply(s, len(left))
    jobs = [(cell, [*clearing(s.grid, cell), {"kind": "place", "target": list(cell), "block": "fence"}])
            for cell in left[:have]]
    return crafting + from_walkway(s, blueprint, jobs) if jobs else []


register(Purpose(
    "build_pen", "build a pen",
    "Put a ring of fences up by home, for the animals creature seeds grow into.",
    valid=build_valid,
    facts=lambda s: f"{seeds_at_hand(s)} creature seeds at hand, carrying {s.count('fence')} fences; "
                    + ("a pen started" if current_pen(s) else "no pen yet"),
    score=lambda s: 45.0 + s.trait("diligence") / 10 + s.trait("creativity") / 20,
    plan=plan_build_pen,
    thoughts=("A pen would keep my animals safe.", "Fences first, then the seeds.")))


# stock_pen ---------------------------------------------------------------------------------------

def finished_pen(s: Situation) -> Blueprint | None:
    pen = current_pen(s)
    return blueprint_of(pen) if pen is not None and pen["status"] == "done" and s.distance((pen["x"], pen["y"], pen["z"])) <= HOME_RANGE else None


def pen_life(s: Situation, blueprint: Blueprint) -> int:
    """Animals standing in the pen and sprouts growing there."""
    herd = s.grid.herd
    x, _, z = blueprint.anchor
    animals = [] if herd is None else [creature for creature in herd.near(x, z, PEN_SIZE)
                                       if not dead(creature) and inside(blueprint, creature_cell(creature))]
    sprouts = [planned for planned in blueprint.parts("pen") if s.grid.material(*planned.cell) == SPROUT]
    return len(animals) + len(sprouts)


def open_plots(s: Situation, blueprint: Blueprint) -> list[Cell]:
    """The pen's inside cells where a seed can go: open, over grass, with no animal standing there."""
    herd = s.grid.herd
    x, _, z = blueprint.anchor
    taken = set() if herd is None else {creature_cell(creature) for creature in herd.near(x, z, PEN_SIZE)
                                         if not dead(creature)}
    found = []
    for planned in blueprint.parts("pen"):
        cx, cy, cz = cell = planned.cell
        material = s.grid.material(*cell)
        if (material != "water" and is_replaceable(material) and s.grid.material(cx, cy - 1, cz) == "grass"
                and cell not in taken):
            found.append(cell)
    return found


def stock_valid(s: Situation) -> bool:
    if s.night or seeds_at_hand(s) < 1:
        return False
    blueprint = finished_pen(s)
    return blueprint is not None and pen_life(s, blueprint) < PEN_ANIMALS and bool(open_plots(s, blueprint))


def plan_stock_pen(s: Situation, context: ActionContext) -> list[dict]:
    blueprint = finished_pen(s)
    if s.night or s.brain["batches"] > 0 or blueprint is None:
        return []
    room = PEN_ANIMALS - pen_life(s, blueprint)
    steps, carried, at = [], s.count(SEED), s.here
    for cell, stand in chests_built(s):
        take = min(room - carried, chest_contents(s, cell).get(SEED, 0))
        if take > 0:
            if at != stand:
                steps.append(whole_walk(stand))
                at = stand
            steps.append({"kind": "take", "target": list(cell), "item": SEED, "amount": take})
            carried += take
    jobs = [(cell, [{"kind": "plant", "target": list(cell), "item": SEED}])
            for cell in open_plots(s, blueprint)[:min(carried, room)]]
    return steps + from_walkway(s, blueprint, jobs, at) if jobs else []


register(Purpose(
    "stock_pen", "plant creature seeds",
    "Plant creature seeds in the pen by home; each grows into an animal in a day.",
    valid=stock_valid,
    facts=lambda s: f"{seeds_at_hand(s)} creature seeds at hand; the pen holds {pen_life(s, finished_pen(s))} of {PEN_ANIMALS}",
    score=lambda s: 50.0 + s.trait("patience") / 10, plan=plan_stock_pen,
    thoughts=("Something will grow from this seed.", "The pen could use a few more friends.")))
