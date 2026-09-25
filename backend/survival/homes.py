"""A bigger stone home (L4): the better_home goal and its improve_home purpose.

The first shelter is as big as Mimo's materials and creativity allowed (blueprints.design_shelter).
Once it lives in one, a better home is a goal: a shelter of a bigger tier (4x3 or 5x4 inside) with
cobblestone walls, whatever Mimo's thrift. improve_home designs it near home (blueprints.find_site
keeps off everything already built): the largest bigger tier the blocks Mimo carries cover, else
the next tier up, named like "Pip's Peaked Stone House". It starts the shelter once Mimo carries
half the blocks, as build_shelter starts a first one, and places the first batch. From then on it
is the newest shelter near Mimo, so build_shelter goes on with it; when its last floor, wall or
roof block is down, home moves into it (building.finish_if_built) and build_shelter furnishes it.

improve_home is offered only while the better home is Mimo's goal, by day, with no bigger shelter
already rising: a pet does not start a second house for the fun of it. Work band: 60 plus a tenth
of creativity. The goal is open while home can grow (it is not the biggest tier yet) and is done
when Mimo lives in a stone home of a bigger tier than the first shelter it finished; its rules
score is 45 plus a tenth of creativity.

When no site fits near home, the goal's first milestone is to find one: the "site" trip
(backend.survival.trips), "scout for a building site", heads for flat dry ground (the terrain
within 3 blocks of a spot at most 1 block uneven is sure, 2 likely) within 32 blocks of home.
After each walk Mimo tries the bigger design where it stands; a site that fits is remembered as a
"site" landmark, better_design looks there too, and improve_home follows.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, terrain_height
from backend.survival.blueprints import NAMES, TIERS, Blueprint, bill, find_site, shelter, style_for
from backend.survival.building import START_SHARE, build_batch, carried_blocks, site_center
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.grid import Cell
from backend.survival.life_goals import all_structures, built_share, first_home, home_structure, shelters, whole
from backend.survival.memory import cell_of, remember
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.structures import start
from backend.survival.trips import Find, Reason, register_reason

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

STONE = "cobblestone"
GOAL = "better_home"
SITE = "site"  # a landmark: where a bigger home fits, found on a trip
SITE_REACH = 32.0  # blocks from home a site trip looks
FLAT = ((-3, -3), (-3, 0), (-3, 3), (0, -3), (0, 0), (0, 3), (3, -3), (3, 0), (3, 3))


def rank(structure: dict) -> int:
    """A shelter's tier: 0 for 3x3, 1 for 4x3, 2 for 5x4 inside."""
    size = tuple(structure["data"].get("style", {}).get("size") or TIERS[0])
    return TIERS.index(size) if size in TIERS else 0


def moved_up(s: Situation) -> bool:
    """Mimo lives in a stone home of a bigger tier than the first shelter it finished."""
    home, first = home_structure(s), first_home(s)
    return (home is not None and first is not None and rank(home) > rank(first)
            and home["data"].get("style", {}).get("wall") == STONE)


def rising(s: Situation) -> dict | None:
    """A bigger shelter Mimo started after the one it lives in and has not finished."""
    home = home_structure(s)
    if home is None:
        return None
    return next((found for found in reversed(shelters(s)) if found["id"] > home["id"] and found["status"] == "building"
                 and rank(found) > rank(home)), None)


def can_grow(s: Situation) -> bool:
    """Mimo lives in a shelter it built that is not the biggest tier."""
    home = home_structure(s)
    return home is not None and rank(home) < len(TIERS) - 1


def design_near(s: Situation, center: Cell) -> Blueprint | None:
    """A bigger stone home at the nearest site to `center`: the largest bigger tier the blocks Mimo
    carries cover, else the next tier up; None when none fits there."""
    home = home_structure(s)
    style = replace(style_for(s.state.get("traits", {}), s.seed, len(all_structures(s))), wall=STONE)
    have, bigger = carried_blocks(s), TIERS[rank(home) + 1:]
    for size in reversed(bigger):
        site = find_site(s.grid, center, size, style.doors, style.roof)
        if site is None:
            continue
        design = shelter(site, style, f"{s.state['name']}'s {NAMES[style.roof]} Stone House")
        if bill(design, s.grid) <= have or size == bigger[0]:
            return design
    return None


