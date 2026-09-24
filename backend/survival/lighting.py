"""light_up: torches around home for the night.

From 5 game minutes before dusk until nightfall, at the shelter it built, Mimo puts a torch on
each outside corner the design marked (up to four) that is still dark, making torches from coal
and sticks (1 coal and 1 stick make 4) when it carries none. Torches glow at night in the viewer
and each one lifts Mimo's mood a little (building.note_building); in sub-project 3 they will keep
creatures away. A mushroom or sapling on a corner is mined first (structures.clearing). The
walks to the corners go all the way or not at all, and head_home leaves light_up alone, since it
keeps Mimo at home.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival.building import current_shelter
from backend.survival.carrying import crafts_fit
from backend.survival.foraging import reach_steps, whole_walk
from backend.survival.grid import Cell
from backend.survival.purposes import LATE_DAY, Purpose, register
from backend.survival.situation import NIGHTFALL, Situation
from backend.survival.structures import blueprint_of, clearing, todo
from backend.survival.toolmaking import Short, make

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

HOME_REACH = 16.0  # light_up is offered this close to the shelter


def dark_corners(s: Situation) -> list[Cell]:
    """The shelter's torch cells without a torch that one can stand in now (open, on solid ground)."""
    structure = current_shelter(s)
    if structure is None or structure["status"] != "done":
        return []
    blueprint = blueprint_of(structure)
    if s.distance(blueprint.anchor) > HOME_REACH:
        return []
    return [planned.cell for planned in todo(s.grid, blueprint, ("torch",))
            if s.grid.standable(planned.cell)]


def evening(s: Situation) -> bool:
    return not s.night and LATE_DAY <= s.clock["seconds_into_day"] < NIGHTFALL


def torch_supply(s: Situation, wanted: int) -> tuple[list[dict], int]:
    """Craft steps making torches (4 at a time) until Mimo has `wanted`, or as many as it can with
    room to carry them (carrying.crafts_fit), and how many it will then carry."""
    inventory, steps = dict(s.inventory), []
    while inventory.get("torch", 0) < wanted:
        trial, more = dict(inventory), []
        try:
            make(trial, "torch", inventory.get("torch", 0) + 1, more)
        except Short:
            break
        if not crafts_fit(s.inventory, steps + more):
            break
        inventory, steps = trial, steps + more
    return steps, inventory.get("torch", 0)


def light_valid(s: Situation) -> bool:
    return evening(s) and bool(dark_corners(s)) and torch_supply(s, 1)[1] > 0


def plan_light(s: Situation, context: ActionContext) -> list[dict]:
    if not evening(s) or s.brain["batches"] > 0:
        return []
    corners = dark_corners(s)
    crafting, have = torch_supply(s, len(corners))
    jobs = [(cell, [*clearing(s.grid, cell), {"kind": "place", "target": list(cell), "block": "torch"}])
            for cell in corners[:have]]
    if not jobs:
        return []
    home = blueprint_of(current_shelter(s)).anchor
    return crafting + reach_steps(s, jobs) + [whole_walk(home)]  # and back inside for the night


register(Purpose(
    "light_up", "light torches", "Put torches around home before night; they glow in the dark.",
    valid=light_valid,
    facts=lambda s: f"{len(dark_corners(s))} dark corners around home, carrying {s.count('torch')} torches",
    score=lambda s: 72.0, plan=plan_light,
    thoughts=("A little light for the night.", "Torches make home feel safe.")))
