"""Making (T1): the raw materials Mimo gathers for what it makes, and how it makes it.

The owner, 2026-09-25: "continue making the world more complex through more block types or objects to
create". Several projects want things made and put in place: the workshop (backend.survival.workshop),
the touches that make home cozy (backend.survival.cozy) and, from T2, the machines
(backend.survival.machines). Each registers in NEEDS a function of the Situation giving the blocks
and items its next steps still want ({"kiln": 1, "glass_pane": 2}); `needs` adds them up once per
Situation.

`raw_needs` works out through the recipes (toolmaking.make) the raw materials those take that Mimo
does not carry: the ones it gathers itself (GATHERED: sugar cane and flowers, clay and sand) and the
ores mine_ore brings (MINED: copper ore). What else a project wants (leather for a book, wool, tallow,
string) waits for a hunt or the chest; a thing it cannot make yet is left for later.

- gather_materials, "gather materials": picks or digs what raw_needs asks for from sources within
  SOURCE_SIGHT blocks, nearest first: plants worldgen grew that still stand (sugar cane from the top
  of its stalk down) and clay or sand on the ground with open air over it, never under water, never
  what Mimo built or tends, never near a failed step. Up to PER_BATCH a batch and GATHER_BATCHES
  batches a choice. Day work in the work band: 45 plus a tenth of diligence, minus late.
- mine_ore goes after copper ore while raw_needs asks for it (work.MORE_ORES), and gather_stone digs for
  the cobblestone it asks for (QUARRIED), a stack at most beyond its own goal (work.MORE_STONE: more
  would only go in the chest, where making cannot use it).
- The chest does not take what a project needs (storage.KEEPS_MORE): the items NEEDS names and every
  ingredient of their recipes stay on Mimo, so the clay it dug is still there when the kiln is made.

`craft_plan(s, items)` is the craft and smelt steps that make `items` from what Mimo carries, with
the stations the recipes need (a crafting table; a furnace, or a kiln for clay and sand): used as
they stand when one is placed within STATION_REACH, else carried or made, put down beside Mimo and
mined back after (`keep`), as craft_tools does. None when something is missing or would not fit.
`place_steps(s, stands, jobs)` walks to the stand nearest where Mimo will be that reaches each job's
cell, when it is out of reach, and does the job.

Mimo's favourite colour (orange, pink or yellow) is a trait of the life, fixed by its world seed and
its name (`favourite_colour`): the rug it makes for home is of that colour (backend.survival.cozy).
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from backend.services.crafting import COOKING, KILN_FIRED, RECIPES, craft, smelt, take_items
from backend.services.worldgen import hash32, surface_material, terrain_height
from backend.survival import storage, work
from backend.survival.carrying import STACK, crafts_fit
from backend.survival.foraging import reach_steps, whole_walk
from backend.survival.grid import Cell
from backend.survival.once import log_once
from backend.survival.purposes import Purpose, late_penalty, register
from backend.survival.senses import natural_plants, near_failure
from backend.survival.situation import Situation
from backend.survival.steps import REACH, STATION_REACH, WORKSTATIONS
from backend.survival.structures import reserved
from backend.survival.toolmaking import SMELTED, Short, make, place_station, station_spots

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

PLANTS = ("sugar_cane", "flower_orange", "flower_pink", "flower_yellow")
GROUND = ("clay", "sand")
GATHERED = PLANTS + GROUND
MINED = ("copper_ore",)
SOURCE_SIGHT = 24
PER_BATCH = 8
GATHER_BATCHES = 3
RAW_TRIES = 64  # units of raw material one wanted item may add before raw_needs stops counting
COLOURS = ("orange", "pink", "yellow")
COLOUR_CHANNEL = 95
QUARRIED = ("cobblestone",)  # what gather_stone digs

# Functions of the Situation giving {item: count}: blocks and items a project still wants made and put
# in place (the workshop's, the cozy home's, the machines').
NEEDS: list = []


def favourite_colour(state: dict) -> str:
    """Orange, pink or yellow: a trait of the life, fixed by its world seed and its name."""
    salt = sum(map(ord, state.get("name", "")))
    return COLOURS[hash32(salt, 0, 0, state.get("world_seed", "0"), COLOUR_CHANNEL) % len(COLOURS)]


def needs(s: Situation) -> dict[str, int]:
    """What every project still wants made and put in place, added up (one that crashes wants nothing,
    logged once), read once per Situation."""
    def look() -> dict[str, int]:
        total: dict[str, int] = {}
        for wants in NEEDS:
            try:
                for item, count in wants(s).items():
                    if count > 0:
                        total[item] = total.get(item, 0) + int(count)
            except Exception as error:
                log_once(logger, "making needs", error)
        return total
    return s.sensed("making needs", look)


def raw_needs(s: Situation) -> dict[str, int]:
    """The raw materials (GATHERED and MINED) the recipes for `needs` take that Mimo does not carry,
    each wanted item worked out in turn on what the ones before it left (read once per Situation)."""
    def look() -> dict[str, int]:
        trial: dict[str, int] = dict(s.inventory)
        raw: dict[str, int] = {}
        for item, count in sorted(needs(s).items()):
            for _ in range(RAW_TRIES):
                attempt = dict(trial)
                try:
                    make(attempt, item, count, [])
                except Short as short:
                    missing = str(short.args[0]) if short.args else ""
                    if missing in GATHERED or missing in MINED or missing in QUARRIED:
                        raw[missing] = raw.get(missing, 0) + 1
                        trial[missing] = trial.get(missing, 0) + 1
                        continue
                    break  # it waits for something no gathering brings
                attempt[item] = attempt.get(item, 0) - count  # spoken for
                trial = attempt
                break
        return raw
    return s.sensed("making raw needs", look)


def ingredients(items) -> set[str]:
    """Every item the recipes and smelting for `items` use, however deep, and the items themselves."""
    seen: set[str] = set()
    todo = list(items)
    while todo:
        item = todo.pop()
        if item in seen:
            continue
        seen.add(item)
        recipe = RECIPES.get(item)
        if recipe is not None:
            todo += list(recipe["ingredients"])
        if item in SMELTED:
            todo.append(SMELTED[item])
    return seen


def kept_for_making(s: Situation, item: str) -> float:
    """storage.KEEPS_MORE: a stack more of anything a project wants or makes what it wants from."""
    wanted = needs(s)
    if not wanted:
        return 0.0
    chain = s.sensed("making chain", lambda: ingredients(wanted))
    return float(STACK) if item in chain else 0.0


def ores_for_making(s: Situation) -> list[str]:
    """work.MORE_ORES: the ores raw_needs asks for."""
    return [ore for ore in MINED if raw_needs(s).get(ore, 0) > 0]


storage.KEEPS_MORE.append(kept_for_making)
work.MORE_ORES.append(ores_for_making)


# Making things -----------------------------------------------------------------------------------

def stations_for(steps: list[dict], near: set[str], inventory: dict[str, int]) -> list[str]:
    """The stations `steps` need that are not placed within reach (`near`): the crafting table first,
    since it makes the others (and is wanted for that when a furnace or kiln has to be made)."""
    wanted: list[str] = []
    for step in steps:
        if step["kind"] == "craft":
            station = RECIPES[step["recipe"]].get("station")
        elif step["kind"] == "smelt" and step["item"] not in COOKING:
            station = "kiln" if step["item"] in KILN_FIRED and "kiln" in near else "furnace"
        else:
            station = None
        if station is not None and station not in near and station not in wanted:
            wanted.append(station)
    making_one = any(inventory.get(station, 0) < 1 for station in wanted)
    if making_one and "crafting_table" not in near and "crafting_table" not in wanted:
        wanted.append("crafting_table")
    return sorted(wanted, key=lambda station: station != "crafting_table")


def craft_plan(s: Situation, items: dict[str, int]) -> list[dict] | None:
    """The steps that make `items` (as many of each as asked, what Mimo carries counting) with the
    stations they need; [] when Mimo carries them all already; None when they cannot all be made now
    or something made would not fit in Mimo's arms."""
    def made(inventory: dict[str, int], steps: list[dict]) -> None:
        for item, count in sorted(items.items()):
            make(inventory, item, count, steps)
            inventory[item] = inventory.get(item, 0) - count  # spoken for

    try:
        dry: list[dict] = []
        made(dict(s.inventory), dry)
        if not dry:
            return []
        x, _, z = s.here
        near = s.grid.placed_near(x, z, STATION_REACH, WORKSTATIONS)
        inventory, steps, placed, spots = dict(s.inventory), [], [], station_spots(s)
        for station in stations_for(dry, near, inventory):
            if inventory.get(station, 0) < 1:
                make(inventory, station, 1, steps)
            cell = place_station(spots, station, steps)
            if cell is None:
                raise Short(station)
            inventory[station] -= 1
            placed.append(cell)
        made(inventory, steps)
    except Short:
        return None
    steps.extend({"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(placed))
    return steps if crafts_fit(s.inventory, steps) else None


def after_steps(inventory: dict[str, int], steps: list[dict]) -> dict[str, int]:
    """What Mimo will carry once `steps` (craft_plan's: crafts, smelts, stations put down and mined
    back) have run."""
    after = dict(inventory)
    for step in steps:
        if step["kind"] == "craft":
            after = craft(after, step["recipe"], {"crafting_table"})
        elif step["kind"] == "smelt":
            after = smelt(after, step["item"], {"furnace", "campfire"})
        elif step["kind"] == "place":
            after = take_items(after, {step["block"]: 1})
        elif step["kind"] == "mine" and step.get("keep"):
            placed = next(entry["block"] for entry in steps if entry["kind"] == "place"
                          and entry["target"] == step["target"])
            after[placed] = after.get(placed, 0) + 1
    return after


def place_steps(s: Situation, stands, jobs: list[tuple[Cell, list[dict]]], at: Cell | None = None) -> list[dict]:
    """Each (cell, steps) job in turn, walking first to the stand nearest where Mimo will be (`at`,
    where it stands unless given) that reaches the cell, whenever the cell is out of reach from there
    or is where Mimo stands. A job no stand reaches is left out."""
    steps: list[dict] = []
    at = at or s.here
    for cell, work_steps in jobs:
        if math.dist(at, cell) > REACH or tuple(at) == tuple(cell):
            reaching = [stand for stand in stands if math.dist(stand, cell) <= REACH and tuple(stand) != tuple(cell)]
            if not reaching:
                continue
            at = min(reaching, key=lambda stand: (math.dist(stand, at), tuple(stand)))
            steps.append(whole_walk(at))
        steps.extend(work_steps)
    return steps


# gather_materials --------------------------------------------------------------------------------

def gathered_wanted(s: Situation) -> dict[str, int]:
    return {item: count for item, count in raw_needs(s).items() if item in GATHERED}


def diggable(s: Situation, cell: Cell, kind: str) -> bool:
    """Still there, with open air over ground (not water), nobody's that Mimo built or tends, and no
    failed step nearby."""
    x, y, z = cell
    if s.grid.material(*cell) != kind or reserved(s.grid, cell) or near_failure(s.state, cell):
        return False
    return kind in PLANTS or (s.grid.passable((x, y + 1, z)) and s.grid.material(x, y + 1, z) != "water")


def sources(s: Situation) -> list[tuple[Cell, str]]:
    """(cell, material) Mimo can gather for raw_needs within SOURCE_SIGHT blocks, nearest first, a
    stalk of sugar cane from its top down."""
    def look() -> list[tuple[Cell, str]]:
        wanted = gathered_wanted(s)
        x, _, z = s.here
        found: list[tuple[Cell, str]] = []
        plants = tuple(kind for kind in PLANTS if kind in wanted)
        if plants:
            for root in natural_plants(s.seed, x, z, SOURCE_SIGHT, plants):
                kind = s.grid.material(*root)
                top = root[1]
                while kind in plants and s.grid.material(root[0], top + 1, root[2]) == kind:
                    top += 1
                found += [((root[0], y, root[2]), kind) for y in range(root[1], top + 1)]
        ground = tuple(kind for kind in GROUND if kind in wanted)
        if ground:
            for gx in range(x - SOURCE_SIGHT, x + SOURCE_SIGHT + 1):
                for gz in range(z - SOURCE_SIGHT, z + SOURCE_SIGHT + 1):
                    if math.hypot(gx - x, gz - z) > SOURCE_SIGHT:
                        continue
                    kind = surface_material(gx, gz, s.seed)
                    if kind in ground:  # a lake bed's is under water: diggable leaves it
                        found.append(((gx, terrain_height(gx, gz, s.seed), gz), kind))
        found = [(cell, kind) for cell, kind in found if diggable(s, cell, kind)]
        return sorted(found, key=lambda entry: (math.hypot(entry[0][0] - x, entry[0][2] - z), -entry[0][1], entry[0]))
    return s.sensed("making sources", look)


def gather_valid(s: Situation) -> bool:
    return not s.night and bool(sources(s))


def gather_facts(s: Situation) -> str:
    wanted = ", ".join(f"{count} {item.replace('_', ' ')}" for item, count in sorted(gathered_wanted(s).items()))
    return f"wants {wanted} for what it makes; {len(sources(s))} to gather within {SOURCE_SIGHT} blocks"


def plan_gather(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= GATHER_BATCHES:
        return []
    wanted, jobs = dict(gathered_wanted(s)), []
    for cell, kind in sources(s):
        if wanted.get(kind, 0) > 0 and len(jobs) < PER_BATCH:
            wanted[kind] -= 1
            jobs.append((cell, [{"kind": "mine", "target": list(cell)}]))
    return reach_steps(s, jobs)


register(Purpose(
    "gather_materials", "gather materials",
    "Pick sugar cane and flowers, or dig clay and sand, for something it is making.",
    valid=gather_valid, facts=gather_facts,
    score=lambda s: max(0.0, 45.0 + s.trait("diligence") / 10 - late_penalty(s)), plan=plan_gather,
    thoughts=("I need a few more things for what I'm making.", "Clay by the water, sand, sugar cane...")))


def stone_for_making(s: Situation) -> float:
    """work.MORE_STONE: the cobblestone raw_needs asks for, a stack at most."""
    return float(min(STACK, raw_needs(s).get("cobblestone", 0)))


work.MORE_STONE.append(stone_for_making)
