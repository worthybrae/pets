"""Camping out on an expedition (L4b): digging in for the night, far from home.

From late in the day (and at night), while Mimo means to stay out (expedition.away), the `camp`
purpose makes camp: 85 late in the day, 95 at dusk and at night, and it meets a need
(goals.URGES), so goal work never crowds it out. It goes back to an outpost within OUTPOST_REUSE
blocks whose hole is still open, or picks the nearest spot within CAMP_SEARCH blocks where it can
dig in: standing on natural ground it can dig, with solid ground under that and on all four sides,
nothing it built or tends, no water or lava beside it, and a block for the roof (carried, or the
one it digs out). There it puts the campfire (carried, or made from logs and sticks) and
CAMP_TORCHES torches on the ground beside it, then digs out the block it stands on and drops into
the hole, walled on four sides, and puts a block over its head (any building block: the one it dug
out will do). Then it waits there for nightfall and sleeps (sleep takes over once it is dug in at
night; the brain remembers the hole as a sheltered spot). With nowhere to dig in, camp is not on
offer and Mimo sleeps where it stands. The camp is remembered as an outpost (a memory place,
kind "outpost", note "camp"; a notable "camp" event) when its roof goes on (`observe_camp`, from
brain.observe_step). In the morning the first batch of any purpose takes the roof off first
(`leave_camp`, from brain.brain_plan), and Mimo climbs out.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.services.blocks import is_solid
from backend.services.crafting import BLOCKS, can_harvest
from backend.survival.blueprints import BUILDING
from backend.survival.cooking import made
from backend.survival.expedition import away, camp_time, from_home, trek
from backend.survival.goals import URGES
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, remember
from backend.survival.once import log_once
from backend.survival.purposes import Purpose, register, walk_to, wait_for_nightfall
from backend.survival.situation import Situation
from backend.survival.steps import as_cell
from backend.survival.structures import reserved
from backend.survival.triggers import ensure_brain

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

OUTPOST_REUSE = 24.0
CAMP_SEARCH = 6
CAMP_TORCHES = 2
SIDES = ((1, 0), (0, 1), (-1, 0), (0, -1))


def roof_block(s: Situation) -> str | None:
    """A building block Mimo carries for the roof."""
    return next((block for block in BUILDING if s.count(block) > 0), None)


def in_camp(s: Situation) -> bool:
    """Mimo stands in a camp dug in with its roof on: walled on four sides, a block over its head."""
    x, y, z = s.here
    return (is_solid(s.grid.material(x, y + 1, z)) and is_solid(s.grid.material(x, y - 1, z))
            and all(is_solid(s.grid.material(x + dx, y, z + dz)) for dx, dz in SIDES))


def in_pit(s: Situation, cell: Cell) -> bool:
    """Mimo stands in the hole at `cell` (dug, its roof still off)."""
    return s.here == tuple(cell)


def camp_spot(s: Situation, cell: Cell) -> bool:
    """Mimo can dig in standing at `cell`: on natural ground it can dig, with solid ground under it
    and on all four sides of the hole, nothing it built or tends, no water or lava beside it, and a
    block for the roof (one it carries, or the one it digs out)."""
    x, y, z = cell
    ground = (x, y - 1, z)
    material = s.grid.material(*ground)
    if not s.grid.standable(cell) or reserved(s.grid, ground) or not can_harvest(material, s.inventory):
        return False
    if roof_block(s) is None and BLOCKS.get(material, {}).get("drop") not in BUILDING:
        return False
    if not is_solid(material) or material in ("water", "lava") or not is_solid(s.grid.material(x, y - 2, z)):
        return False
    return all(is_solid(s.grid.material(x + dx, y - 1, z + dz))
               and s.grid.material(x + dx, y, z + dz) not in ("water", "lava") for dx, dz in SIDES)


def outpost_near(s: Situation) -> Cell | None:
    """An outpost within OUTPOST_REUSE blocks whose hole is still open and empty."""
    for place in sorted((place for place in s.places if place["kind"] == "outpost"),
                        key=lambda place: s.distance(cell_of(place))):
        cell = cell_of(place)
        if s.distance(cell) > OUTPOST_REUSE:
            break
        x, y, z = cell
        if s.grid.passable(cell) and s.grid.passable((x, y + 1, z)) and is_solid(s.grid.material(x, y - 1, z)):
            return cell
    return None


def new_camp(s: Situation) -> Cell | None:
    """The nearest spot within CAMP_SEARCH blocks (and a block or two up or down) to dig in at."""
    x, y, z = s.here
    spots = []
    for dx in range(-CAMP_SEARCH, CAMP_SEARCH + 1):
        for dz in range(-CAMP_SEARCH, CAMP_SEARCH + 1):
            column = [(x + dx, y + dy, z + dz) for dy in (0, 1, -1, 2, -2)]
            cell = next((cell for cell in column if s.grid.standable(cell)), None)
            if cell is not None and camp_spot(s, cell):
                spots.append(cell)
    return min(spots, key=lambda cell: (s.distance(cell), cell)) if spots else None


def ground_spots(s: Situation, cell: Cell) -> list[Cell]:
    """Cells beside the camp on the ground, where the campfire and torches go: nearest first."""
    x, y, z = cell
    found = [(x + dx, y, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))]
    return [spot for spot in found if s.grid.standable(spot) and not reserved(s.grid, spot)]


def settled(s: Situation) -> bool:
    """Dug in for the night: in the camp with its roof on, or in its hole with no block for a roof."""
    camp = (trek(s) or {}).get("camp")
    return in_camp(s) or (camp is not None and in_pit(s, camp) and roof_block(s) is None)


def somewhere(s: Situation) -> bool:
    """Mimo has somewhere to camp: its hole, an outpost near, or a spot to dig in."""
    camp = (trek(s) or {}).get("camp")
    return s.sensed("camp spot", lambda: (camp is not None and in_pit(s, camp)) or outpost_near(s) is not None
                    or new_camp(s) is not None)


def camp_valid(s: Situation) -> bool:
    """Far from home from late in the day on, with somewhere to camp; once dug in at night, sleep takes over."""
    return away(s) and camp_time(s) and not (s.night and settled(s)) and (settled(s) or somewhere(s))


def camp_score(s: Situation) -> float:
    return 95.0 if s.night or s.phase == "dusk" else 85.0


def plan_camp(s: Situation, context: ActionContext) -> list[dict]:
    """Dig in: to the camp, fire and torches beside it, the hole (Mimo drops in); then the roof;
    then wait for nightfall."""
    found = trek(s)
    if found is None:
        return []
    if settled(s):
        return [] if s.night else [wait_for_nightfall(s)]
    camp = found.get("camp")
    if camp is not None and in_pit(s, camp):
        block = roof_block(s)
        x, y, z = camp
        return [{"kind": "place", "target": [x, y + 1, z], "block": block}] if block else []
    reuse = outpost_near(s)
    if reuse is not None:
        found["camp"] = list(reuse)
        x, y, z = reuse
        return [{**walk_to((x, y + 1, z), 1.0), "whole": True}, walk_to(reuse)]
    spot = new_camp(s)
    if spot is None:
        return []
    x, y, z = spot
    found["camp"] = [x, y - 1, z]
    steps = [] if s.here == spot else [{**walk_to(spot), "whole": True}]
    inventory = dict(s.inventory)
    lights = ground_spots(s, spot)
    if inventory.get("campfire", 0) < 1:
        steps += made(inventory, "campfire") or []
    if lights and inventory.get("campfire", 0) > 0:
        steps.append({"kind": "place", "target": list(lights.pop(0)), "block": "campfire"})
    for cell in lights[:min(CAMP_TORCHES, inventory.get("torch", 0))]:
        steps.append({"kind": "place", "target": list(cell), "block": "torch"})
    return [*steps, {"kind": "mine", "target": [x, y - 1, z]}]


URGES["camp"] = lambda s: True  # making camp at dusk far from home is a need, like going home


register(Purpose(
    "camp", "make camp", "Far from home at dusk: dig in for the night by a campfire, with torches around.",
    valid=camp_valid, facts=lambda s: f"{round(from_home(s))} blocks from home; {s.phase}",
    score=camp_score, plan=plan_camp,
    thoughts=("Too far to go home tonight. I'll dig in here.", "A little camp, a little fire. Cosy.")))


def leave_camp(s: Situation, steps: list[dict]) -> list[dict]:
    """Once it is not time to camp, the first batch planned inside a dug-in camp (any purpose but
    camp and sleep) takes the roof off first, so Mimo can climb out."""
    if not steps or s.brain.get("purpose") in ("camp", "sleep") or camp_time(s) or not in_camp(s):
        return steps
    x, y, z = s.here
    if not any(place["kind"] == "outpost" and cell_of(place) == s.here for place in s.places):
        return steps
    return [{"kind": "mine", "target": [x, y + 1, z]}, *steps]


def observe_camp(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """The camp's roof went on (brain.observe_step): the camp is remembered as an outpost."""
    if step["kind"] != "place" or step.get("purpose") != "camp" or context.db is None:
        return
    try:
        found = ensure_brain(state).get("expedition") or {}
        camp = found.get("camp")
        if camp is None or as_cell(step["target"]) != (camp[0], camp[1] + 1, camp[2]):
            return
        if remember(context.db, "outpost", tuple(camp), at, "camp"):
            context.events.append((at, "camp", f"{state['name']} dug in for the night and made a camp."))
    except Exception as error:
        log_once(logger, "camp", error)
