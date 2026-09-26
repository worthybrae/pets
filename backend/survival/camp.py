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

L4b final fix wave, I1: with its arms full and no building block carried, the block it dug out was
left behind (carrying's overflow rule), and it slept in an open hole, worse than open ground (one
pet lost 65 health to a gloomling on the rim in a night). The block it digs out counts as the roof
only when it fits in Mimo's arms (`roof_fits`); otherwise the plan first drops a stack of what gives
way to food (`spare_stack`: carrying.GIVES_WAY_TO_FOOD, never a material gear still wants nor an ore
the pickaxe ladder counts), and with nothing to drop there is no spot, so Mimo sleeps on the surface,
where it can flee or fight as ever. An outpost is gone back to only with a roof block in hand.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.services.blocks import is_replaceable, is_solid
from backend.services.crafting import BLOCKS, can_harvest
from backend.survival.blueprints import BUILDING
from backend.survival.carrying import CARRY_STACKS, GIVES_WAY_TO_FOOD, STACK, room_for
from backend.survival.cooking import made
from backend.survival.creatures.hostiles import enclosed
from backend.survival.creatures.gear import materials_wanted
from backend.survival.expedition import away, camp_time, from_home, trek
from backend.survival.goals import URGES
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, remember
from backend.survival.once import log_once
from backend.survival.purposes import Purpose, register, walk_to, wait_for_nightfall
from backend.survival.senses import near_failure
from backend.survival.situation import Situation
from backend.survival.steps import as_cell
from backend.survival.structures import reserved
from backend.survival.triggers import ensure_brain
from backend.survival.work import ladder_ores

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

OUTPOST_REUSE = 24.0
CAMP_SEARCH = 6
CAMP_TORCHES = 2
SIDES = ((1, 0), (0, 1), (-1, 0), (0, -1))
GROUND = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))


def roof_in(inventory: dict) -> str | None:
    """A building block in `inventory` for the roof."""
    return next((block for block in BUILDING if inventory.get(block, 0) > 0), None)


def roof_block(s: Situation) -> str | None:
    """A building block Mimo carries for the roof."""
    return roof_in(s.inventory)


def dug_block(material: str) -> str | None:
    """The building block digging `material` out gives Mimo (its roof when it carries none), or None."""
    drop = BLOCKS.get(material, {}).get("drop")
    return drop if drop in BUILDING else None


def spare_stack(inventory: dict) -> str | None:
    """A stack Mimo may leave behind to make room for its roof (I1): the first of
    carrying.GIVES_WAY_TO_FOOD it carries (it "all comes back with the next hunt or dig"), but never a
    material gear still wants (creatures.gear.materials_wanted) or an ore the pickaxe ladder counts
    (work.ladder_ores). None when there is nothing it may drop."""
    kept = materials_wanted(inventory) | ladder_ores(inventory)
    return next((item for item in GIVES_WAY_TO_FOOD if inventory.get(item, 0) > 0 and item not in kept), None)


def roof_fits(inventory: dict, block: str) -> bool:
    """The block it digs out fits in Mimo's arms (carrying.room_for), so it has its roof (I1)."""
    return room_for(inventory, block, CARRY_STACKS) >= 1


def in_camp(s: Situation) -> bool:
    """Mimo stands in a camp dug in with its roof on: walled on four sides, a block over its head
    and under its feet (creatures.hostiles.enclosed, which the alarm shares: the final fix wave's I3)."""
    return enclosed(s.grid, s.here)


def in_pit(s: Situation, cell: Cell) -> bool:
    """Mimo stands in the hole at `cell` (dug, its roof still off)."""
    return s.here == tuple(cell)


def roofed(inventory: dict, ground: str) -> bool:
    """With `inventory` in its arms, Mimo will have a roof over its hole: a building block it carries,
    or the one digging `ground` out gives, when that fits in its arms (`roof_fits`) or a stack may be
    dropped to make room for it (`spare_stack`; the final fix wave's I1)."""
    if roof_in(inventory) is not None:
        return True
    dug = dug_block(ground)
    return dug is not None and (roof_fits(inventory, dug) or spare_stack(inventory) is not None)


def camp_spot(s: Situation, cell: Cell) -> bool:
    """Mimo can dig in standing at `cell`: on natural ground it can dig, with solid ground under it
    and on all four sides of the hole, nothing it built or tends, no water or lava beside it, and a
    block for the roof (`roofed`: one it carries, or the one it digs out, when that fits in its arms
    or it can drop a stack for it, I1), judged on its arms once the campfire and torches are down
    (`lit_camp`, as plan_camp plans them; follow-up 2, F2)."""
    x, y, z = cell
    ground = (x, y - 1, z)
    material = s.grid.material(*ground)
    if not s.grid.standable(cell) or reserved(s.grid, ground) or not can_harvest(material, s.inventory):
        return False
    if not is_solid(material) or material in ("water", "lava") or not is_solid(s.grid.material(x, y - 2, z)):
        return False
    if not all(is_solid(s.grid.material(x + dx, y - 1, z + dz))
               and s.grid.material(x + dx, y, z + dz) not in ("water", "lava") for dx, dz in SIDES):
        return False
    return roofed(lit_camp(s, cell)[1], material)


