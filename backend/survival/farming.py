"""Farming: till plots near water, plant seeds and carrots, harvest ripe crops and plant again.

The farm is where Mimo tilled first (a remembered `farm` place). With no farm yet, the first
plot goes beside the nearest shore within 16 blocks, where crops grow three times as fast, or
else on the natural surface where Mimo is. Plots are only ever tilled on the natural surface or
above, never in Mimo's own staircase or tunnels. A farm more than 24 blocks away is walked to
first, but only when there is work waiting there (ripe crops, or something to plant and a plot
for it); far from its farm Mimo does no farm work. Each batch does the most useful work it can,
at most 4 plots:
1. harvest ripe crops within 24 blocks and plant each plot again with what it gave;
2. plant empty farmland, carrots first (they feed Mimo) and then seeds;
3. till new plots next to the farm, up to 9, for the carrots and seeds left over;
4. with nothing to plant, break tall grass within 16 blocks for seeds (1 in 5 gives some, and 1
   in 20 a carrot).
The purpose ends when none of these is left, or after 6 batches. It is day work. Plots, grass
and a farm within 4 blocks of where a step just failed are left alone for a while
(senses.near_failure). It scores as work, and ripe crops lift it toward the needs band as far as
Mimo lacks food, never past 80 (farm_score).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.blocks import is_replaceable
from backend.services.worldgen import terrain_height
from backend.survival.foraging import FOOD_WANTED, food_need, reach_steps, whole_walk
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, nearest
from backend.survival.nature import CROP_BLOCKS, HARVESTS, RIPE_CROPS, TILLABLE, crop_stage
from backend.survival.purposes import Purpose, late_penalty, register
from backend.survival.senses import by_distance, grass_near, near_failure, shores_near
from backend.survival.situation import Situation

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

FARM_SIZE = 9
PLOTS_PER_BATCH = 4
GRASS_PER_BATCH = 6
FARM_BATCHES = 6
FARM_RANGE = 24.0
FARM_TRAVEL = 64.0
SITE_SEARCH = 16.0
GRASS_SEARCH = 16.0
STAND = 2.0
RIPE_BONUS = 25.0  # score for ripe crops when Mimo carries no food; less as it carries more
FARM_TOP = 80.0
PLANTABLE = ("carrot", "seeds")  # what to plant, in order of preference
SEED_OF = {"wheat": "seeds", "carrot": "carrot"}
# Plot offsets around the farm, nearest first, in a 5x5 square.
PLOT_OFFSETS = sorted(((dx, dz) for dx in range(-2, 3) for dz in range(-2, 3)),
                      key=lambda offset: (abs(offset[0]) + abs(offset[1]), offset))


def above(cell: Cell) -> Cell:
    return cell[0], cell[1] + 1, cell[2]


def open_above(s: Situation, ground: Cell) -> bool:
    material = s.grid.material(*above(ground))
    return material != "water" and is_replaceable(material)


def farm_place(s: Situation) -> dict | None:
    return nearest(s.places, s.here, ("farm",), FARM_TRAVEL)


def farm_anchor(s: Situation) -> Cell:
    """The ground cell new plots go around: the remembered farm, else beside the nearest shore
    within 16 blocks, else the natural surface of Mimo's column (not under Mimo, who may stand
    in its own staircase)."""
    farm = farm_place(s)
    if farm is not None:
        return cell_of(farm)
    shores = s.sensed("farm_shores", lambda: shores_near(s.grid, s.seed, s.here, SITE_SEARCH))
    x, _, z = shores[0][0] if shores else s.here
    return x, terrain_height(x, z, s.seed), z


def reachable(s: Situation, cells) -> list[Cell]:
    """The cells with no failed step lately within 4 blocks."""
    return [cell for cell in cells if not near_failure(s.state, cell)]


def new_plots(s: Situation, anchor: Cell) -> list[Cell]:
    """Ground cells next to the farm that can be tilled, nearest the anchor first. Only ground on
    the natural surface or above counts: below it lie Mimo's own stairs and tunnels."""
    ax, ay, az = anchor
    found = []
    for dx, dz in PLOT_OFFSETS:
        if near_failure(s.state, (ax + dx, ay, az + dz)):
            continue
        surface = terrain_height(ax + dx, az + dz, s.seed)
        for y in (ay, ay + 1, ay - 1):
            ground = (ax + dx, y, az + dz)
            if y >= surface and s.grid.material(*ground) in TILLABLE and open_above(s, ground):
                found.append(ground)
                break
    return found


def next_seed(inventory: dict) -> str | None:
    return next((item for item in PLANTABLE if inventory.get(item, 0) > 0), None)


def plant(cell: Cell, item: str) -> dict:
    return {"kind": "plant", "target": list(cell), "item": item}


