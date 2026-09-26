"""The workshop (Making, T1): a crafting table, a furnace, a kiln and a barrel under one roof, by home.

The spec: "A 'workshop' structure (a crafting table, furnace, kiln and barrel under one roof) becomes a
goal." The workshop is a structure of its own (kind "workshop"), designed like a first shelter
(blueprints.shelter: 3x3 inside, flat roof, a door and a window high in each side wall) on the nearest
site within WORKSHOP_REACH blocks of home's surface, and then fitted out (`design_workshop`):
- its roof is of slabs (any building block stands in when Mimo has none), with a trapdoor for a hatch
  over the middle, where the home cell of a shelter would be;
- the bed's corner holds the crafting table and the chest's the barrel; the two front corners inside
  the furnace and the kiln; the back middle a seat (a stair block) at the bench;
- iron bars in its two windows, a sign by the door where a shelter's campfire goes, and torches at the
  outside corners as a shelter's.
Mimo stands in the rest of the inside (the door's passage and the two side cells) to build it.

build_workshop ("build the workshop") starts it while the workshop is Mimo's goal, by day, by home
(pens.near_home), once Mimo carries half the blocks its walls and roof take (as build_shelter starts a
first shelter); from then on it goes on with it whenever it can: the walls and roof first, 12 blocks a
batch (building.structural_batch, making the slabs for the roof first when Mimo has planks to spare),
then the fixtures, up to FIXTURES_PER_BATCH a batch, made where Mimo stands with the stations they need
(making.craft_plan) and put in from inside. When the walls and roof stand the workshop is done
(building.finish_if_built: "Pip built Pip's Workshop."); fitting it out goes on after. Work band: 55 plus
a tenth of creativity.

The workshop goal ("A workshop", after a home and iron tools, for the bars): fire bricks for the kiln,
raise the walls and roof, put in the crafting table, furnace, kiln and barrel, then the bars, the hatch,
the seat and the sign. While it is the goal or the workshop is being built, its fixtures and slabs are
what it wants made (making.NEEDS) and its walls and roof what gathering aims for
(building.MORE_BLOCKS). Rules score 40 plus a tenth of creativity and a twentieth of diligence, and
UNDER_WAY more once its walls and roof stand. The Making final fix wave (C1): gather_stone works toward the
furnace's and kiln's cobblestone, gather_wood toward the barrel's, hatch's, seat's and sign's planks and
mine_ore toward the bars' iron (making.MINED), so none waits for another goal to be offered; the fixtures
are made at the workshop's own table and furnace once they are in (`at_bench`).
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.survival.blueprints import Blueprint, Planned, bill, find_site, shelter, style_for
from backend.survival.building import (
    MORE_BLOCKS, START_SHARE, carried_blocks, site_center, structural_batch,
)
from backend.survival.goals import Goal, Milestone, active, reached, register_goal
from backend.survival.home import all_structures, home_structure
from backend.survival.making import LATER, NEEDS, after_steps, craft_plan, place_steps
from backend.survival import storage
from backend.survival.pens import near_home
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.structures import blocked, blueprint_of, clearing, start, todo
from backend.survival.foraging import reach_steps, whole_walk

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

GOAL = "workshop"
KIND = "workshop"
WORKSHOP_REACH = 16  # blocks from home's surface to the workshop's middle, at most
SIZE = (3, 3)
FIXTURES_PER_BATCH = 4
WORKSHOP_BATCHES = 8
ROOF = "slab"
FITTED = ("crafting_table", "furnace", "kiln", "barrel")  # the four the spec names
FIXTURE_ORDER = FITTED + ("iron_bars", "trapdoor", "stairs", "sign", "torch")
FIXTURE = "fixture"
BENCH = ("crafting_table", "furnace")  # the fixtures the rest are made at, once they are in
UNDER_WAY = 25.0  # the final fix wave: the goal's rules score once the workshop's walls and roof stand


# The design --------------------------------------------------------------------------------------

def fitted_out(base: Blueprint, site, owner: str) -> Blueprint:
    """A shelter's design turned into a workshop's (see the module docstring)."""
    width, depth = site.size
    door, middle = (width - 1) // 2, (depth - 1) // 2
    floor = site.floor
    inside = {site.world(0, 0, floor + 1): "furnace", site.world(width - 1, 0, floor + 1): "kiln",
              site.world(door, depth - 1, floor + 1): "stairs"}
    hatch = site.world(door, middle, floor + 3)
    swaps = {"bed": "crafting_table", "chest": "barrel", "campfire": "sign"}
    cells: list[Planned] = []
    for planned in base.cells:
        if planned.part in swaps:
            cells.append(Planned(planned.cell, FIXTURE, swaps[planned.part]))
        elif planned.part == "torch":
            cells.append(Planned(planned.cell, FIXTURE, "torch"))
        elif planned.cell in inside and planned.part == "room":
            cells.append(Planned(planned.cell, FIXTURE, inside[planned.cell]))
        elif planned.part == "roof" and planned.cell == hatch:
            cells.append(Planned(planned.cell, FIXTURE, "trapdoor"))
        elif planned.part == "roof":
            cells.append(Planned(planned.cell, "roof", ROOF))
        else:
            cells.append(planned)
    cells += [Planned(site.world(i, middle, floor + 2), FIXTURE, "iron_bars") for i in (-1, width)]
    taken = {planned.cell for planned in cells if planned.part == FIXTURE}
    stands = tuple(stand for stand in base.stands if stand not in taken)
    return Blueprint(KIND, f"{owner}'s Workshop", base.anchor, tuple(cells), stands, base.front,
                     {**base.style, "roof_block": ROOF})


def design_workshop(grid, seed: str, center, traits: dict, owner: str, salt: int = 0) -> Blueprint | None:
    """The workshop on the nearest site to `center` (home's surface) where a flat-roofed 3x3 building
    with a window in each side wall fits, or None."""
    style = replace(style_for(traits, seed, salt), roof="flat", windows="sides")
    site = find_site(grid, center, SIZE, style.doors, style.roof, reach=WORKSHOP_REACH)
    if site is None:
        return None
    return fitted_out(shelter(site, style, owner), site, owner)


# Where it stands ---------------------------------------------------------------------------------

def current_workshop(s: Situation) -> dict | None:
    """The workshop Mimo started, the newest (there is only ever one), or None."""
    found = [structure for structure in all_structures(s) if structure["kind"] == KIND]
    return found[-1] if found else None


def workshop_design(s: Situation) -> Blueprint | None:
    """A new workshop's design by home (looked for once per Situation)."""
    return s.sensed("workshop design", lambda: design_workshop(
        s.grid, s.seed, site_center(s), s.state.get("traits", {}), s.state["name"], len(all_structures(s))))


def fixtures_left(s: Situation, blueprint: Blueprint) -> list[Planned]:
    """The fixtures still to go in, the four the spec names first."""
    left = todo(s.grid, blueprint, (FIXTURE,))
    return sorted(left, key=lambda planned: FIXTURE_ORDER.index(planned.block) if planned.block in FIXTURE_ORDER
                  else len(FIXTURE_ORDER))


def working_on(s: Situation) -> bool:
    """The workshop is Mimo's goal, or one is being built."""
    goal = active(s)
    workshop = current_workshop(s)
    return (goal is not None and goal.name == GOAL) or (workshop is not None and workshop["status"] == "building")


def workshop_needs(s: Situation) -> dict[str, int]:
    """making.NEEDS: the fixtures still missing, and slabs for the roof still to go on, while the
    workshop is being worked on."""
    workshop = current_workshop(s)
    if not working_on(s) and (workshop is None or workshop["status"] != "done"):
        return {}
    blueprint = blueprint_of(workshop) if workshop is not None else workshop_design(s)
    if blueprint is None:
        return {}
    wanted: dict[str, int] = {}
    for planned in fixtures_left(s, blueprint):
        wanted[planned.block] = wanted.get(planned.block, 0) + 1
    roof = sum(1 for planned in todo(s.grid, blueprint, ("roof",)))
    if roof:
        wanted[ROOF] = roof
    return wanted


def walls_left(s: Situation) -> int:
    """building.MORE_BLOCKS: the blocks the workshop's walls still take while Mimo works on it."""
    if not working_on(s):
        return 0
    workshop = current_workshop(s)
    blueprint = blueprint_of(workshop) if workshop is not None else workshop_design(s)
    return 0 if blueprint is None else len(todo(s.grid, blueprint, ("floor", "wall")))


def kiln_wanted(s: Situation) -> bool:
    """The Making final fix wave: the workshop goal is not reached and its kiln is not in yet (read once per
    Situation). Clay is rare, and the way to the computer runs through the kiln: the clay Mimo digs is kept
    for it meanwhile (making.LATER), and the cozy home's flower pot waits for it (backend.survival.cozy)."""
    def look() -> bool:
        if GOAL in reached(s):
            return False
        workshop = current_workshop(s)
        return workshop is None or any(planned.block == "kiln" for planned in fixtures_left(s, blueprint_of(workshop)))
    return s.sensed("workshop kiln wanted", look)


def workshop_later(s: Situation) -> dict[str, int]:
    """making.LATER: the kiln, while `kiln_wanted`."""
    return {"kiln": 1} if kiln_wanted(s) else {}


def stations_at_home(s: Situation, item: str) -> float:
    """storage.KEEPS_MORE (the Making final fix wave): once the workshop's own crafting table and furnace are
    in, the ones Mimo carries go in the chest: what it makes at home it makes there (`at_bench`, and
    build_machine at the workshop), and they took two of its 16 stacks. On the gate's route check pets with
    the spark, the wire and a lamp's copper in hand had no room left to make the lamp's torch. Out in the
    field, craft_tools makes a table again from four planks when it needs one."""
    if item not in BENCH:
        return 0.0
    workshop = current_workshop(s)
    if workshop is None or workshop["status"] != "done":
        return 0.0
    return -1.0 if at_bench(s, blueprint_of(workshop)) is not s else 0.0


NEEDS.append(workshop_needs)
LATER.append(workshop_later)
MORE_BLOCKS.append(walls_left)
storage.KEEPS_MORE.append(stations_at_home)
storage.KEEP.update({station: 1 for station in BENCH if station not in storage.KEEP})  # one of each is carried


# build_workshop ----------------------------------------------------------------------------------

def slabs_first(s: Situation, blueprint: Blueprint) -> tuple[list[dict], Situation]:
    """Steps that make the slabs the roof still wants beyond those carried, when Mimo can make them
    where it stands (outside: inside the workshop there is no room to put a table down) and carry
    them, and `s` as it will be after them (the same Situation when none)."""
    short = len(todo(s.grid, blueprint, ("roof",))) - s.count(ROOF)
    steps = craft_plan(s, {ROOF: s.count(ROOF) + short}) if short > 0 else None
    if not steps:
        return [], s
    return steps, replace(s, state={**s.state, "inventory": after_steps(s.inventory, steps)}, memo={})


def at_bench(s: Situation, blueprint: Blueprint) -> Situation:
    """`s` as Mimo will be inside the workshop, once its own crafting table and furnace are in (the Making
    final fix wave, as build_machine works at them): the kiln's bricks are fired there. Before, it made
    and carried a table and a furnace of its own wherever it stood, and on the gate's route check a pet
    with the kiln's clay in hand lacked the furnace's 8 cobblestone besides, so it never made the kiln.
    `s` itself until both are in."""
    placed = {planned.block for planned in blueprint.parts(FIXTURE)
              if planned.block in BENCH and s.grid.material(*planned.cell) == planned.block}
    if placed != set(BENCH):
        return s
    return replace(s, state={**s.state, "position": dict(zip("xyz", map(float, blueprint.anchor)))}, memo={})


def fixture_batch(s: Situation, blueprint: Blueprint) -> list[dict]:
    """Make the next fixtures Mimo can (up to FIXTURES_PER_BATCH, a torch only when it carries one), at the
    workshop's own crafting table and furnace once they are in (`at_bench`, walking in first), and put them
    in from inside."""
    where = at_bench(s, blueprint)
    chosen: list[Planned] = []
    for planned in fixtures_left(s, blueprint):
        trial = {}
        for item in [entry.block for entry in chosen + [planned]]:
            trial[item] = trial.get(item, 0) + 1
        if craft_plan(where, trial) is not None:
            chosen.append(planned)
        if len(chosen) >= FIXTURES_PER_BATCH:
            break
    if not chosen:
        return []
    wanted: dict[str, int] = {}
    for planned in chosen:
        wanted[planned.block] = wanted.get(planned.block, 0) + 1
    crafting = craft_plan(where, wanted) or []
    walk = [whole_walk(where.here)] if crafting and where is not s and where.here != s.here else []
    jobs = [(planned.cell, [*clearing(s.grid, planned.cell),
                            {"kind": "place", "target": list(planned.cell), "block": planned.block}])
            for planned in chosen]
    return walk + crafting + place_steps(s, blueprint.stands, jobs, at=where.here if walk else None)


def next_batch(s: Situation, blueprint: Blueprint) -> list[dict]:
    """Clear a blocked door or way in, then the walls and roof, then the fixtures."""
    clear = reach_steps(s, [(cell, [{"kind": "mine", "target": list(cell)}]) for cell in blocked(s.grid, blueprint)])
    if todo(s.grid, blueprint):
        slabs, after = slabs_first(s, blueprint)
        stand = s.here if s.here in blueprint.stands else blueprint.stands[0]
        walk = [] if stand == s.here else [whole_walk(stand)]
        work = structural_batch(after, blueprint, stand)
        return clear + slabs + walk + work if work else clear
    return clear + fixture_batch(s, blueprint)


def workshop_valid(s: Situation) -> bool:
    if s.night or not near_home(s) or home_structure(s) is None or home_structure(s)["status"] != "done":
        return False
    workshop = current_workshop(s)
    if workshop is None:
        goal = active(s)
        design = workshop_design(s) if goal is not None and goal.name == GOAL else None
        return design is not None and carried_blocks(s) >= START_SHARE * bill(design, s.grid)
    return bool(next_batch(s, blueprint_of(workshop)))


def workshop_facts(s: Situation) -> str:
    workshop = current_workshop(s)
    if workshop is None:
        design = workshop_design(s)
        return (f"no workshop yet; one by home would need {bill(design, s.grid) if design else '?'} blocks, "
                f"carrying {carried_blocks(s)}")
    blueprint = blueprint_of(workshop)
    left = [planned.block.replace("_", " ") for planned in fixtures_left(s, blueprint)]
    walls = len(todo(s.grid, blueprint))
    return (f"building {workshop['name']}: {walls} blocks of wall and roof to go, "
            f"then {', '.join(left) or 'nothing more'}")


def plan_workshop(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.db is None or s.brain["batches"] >= WORKSHOP_BATCHES or not workshop_valid(s):
        return []
    workshop = current_workshop(s)
    if workshop is None:
        blueprint = workshop_design(s)
        start(s.db, s.grid, blueprint, s.at)
    else:
        blueprint = blueprint_of(workshop)
    return next_batch(s, blueprint)


register(Purpose(
    "build_workshop", "build the workshop",
    "Build a workshop by home, block by block: a crafting table, a furnace, a kiln and a barrel under one roof.",
    valid=workshop_valid, facts=workshop_facts, score=lambda s: 55.0 + s.trait("creativity") / 10, plan=plan_workshop,
    thoughts=("A workshop of my own, for making things.", "Everything I need to make things, in one place.")))


# The workshop goal -------------------------------------------------------------------------------

def whole(done: bool) -> float:
    return 1.0 if done else 0.0


def workshop_blueprint(s: Situation) -> Blueprint | None:
    workshop = current_workshop(s)
    return None if workshop is None else blueprint_of(workshop)


def bricks_fired(s: Situation) -> float:
    """Three bricks for the kiln, carried or already in it (a kiln carried or placed counts whole)."""
    blueprint = workshop_blueprint(s)
    placed = blueprint is not None and not any(planned.block == "kiln" for planned in fixtures_left(s, blueprint))
    return whole(placed or s.count("kiln") > 0) or min(1.0, s.count("brick") / 3)


def raised(s: Situation) -> float:
    workshop = current_workshop(s)
    if workshop is None:
        return 0.0
    if workshop["status"] == "done":
        return 1.0
    blueprint = blueprint_of(workshop)
    total = bill(blueprint)
    return 1.0 - bill(blueprint, s.grid) / total if total else 1.0


def fixtures_in(s: Situation, names) -> float:
    """The share of the workshop's fixtures of these kinds that are in."""
    blueprint = workshop_blueprint(s)
    if blueprint is None:
        return 0.0
    wanted = [planned for planned in blueprint.parts(FIXTURE) if planned.block in names]
    left = [planned for planned in fixtures_left(s, blueprint) if planned.block in names]
    return 1.0 - len(left) / len(wanted) if wanted else 1.0


def goal_score(s: Situation) -> float:
    """40 plus a tenth of creativity and a twentieth of diligence, and UNDER_WAY more once its walls and roof
    stand (the Making final fix wave: finishing what it started comes first; on the gate's route check pets
    whose workshop lacked only its kiln or bars, the clay or iron in hand, chose the workshop once or twice in
    50 game days against the discovery goals, 30 plus seven tenths of curiosity, and never finished it)."""
    workshop = current_workshop(s)
    started = workshop is not None and workshop["status"] == "done"
    return 40.0 + s.trait("creativity") / 10 + s.trait("diligence") / 20 + (UNDER_WAY if started else 0.0)


register_goal(Goal(
    GOAL, "A workshop",
    "Making things wants a place of its own: a crafting table, a furnace, a kiln and a barrel under one roof.",
    (Milestone("Fire bricks for a kiln", bricks_fired, ("gather_materials", "build_workshop", "build_storage"),
               ("kiln",)),
     Milestone("Raise the workshop's walls and roof", raised, ("build_workshop", "gather_wood", "gather_stone")),
     Milestone("Put in a crafting table, a furnace, a kiln and a barrel", lambda s: fixtures_in(s, FITTED),
               ("build_workshop", "gather_materials", "gather_stone", "gather_wood", "build_storage")),
     Milestone("Fit bars, a hatch, a seat and a sign", lambda s: fixtures_in(
         s, ("iron_bars", "trapdoor", "stairs", "sign")), ("build_workshop", "mine_ore", "gather_wood", "build_storage"),
               ("iron_bars",))),
    score=lambda s: goal_score(s),
    thought="A workshop, with a kiln! Then I can make anything.", after=("first_shelter", "iron_tools")))