def better_design(s: Situation) -> Blueprint | None:
    """A bigger stone home near home or at a site Mimo found (looked for once per Situation), or None
    when home is as big as a shelter gets or no site fits."""
    def look() -> Blueprint | None:
        if not can_grow(s):
            return None
        home = site_center(s)
        centers = [home, *(cell_of(place) for place in s.places if place["kind"] == SITE
                           and math.hypot(place["x"] - home[0], place["z"] - home[2]) <= SITE_REACH)]
        return next((design for design in map(lambda center: design_near(s, center), centers) if design), None)
    return s.sensed("better_design", look)


def blocks_wanted(s: Situation) -> int:
    """The blocks Mimo carries before it starts the bigger home: half of what it takes."""
    design = better_design(s)
    return round(START_SHARE * bill(design, s.grid)) if design is not None else 0


def improving(s: Situation) -> bool:
    goal = active(s)
    return goal is not None and goal.name == GOAL


def improve_valid(s: Situation) -> bool:
    if s.night or not improving(s) or rising(s) is not None:
        return False
    return better_design(s) is not None and carried_blocks(s) >= blocks_wanted(s)


def improve_facts(s: Situation) -> str:
    design = better_design(s)
    size = "x".join(str(side) for side in design.style["size"])
    return (f"{design.name} ({size} inside, stone walls) would need {bill(design, s.grid)} blocks, "
            f"carrying {carried_blocks(s)}")


def plan_improve(s: Situation, context: ActionContext) -> list[dict]:
    """Start the bigger home and place its first blocks; build_shelter goes on with it."""
    if s.db is None or s.brain["batches"] > 0 or not improve_valid(s):
        return []
    design = better_design(s)
    start(s.db, s.grid, design, s.at)
    return build_batch(s, design)


register(Purpose(
    "improve_home", "build a bigger home",
    "Start a bigger home with stone walls near the old one; it moves in when the roof is on.",
    valid=improve_valid, facts=improve_facts, score=lambda s: 60.0 + s.trait("creativity") / 10, plan=plan_improve,
    thoughts=("A bigger home, with stone walls this time.", "Room to stretch out. Let's build it.")))


def home_blocks(s: Situation) -> float:
    if moved_up(s) or rising(s) is not None:
        return 1.0
    wanted = blocks_wanted(s)
    return carried_blocks(s) / wanted if wanted else 0.0


def site_known(s: Situation) -> float:
    return whole(moved_up(s) or rising(s) is not None or better_design(s) is not None)


register_goal(Goal(
    GOAL, "A bigger stone home",
    "The first shelter is small: a bigger home with stone walls is roomier, warmer and safer.",
    (Milestone("Find a site for it", site_known, ("improve_home", "explore")),
     Milestone("Gather blocks for a bigger home", home_blocks, ("gather_stone", "gather_wood", "improve_home")),
     Milestone("Raise its stone walls and roof", lambda s: 1.0 if moved_up(s) else built_share(s, rising(s)),
               ("build_shelter", "improve_home", "gather_stone", "gather_wood")),  # more blocks as they run out
     Milestone("Move in", lambda s: whole(moved_up(s)), ("build_shelter",))),
    score=lambda s: 45.0 + s.trait("creativity") / 10, thought="A bigger home, with stone walls this time.",
    after=("first_shelter",), valid=lambda s: rising(s) is not None or can_grow(s)))


# The trip for a site ---------------------------------------------------------------------------

def site_trip(s: Situation) -> str | None:
    if not improving(s) or rising(s) is not None or not can_grow(s) or better_design(s) is not None:
        return None
    return "no site near home fits a bigger home"


def site_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    heights = [terrain_height(x + dx, z + dz, s.seed) for dx, dz in FLAT]
    if min(heights) <= SEA_LEVEL:
        return 0.0, ""
    spread = max(heights) - min(heights)
    return (1.0, "flat ground") if spread <= 1 else (0.4, "gentle ground") if spread <= 2 else (0.0, "")


def site_look(s: Situation, context) -> Find | None:
    """Try the bigger design where Mimo stands (a trip's walk ends on the ground)."""
    if design_near(s, s.here) is None:
        return None
    return Find("flat ground for a bigger home", True, remember(s.db, SITE, s.here, s.at))


register_reason(Reason(
    "site", "scout for a building site", site_trip, site_value, lambda s: 40.0 + s.trait("creativity") / 10,
    goals=(GOAL,), look=site_look, reach=SITE_REACH))