def outpost_near(s: Situation) -> Cell | None:
    """An outpost within OUTPOST_REUSE blocks whose hole is still open and empty, its floor and its
    four walls still solid (Fix round 1, Critical 1c: a wall dug away since is not reused), and no
    step failed near it lately (Fix round 1, Critical 1b: senses.near_failure). The final fix wave,
    I1: only with a roof block in hand, since nothing is dug out there to roof it with."""
    if roof_block(s) is None:
        return None
    for place in sorted((place for place in s.places if place["kind"] == "outpost"),
                        key=lambda place: s.distance(cell_of(place))):
        cell = cell_of(place)
        if s.distance(cell) > OUTPOST_REUSE:
            break
        x, y, z = cell
        if (s.grid.passable(cell) and s.grid.passable((x, y + 1, z)) and is_solid(s.grid.material(x, y - 1, z))
                and all(is_solid(s.grid.material(x + dx, y, z + dz)) for dx, dz in SIDES)
                and not near_failure(s.state, cell)):
            return cell
    return None


def new_camp(s: Situation) -> Cell | None:
    """The nearest spot within CAMP_SEARCH blocks (and a block or two up or down) to dig in at, not
    one a step failed near lately (Fix round 1, Critical 1b: senses.near_failure), so a spot Mimo
    cannot reach or cannot use is not picked again at once."""
    x, y, z = s.here
    spots = []
    for dx in range(-CAMP_SEARCH, CAMP_SEARCH + 1):
        for dz in range(-CAMP_SEARCH, CAMP_SEARCH + 1):
            column = [(x + dx, y + dy, z + dz) for dy in (0, 1, -1, 2, -2)]
            cell = next((cell for cell in column if s.grid.standable(cell)), None)
            if cell is not None and camp_spot(s, cell) and not near_failure(s.state, cell):
                spots.append(cell)
    return min(spots, key=lambda cell: (s.distance(cell), cell)) if spots else None


def ground_spots(s: Situation, cell: Cell) -> list[Cell]:
    """Cells beside the camp on the ground that are free to build on (Fix round 1, Critical 1a: not
    a berry bush or a mushroom, and not a campfire or torch already there), nearest first."""
    x, y, z = cell
    found = [(x + dx, y, z + dz) for dx, dz in GROUND]
    return [spot for spot in found if s.grid.standable(spot) and is_replaceable(s.grid.material(*spot))
            and not reserved(s.grid, spot)]


def lit_near(s: Situation, cell: Cell, block: str) -> int:
    """How many `block` ("campfire" or "torch") already stand on the ground beside `cell` (Fix
    round 1, Critical 1a): reused, not placed again."""
    x, y, z = cell
    return sum(1 for dx, dz in GROUND if s.grid.material(x + dx, y, z + dz) == block)


def campfire_made(s: Situation) -> tuple[list[dict], dict]:
    """The craft steps for a campfire Mimo does not carry (cooking.made: from logs and sticks, as far
    as it fits in its arms; none when it carries one or cannot make one) and its arms after them,
    worked out once per Situation: the same for every spot new_camp weighs."""
    def look() -> tuple[list[dict], dict]:
        inventory = dict(s.inventory)
        steps = (made(inventory, "campfire") or []) if inventory.get("campfire", 0) < 1 else []
        return steps, inventory
    return s.sensed("camp campfire made", look)


def lit_camp(s: Situation, spot: Cell) -> tuple[list[dict], dict]:
    """The steps that make and put down the campfire and CAMP_TORCHES torches on the ground beside
    `spot`, and Mimo's arms once they are done. Fix round 1, Critical 1a: a campfire or torches
    already standing there (a batch cut short and planned again) are counted, not placed again.
    Follow-up 2 (F2): the one reckoning plan_camp plans by and camp_spot judges the roof's room by, so
    a campfire put down (or made from sticks and logs) frees the stack the roof needs for both."""
    steps: list[dict] = []
    inventory = dict(s.inventory)
    lights = ground_spots(s, spot)
    if lit_near(s, spot, "campfire") < 1:
        crafting, crafted = campfire_made(s)
        steps, inventory = list(crafting), dict(crafted)
        if lights and inventory.get("campfire", 0) > 0:
            steps.append({"kind": "place", "target": list(lights.pop(0)), "block": "campfire"})
            inventory["campfire"] -= 1
    torches_wanted = max(0, CAMP_TORCHES - lit_near(s, spot, "torch"))
    for cell in lights[:min(torches_wanted, inventory.get("torch", 0))]:
        steps.append({"kind": "place", "target": list(cell), "block": "torch"})
        inventory["torch"] -= 1
    return steps, inventory


def settled(s: Situation) -> bool:
    """Dug in for the night: in the camp with its roof on, in its hole with no block for a roof, or
    in its hole with the roof cell already solid (Fix round 1, Critical 1d: a reused outpost or a
    batch planned twice must not plan another roof step onto a cell already taken)."""
    camp = (trek(s) or {}).get("camp")
    in_hole = camp is not None and in_pit(s, camp)
    roofed = in_hole and is_solid(s.grid.material(camp[0], camp[1] + 1, camp[2]))
    return in_camp(s) or (in_hole and (roof_block(s) is None or roofed))


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
    then wait for nightfall. The fire and torches are `lit_camp`'s (fix round 1, Critical 1a: ones
    already standing beside the spot are counted, not placed a second time). The final fix wave,
    I1: with no roof block and no room for the block it digs out once the fire and torches are down,
    it drops a spare stack (`spare_stack`) just before it digs."""
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
    lights, inventory = lit_camp(s, spot)
    steps += lights
    dug = dug_block(s.grid.material(x, y - 1, z))
    if roof_in(inventory) is None and dug is not None and not roof_fits(inventory, dug):
        spare = spare_stack(inventory)  # I1: make room for the roof it digs out first
        if spare is not None:
            steps.append({"kind": "drop", "item": spare, "amount": inventory[spare] % STACK or STACK})
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