def farm_jobs(s: Situation) -> list[tuple[Cell, list[dict]]]:
    """This batch's farm work as (cell, steps) jobs, before any walking."""
    x, _, z = s.here
    inventory = dict(s.inventory)
    placed = s.grid.placed_cells(x, z, FARM_RANGE, CROP_BLOCKS + ("farmland",))
    ripe = reachable(s, by_distance((cell for cell, material in placed if material in RIPE_CROPS), s.here))
    farmland = [cell for cell, material in placed if material == "farmland"]
    empty = reachable(s, by_distance((above(cell) for cell in farmland if open_above(s, cell)), s.here))
    jobs: list[tuple[Cell, list[dict]]] = []
    for cell in ripe[:PLOTS_PER_BATCH]:
        crop = s.grid.material(*cell)
        for item, amount in HARVESTS[crop].items():
            inventory[item] = inventory.get(item, 0) + amount
        seed = SEED_OF[crop_stage(crop)[0]]
        inventory[seed] -= 1
        jobs.append((cell, [{"kind": "harvest", "target": list(cell)}, plant(cell, seed)]))
    for cell in empty:
        seed = next_seed(inventory)
        if seed is None or len(jobs) >= PLOTS_PER_BATCH:
            break
        inventory[seed] -= 1
        jobs.append((cell, [plant(cell, seed)]))
    if len(jobs) < PLOTS_PER_BATCH and len(farmland) < FARM_SIZE:
        room = min(PLOTS_PER_BATCH - len(jobs), FARM_SIZE - len(farmland))
        for ground in new_plots(s, farm_anchor(s))[:room]:
            seed = next_seed(inventory)
            if seed is None:
                break
            inventory[seed] -= 1
            jobs.append((above(ground), [{"kind": "till", "target": list(ground)}, plant(above(ground), seed)]))
    if not jobs and next_seed(inventory) is None and (empty or len(farmland) < FARM_SIZE):
        grass = reachable(s, grass_near(s.grid, s.seed, s.here, GRASS_SEARCH))
        jobs = [(cell, [{"kind": "mine", "target": list(cell)}]) for cell in grass[:GRASS_PER_BATCH]]
    return jobs


def farm_work(s: Situation) -> list[tuple[Cell, list[dict]]]:
    return s.sensed("farm_jobs", lambda: farm_jobs(s))


def far_farm(s: Situation) -> dict | None:
    """The remembered farm when it lies beyond reach of the plots Mimo tends."""
    farm = farm_place(s)
    return farm if farm is not None and s.distance(cell_of(farm)) > FARM_RANGE else None


def work_waiting(s: Situation, farm: dict) -> bool:
    """Ripe crops at the farm, or something to plant and a plot for it there."""
    fx, _, fz = cell_of(farm)
    placed = s.grid.placed_cells(fx, fz, FARM_RANGE, CROP_BLOCKS + ("farmland",))
    if any(material in RIPE_CROPS for _, material in placed):
        return True
    farmland = [cell for cell, material in placed if material == "farmland"]
    return next_seed(s.inventory) is not None and (len(farmland) < FARM_SIZE
                                                   or any(open_above(s, cell) for cell in farmland))


def farm_trip(s: Situation) -> bool:
    """Walk back to a far farm: only with work waiting there, and not where a walk just failed."""
    farm = far_farm(s)
    return farm is not None and bool(reachable(s, [cell_of(farm)])) and work_waiting(s, farm)


def farm_valid(s: Situation) -> bool:
    if s.night:
        return False
    return farm_trip(s) if far_farm(s) is not None else bool(farm_work(s))


def farm_facts(s: Situation) -> str:
    x, _, z = s.here
    placed = s.grid.placed_cells(x, z, FARM_RANGE, CROP_BLOCKS + ("farmland",))
    ripe = sum(1 for _, material in placed if material in RIPE_CROPS)
    plots = sum(1 for _, material in placed if material == "farmland")
    return (f"{plots} plots and {ripe} ripe crops near, carrying {s.count('seeds')} seeds and "
            f"{s.count('carrot')} carrots")


def farm_score(s: Situation) -> float:
    """Work (40-65), plus up to 25 for ripe crops in proportion to the food Mimo lacks
    (foraging.food_need), at most 80: a ripe farm climbs into the needs band only when Mimo
    carries little food, so it never outranks eating what it carries when hungry."""
    x, _, z = s.here
    ripe = bool(s.grid.placed_cells(x, z, FARM_RANGE, RIPE_CROPS))
    score = 40.0 + s.trait("diligence") / 10 + s.trait("patience") / 20
    score += (RIPE_BONUS * food_need(s) / FOOD_WANTED if ripe else 0.0) + (10.0 if next_seed(s.inventory) else 0.0)
    return min(FARM_TOP, score) - late_penalty(s)


def plan_farm(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= FARM_BATCHES:
        return []
    if far_farm(s) is not None:
        return [whole_walk(above(cell_of(far_farm(s))), STAND)] if farm_trip(s) else []
    return reach_steps(s, farm_work(s))


register(Purpose(
    "farm", "farm", "Till plots near water, plant seeds and carrots, and harvest ripe crops.",
    valid=farm_valid, facts=farm_facts, score=farm_score, plan=plan_farm,
    thoughts=("A little farm would keep me fed.", "Time to tend the crops.")))
