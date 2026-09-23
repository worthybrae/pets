"""build_farm: lay out a proper farm near home.

The generator (blueprints.design_farm) picks a 3x3 rectangle of plots on flat tillable ground,
4x4 with 12 things to plant and diligence 60, 5x5 with 20 and diligence 80. When Mimo already
keeps a farm (the remembered `farm` place, where it tilled first), the rectangle is laid over
that farm and as much of its farmland as it can hold, so the old farm grows into the new shape
instead of a second one starting. With no farm yet it goes beside the nearest shore within 16
blocks of home, where crops grow three times as fast, else near home. build_farm tills the plots still
missing and plants what Mimo carries on them, carrots first, 4 plots a batch; farming then tends
them. The plots are claimed (structures.reserved), so nothing digs them up and farm leaves them to
build_farm, which is offered again when some turned back into dirt and Mimo has seeds for them.
It is day work, offered once Mimo has a home and at least 2 things to plant, and scores in the
work band.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.survival.blueprints import Blueprint, design_farm
from backend.survival.building import site_center, structures_near
from backend.survival.farming import FARM_TRAVEL, PLANTABLE, SITE_SEARCH, next_seed, open_above, plant
from backend.survival.foraging import reach_steps
from backend.survival.memory import cell_of, nearest
from backend.survival.purposes import HOME_RANGE, Purpose, late_penalty, register
from backend.survival.senses import shores_near
from backend.survival.situation import Situation
from backend.survival.structures import blueprint_of, start, todo

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

PLOTS_PER_BATCH = 4
FARM_BATCHES = 6
OLD_FARM_REACH = 3.0  # farmland this close to the remembered farm is part of it


def plantables(s: Situation) -> int:
    return s.count(*PLANTABLE)


def farm_size(s: Situation) -> int:
    count, diligence = plantables(s), s.trait("diligence")
    if count >= 20 and diligence >= 80:
        return 5
    if count >= 12 and diligence >= 60:
        return 4
    return 3


def current_farm(s: Situation) -> dict | None:
    near = structures_near(s, "farm")
    return near[-1] if near else None


def farm_design(s: Situation) -> Blueprint | None:
    """A new farm's design, over the farm Mimo keeps, else beside the nearest shore within 16
    blocks of home, else at home (looked for once per Situation)."""
    def look() -> Blueprint | None:
        if nearest(s.places, s.here, ("home",), HOME_RANGE) is None:
            return None
        old = nearest(s.places, s.here, ("farm",), FARM_TRAVEL)
        if old is not None:
            x, y, z = cell_of(old)
            tilled = tuple(cell for cell, _ in s.grid.placed_cells(x, z, OLD_FARM_REACH, ("farmland",)) if cell[1] == y)
            return design_farm(s.grid, (x, y, z), farm_size(s), s.state["name"], tilled or ((x, y, z),))
        home = site_center(s)
        shores = shores_near(s.grid, s.seed, home, SITE_SEARCH)
        x, y, z = shores[0][0] if shores else home
        return design_farm(s.grid, (x, y - 1, z), farm_size(s), s.state["name"])
    return s.sensed("farm_design", look)


def plots_left(s: Situation, blueprint: Blueprint) -> list:
    return [planned for planned in todo(s.grid, blueprint, ("plot",)) if open_above(s, planned.cell)]


def farm_valid(s: Situation) -> bool:
    if s.night or plantables(s) < 2:
        return False
    farm = current_farm(s)
    if farm is None:
        return farm_design(s) is not None
    return bool(plots_left(s, blueprint_of(farm)))


def farm_facts(s: Situation) -> str:
    farm = current_farm(s)
    if farm is None:
        design = farm_design(s)
        size = design.style["size"][0] if design else 3
        return f"no laid-out farm yet; room for a {size}x{size} farm, carrying {plantables(s)} things to plant"
    return f"{farm['name']} has {len(plots_left(s, blueprint_of(farm)))} plots to till again"


def plan_build_farm(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= FARM_BATCHES or s.db is None:
        return []
    farm = current_farm(s)
    if farm is None:
        design = farm_design(s)
        if design is None:
            return []
        start(s.db, s.grid, design, s.at)
        blueprint = design
    else:
        blueprint = blueprint_of(farm)
    inventory, jobs = dict(s.inventory), []
    nearest_first = sorted(plots_left(s, blueprint),
                           key=lambda planned: (math.dist(planned.cell, s.here), planned.cell))
    for planned in nearest_first:
        seed = next_seed(inventory)
        if seed is None or len(jobs) >= PLOTS_PER_BATCH:
            break
        inventory[seed] -= 1
        ground = planned.cell
        top = (ground[0], ground[1] + 1, ground[2])
        jobs.append((top, [{"kind": "till", "target": list(ground)}, plant(top, seed)]))
    return reach_steps(s, jobs)


register(Purpose(
    "build_farm", "lay out a farm",
    "Lay out a neat farm of 3x3 to 5x5 plots near home, beside water if it can, over the farm it keeps.",
    valid=farm_valid, facts=farm_facts,
    score=lambda s: 45.0 + s.trait("diligence") / 10 - late_penalty(s), plan=plan_build_farm,
    thoughts=("Rows of crops, right by home.", "A proper farm would feed me all year.")))
