"""Making (T1): the raw materials Mimo gathers for what it makes, and how it makes it.

The owner, 2026-09-25: "continue making the world more complex through more block types or objects to
create". Several projects want things made and put in place: the workshop (backend.survival.workshop),
the touches that make home cozy (backend.survival.cozy) and, from T2, the machines
(backend.survival.machines). Each registers in NEEDS a function of the Situation giving the blocks
and items its next steps still want ({"kiln": 1, "glass_pane": 2}); `needs` adds them up once per
Situation.

`raw_needs` works out through the recipes (toolmaking.make) the raw materials those take that Mimo
does not carry or keep in a chest: the ones it gathers itself (GATHERED: sugar cane and flowers, clay
and sand) and what mine_ore brings (MINED: copper ore, iron ore for the workshop's bars, and coal for
torches). What else a project wants (leather for a book, wool, tallow) waits for a hunt or the chest;
a thing it cannot make yet is left for later.

- gather_materials, "gather materials": picks or digs what raw_needs asks for from sources within
  SOURCE_SIGHT blocks, nearest first: plants worldgen grew that still stand (sugar cane from the top
  of its stalk down; a root already picked is no source) and clay or sand on the ground with open air
  over it, never under water, never what Mimo built or tends, never near a failed step. Up to PER_BATCH
  a batch and GATHER_BATCHES batches a choice. Day work in the work band: 45 plus a tenth of diligence,
  minus late. The Making final fix wave (C1): most homes have no shore in sight, so when nothing Mimo
  wants lies within SOURCE_SIGHT it looks farther: every column of the natural surface out to FAR_SIGHT
  blocks from home for clay and sand, and the plants worldgen grew out to FAR_PLANTS (`far_scan`: the
  FAR_KEPT nearest of each kind still there, remembered in state["brain"] and looked over again on a new
  game day once none of them is left). Clay is rare: 3 to 12 columns lie within 96 blocks of the gate's six
  homes, 15 to 34 within 160. A batch then walks to the nearest one (in segments, beyond one whole walk)
  and digs it, and the next batch finds the rest of that shore in sight.
- mine_ore goes after copper and iron ore while raw_needs asks for it (work.MORE_ORES), and gather_stone
  digs for the cobblestone it asks for (QUARRIED), a stack at most beyond its own goal (work.MORE_STONE:
  more would only go in the chest).
- The chest does not take what a project needs (storage.KEEPS_MORE, `kept_for_making`): as many of each
  item as the needs' recipes take (`allot`: from what Mimo carries first, then what its chests hold, the
  rest made from ingredients), never a whole stack more, and wood and stone only with full arms (L4a keeps
  them by its own rules otherwise). What they take from a chest, wood and stone too, build_storage takes back
  out (storage.TAKES_MORE, `from_chests`).
  Clay is rare, so the clay Mimo dug and the bricks fired from it are also kept for a project it is not
  working on now (LATER: the workshop's kiln until it is in, the cozy home's touches; `saved`), and no wall
  is raised with them (building.SPARED). What making made and no project needs now (a glass pane recipe
  makes 16, iron bars 16) goes in the chest (MADE, storage.KEEP) and comes back out when one does.
  Making wave 2: while a making goal is Mimo's goal and its arms are getting full (ROOM_FROM stacks), what
  L4a keeps on hand for its other goals (ROOM_KEPT: seeds, saplings, wheat, iron, gold, hides...) goes in
  the chest too unless the needs take it (`making_room`), so the goal's copper and torch chain fit.

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
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.services.crafting import COOKING, KILN_FIRED, LOGS, PLANKS, RECIPES, craft, smelt, take_items
from backend.services.worldgen import SEA_LEVEL, hash32, surface_material, swamp_pool, terrain_height
from backend.survival import building, storage, work
from backend.survival.carrying import CARRY_STACKS, STACK, crafts_fit, full, room_for, stacks
from backend.survival.foraging import STAND, reach_steps, whole_walk
from backend.survival.goals import ADVANCES, active
from backend.survival.grid import Cell
from backend.survival.home import home_cell
from backend.survival.once import log_once
from backend.survival.pathing import MAX_RANGE
from backend.survival.purposes import Purpose, late_penalty, register, walk_to
from backend.survival.senses import natural_plants, near_failure
from backend.survival.situation import Situation
from backend.survival.steps import REACH, STATION_REACH, WORKSTATIONS
from backend.survival.structures import reserved
from backend.survival.toolmaking import MAX_DEPTH, SMELTED, Short, make, place_station, station_spots

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

PLANTS = ("sugar_cane", "flower_orange", "flower_pink", "flower_yellow")
GROUND = ("clay", "sand")
GATHERED = PLANTS + GROUND
# What mine_ore brings -> the ore it goes after (the Making final fix wave, C1: iron for the workshop's bars).
MINED = {"copper_ore": "copper_ore", "coal": "coal_ore", "iron_ore": "iron_ore"}
SOURCE_SIGHT = 24
FAR_SIGHT = 160  # C1: blocks from home the natural surface is looked over for clay and sand not in sight
FAR_PLANTS = 96  # and for plants worldgen grew (their chunks cost more to read)
FAR_KEPT = 48  # the nearest cells of each kind still there that are remembered
FAR = "making_far"  # state["brain"]'s key for them
WOOD_AND_STONE = LOGS + PLANKS + ("sticks", "cobblestone")  # I1: kept and gathered by L4a's own rules
PER_BATCH = 8
GATHER_BATCHES = 3
RAW_TRIES = 64  # units of raw material one wanted item may add before raw_needs stops counting
COLOURS = ("orange", "pink", "yellow")
COLOUR_CHANNEL = 95
QUARRIED = ("cobblestone",)  # what gather_stone digs

# Functions of the Situation giving {item: count}: blocks and items a project still wants made and put
# in place (the workshop's, the cozy home's, the machines').
NEEDS: list = []
# The Making final fix wave: functions of the Situation giving {item: count} a project that is not done
# will want once Mimo works on it again (the workshop's kiln, the cozy home's touches), so the SAVED things
# Mimo gathered for it are kept meanwhile (`saved`).
LATER: list = []
SAVED = ("clay", "brick")  # the rare clay Mimo dug, and the bricks fired from it
# The things making makes: what is left over (a glass pane recipe makes 16, iron bars 16, stairs 4) goes in
# the chest like any other spare material (storage.KEEP), and comes back out when a project needs it.
MADE = ("paper", "book", "dye_orange", "dye_pink", "dye_yellow", "wool_orange", "wool_pink", "wool_yellow",
        "rug_orange", "rug_pink", "rug_yellow", "bookshelf", "kiln", "stairs", "slab", "glass_pane", "trapdoor",
        "iron_bars", "flower_pot", "sign", "barrel", "composter", "candle", "tallow", "copper_wire", "lever",
        "button", "pressure_plate", "daylight_sensor", "repeater", "inverter", "joiner", "lamp", "bell")
# Making wave 2: the making goals (backend.survival.workshop, cozy, machines and computer register them), and
# what L4a keeps on hand for its own goals that one of them puts in the chest to make room, when it does not
# need it (`making_room`). Never food, tools, fuel (coal, wood), stone or torches: every project burns or
# builds with them, and L4a gathers them by its own rules.
MAKING_GOALS = ("workshop", "cozy_home", "first_circuits", "thinking_machine")
ROOM_KEPT = ("seeds", "sapling", "wheat", "iron_ore", "iron_ingot", "gold_ore", "gold_ingot", "leather", "feather",
             "rabbit_hide", "string", "flint", "stone_bricks")
ROOM_FROM = storage.STORE_FROM  # stacks carried from which a making goal makes room


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


def in_chests(s: Situation) -> dict[str, int]:
    """What the chests Mimo built and can get to hold, added up (storage.reachable_chests; read once per
    Situation)."""
    def look() -> dict[str, int]:
        total: dict[str, int] = {}
        for cell, _ in storage.reachable_chests(s):
            for item, count in storage.chest_contents(s, cell).items():
                total[item] = total.get(item, 0) + count
        return total
    return s.sensed("making chests", look)


def raw_needs(s: Situation) -> dict[str, int]:
    """The raw materials (GATHERED and MINED) the recipes for `needs` take that Mimo does not carry,
    each wanted item worked out in turn on what the ones before it left (read once per Situation). What
    its chests hold counts as had (the Making final fix wave, I1: build_storage takes it back out)."""
    def look() -> dict[str, int]:
        trial: dict[str, int] = dict(s.inventory)
        if needs(s):
            for item, count in in_chests(s).items():
                trial[item] = trial.get(item, 0) + count
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


def allot(wanted: dict[str, int], carried: dict[str, int],
          pool: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    """(used, taken): how many of each item making `wanted` takes from what Mimo carries and from its
    chests (`pool`), worked down the recipes (the Making final fix wave, I1). Each item comes from what
    Mimo carries first, then from the chests; what is still short is made from its ingredients (a craft
    rounded up to its whole output) or smelted from its ore. Wood and stone (WOOD_AND_STONE) are taken
    as they are but never made here (L4a gathers them by its own rules); fuel is not counted."""
    carried, pool = dict(carried), dict(pool)
    used: dict[str, int] = {}
    taken: dict[str, int] = {}

    def need(item: str, count: int, depth: int) -> None:
        if count <= 0 or depth > MAX_DEPTH:
            return
        for source, record in ((carried, used), (pool, taken)):
            got = min(count, source.get(item, 0))
            if got > 0:
                source[item] -= got
                record[item] = record.get(item, 0) + got
                count -= got
        if count <= 0 or item in WOOD_AND_STONE:  # wood and stone: L4a gathers them by its own rules
            return
        recipe = RECIPES.get(item)
        if recipe is not None and recipe["output"].get(item):
            crafts = math.ceil(count / recipe["output"][item])
            for name, each in sorted(recipe["ingredients"].items()):
                need(name, crafts * each, depth + 1)
        elif item in SMELTED:
            need(SMELTED[item], count, depth + 1)

    for item, count in sorted(wanted.items()):
        need(item, count, 0)
    return used, taken


def allotted(s: Situation) -> tuple[dict[str, int], dict[str, int]]:
    """`allot` for what every project needs now (read once per Situation)."""
    def look() -> tuple[dict[str, int], dict[str, int]]:
        wanted = needs(s)
        return allot(wanted, s.inventory, in_chests(s)) if wanted else ({}, {})
    return s.sensed("making allotted", look)


def later(s: Situation) -> dict[str, int]:
    """What LATER's projects will want once Mimo works on them again, added up (one that crashes wants
    nothing, logged once; read once per Situation)."""
    def look() -> dict[str, int]:
        total: dict[str, int] = {}
        for wants in LATER:
            try:
                for item, count in wants(s).items():
                    if count > 0:
                        total[item] = total.get(item, 0) + int(count)
            except Exception as error:
                log_once(logger, "making later", error)
        return total
    return s.sensed("making later", look)


def saved(s: Situation) -> dict[str, int]:
    """Of the SAVED things Mimo carries, as many as LATER's projects will take (read once per Situation)."""
    def look() -> dict[str, int]:
        wanted = later(s)
        used = allot(wanted, s.inventory, {})[0] if wanted else {}
        return {item: count for item, count in used.items() if item in SAVED}
    return s.sensed("making saved", look)


def making_room(s: Situation) -> bool:
    """Making wave 2: a making goal is Mimo's goal and its arms are getting full (ROOM_FROM stacks, where
    build_storage's trip home is worth it), so what L4a keeps on hand for other goals (ROOM_KEPT) and this
    one does not need goes in the chest to make room for its materials (read once per Situation)."""
    def look() -> bool:
        goal = active(s)
        return goal is not None and goal.name in MAKING_GOALS and stacks(s.inventory) >= ROOM_FROM
    return s.sensed("making room", look)


def kept_for_making(s: Situation, item: str) -> float:
    """storage.KEEPS_MORE: as many of an item as what the projects need takes of it (carried, or to be
    taken out of a chest), and no more (the Making final fix wave, I1: it was a whole stack more of every
    item anywhere in the chain, which filled Mimo's arms); and of the clay Mimo dug and the bricks fired
    from it, what a project it is not working on now will take (`saved`: on the gate's first run every
    clay within 96 blocks of home was dug, then built into walls or dropped as a loose block while
    another goal was Mimo's, and no kiln was ever made). Wood and stone only with full arms: otherwise
    L4a's own keep (16 cobblestone, 16 planks, 8 logs, 8 sticks) already holds what the needs take, but full
    arms put every building block in the chest, and a lever's one cobblestone went in and out for good.
    Making wave 2: none of what L4a keeps for other goals (ROOM_KEPT: seeds, saplings, iron, hides...) that
    the needs do not take, while a making goal is Mimo's goal and its arms are getting full (`making_room`:
    on the gate's route runs 16 stacks of them and food left the lamp's torch chain no room, and copper
    none at all)."""
    if item in ROOM_KEPT and making_room(s) and item not in ingredients(needs(s)):
        return -float(storage.KEEP.get(item, 0))
    if item in WOOD_AND_STONE and not full(s.inventory):
        return 0.0
    used, taken = allotted(s)
    return float(max(used.get(item, 0) + taken.get(item, 0), saved(s).get(item, 0)))


def from_chests(s: Situation) -> dict[str, int]:
    """storage.TAKES_MORE: what the projects need that Mimo's chests hold (the Making final fix wave, I1:
    only food and seeds ever came back out, so what went in stayed there while Mimo went for more)."""
    return dict(allotted(s)[1])


def storage_advances(s: Situation, goal) -> bool:
    """goals.ADVANCES (Making wave 2): build_storage, which each making goal's milestones name, works toward
    it only while it would make room for its materials (`making_room`) or take out of a chest what its
    needs take (`from_chests`). On the gate's route runs Hazel's chest held 5 copper ore while "First
    circuits" was its goal 14 times: nothing that took it out counted toward the goal, so the goal was set
    aside for "nothing to do for it now" within half a game day each time."""
    if goal.name not in MAKING_GOALS:
        return False
    wanted = from_chests(s)
    return making_room(s) or any(item in wanted for _, item, _ in storage.to_take(s))


def ores_for_making(s: Situation) -> list[str]:
    """work.MORE_ORES: the ores raw_needs asks for that Mimo has room to carry (the final fix wave: a find with
    full arms is left behind, carrying.settle)."""
    return [ore for item, ore in MINED.items()
            if raw_needs(s).get(item, 0) > 0 and room_for(s.inventory, item, CARRY_STACKS) > 0]


def spared_for_making(s: Situation) -> dict[str, int]:
    """building.SPARED: walls never take the clay and bricks making keeps (SAVED)."""
    return {item: round(kept_for_making(s, item)) for item in SAVED}


def spare_parts(s: Situation) -> Situation:
    """`s` without the wood and stone Mimo carries that the needs take (`allot`: a repeater's and a joiner's 3
    cobblestone, a lever's, the planks for sticks and slabs), for filling a machine's yard in (Making wave 2:
    on the gate's route runs a yard's floor was filled in with them, 96 cobblestone under a counter on rough
    ground, and a pet's 29 under its computer in one batch, while its repeaters waited for more)."""
    used = allotted(s)[0]
    spared = {item: count - used.get(item, 0) if item in WOOD_AND_STONE else count
              for item, count in s.inventory.items()}
    if spared == dict(s.inventory):
        return s
    return replace(s, state={**s.state, "inventory": {item: count for item, count in spared.items() if count > 0}},
                   memo={})


storage.KEEPS_MORE.append(kept_for_making)
storage.TAKES_MORE.append(from_chests)
ADVANCES["build_storage"] = storage_advances
building.SPARED.append(spared_for_making)
storage.KEEP.update({item: 0 for item in MADE if item not in storage.KEEP})
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
    """What raw_needs asks gathering for, as far as Mimo has room to carry it (the Making final fix wave: on
    the gate's route check a pet with its 16 stacks taken dug every clay within 160 blocks of home, and
    each one was left behind at once, carrying.settle; with no room, build_storage makes some first)."""
    wanted = {}
    for item, count in raw_needs(s).items():
        room = room_for(s.inventory, item, CARRY_STACKS) if item in GATHERED else 0
        if room > 0:
            wanted[item] = min(count, room)
    return wanted


def diggable(s: Situation, cell: Cell, kind: str) -> bool:
    """Still there, with open air over ground (not water), nobody's that Mimo built or tends, and no
    failed step nearby."""
    x, y, z = cell
    if s.grid.material(*cell) != kind or reserved(s.grid, cell) or near_failure(s.state, cell):
        return False
    return kind in PLANTS or (s.grid.passable((x, y + 1, z)) and s.grid.material(x, y + 1, z) != "water")


def plant_cells(s: Situation, root: Cell, plants: tuple[str, ...]) -> list[tuple[Cell, str]]:
    """The cells of a wanted plant worldgen grew at `root`, from its root up; none once it is picked (the
    Making final fix wave, I2: a picked stalk's root reads "air", and it used to count as a source)."""
    kind = s.grid.material(*root)
    if kind not in plants:
        return []
    top = root[1]
    while s.grid.material(root[0], top + 1, root[2]) == kind:
        top += 1
    return [((root[0], y, root[2]), kind) for y in range(root[1], top + 1)]


def ground_at(seed: str, x: int, z: int, kinds: tuple[str, ...]) -> tuple[Cell, str] | None:
    """The natural surface block of a column when it is one of `kinds` ((cell, kind)), else None."""
    kind = surface_material(x, z, seed)
    return ((x, terrain_height(x, z, seed), z), kind) if kind in kinds else None


def far_scan(s: Situation, center: Cell, kind: str) -> list[list[int]]:
    """C1: the FAR_KEPT nearest cells to `center` where `kind` still lies as worldgen put it: clay or sand
    on dry ground within FAR_SIGHT blocks (never a lake bed or a swamp pool), every column; or a plant
    worldgen grew within FAR_PLANTS, the root of a stalk that still stands."""
    cx, _, cz = center
    found: list[tuple[float, tuple[int, int, int]]] = []
    if kind in PLANTS:
        found = [(math.hypot(x - cx, z - cz), (x, y, z))
                 for x, y, z in natural_plants(s.seed, cx, cz, FAR_PLANTS, (kind,))]
    else:
        for x in range(cx - FAR_SIGHT, cx + FAR_SIGHT + 1):
            for z in range(cz - FAR_SIGHT, cz + FAR_SIGHT + 1):
                distance = math.hypot(x - cx, z - cz)
                if distance > FAR_SIGHT:
                    continue
                y = terrain_height(x, z, s.seed)
                if y < SEA_LEVEL or (kind == "clay" and y != SEA_LEVEL):  # clay only lies on shores, at sea level
                    continue
                if surface_material(x, z, s.seed) == kind and not swamp_pool(x, z, s.seed):
                    found.append((distance, (x, y, z)))
    kept: list[list[int]] = []
    for _, cell in sorted(found):
        if s.grid.material(*cell) == kind:
            kept.append(list(cell))
            if len(kept) >= FAR_KEPT:
                break
    return kept


def far_sources(s: Situation, kinds: tuple[str, ...]) -> list[tuple[Cell, str]]:
    """C1: what lies of `kinds` beyond sight, from home (`far_scan`; nothing without one), remembered in
    state["brain"][FAR] and looked over again when home moves, or on a new game day once none of a kind's
    cells is left; only the cells Mimo can still gather (`diggable`), within FAR_SIGHT of where it stands."""
    center = home_cell(s)
    if center is None:
        return []
    day, at = s.clock.get("day_number"), [center[0], center[2]]
    cache = s.brain.get(FAR)
    if not isinstance(cache, dict) or cache.get("at") != at:
        cache = {"at": at, "found": {}}
        s.brain[FAR] = cache
    found: list[tuple[Cell, str]] = []
    for kind in kinds:
        known = cache["found"].get(kind)
        if not isinstance(known, dict) or (known.get("day") != day and not any(
                s.grid.material(*cell) == kind for cell in known.get("cells", []))):
            known = cache["found"][kind] = {"day": day, "cells": far_scan(s, center, kind)}
        for cell in map(tuple, known["cells"]):
            found += plant_cells(s, cell, (kind,)) if kind in PLANTS else [(cell, kind)]
    return [(cell, kind) for cell, kind in found
            if math.hypot(cell[0] - s.here[0], cell[2] - s.here[2]) <= FAR_SIGHT and diggable(s, cell, kind)]


def sources(s: Situation) -> list[tuple[Cell, str]]:
    """(cell, material) Mimo can gather for raw_needs within SOURCE_SIGHT blocks, nearest first, a
    stalk of sugar cane from its top down; and, for a kind it wants with none in sight, what lies of it
    farther out (`far_sources`, C1)."""
    def look() -> list[tuple[Cell, str]]:
        wanted = gathered_wanted(s)
        x, _, z = s.here
        found: list[tuple[Cell, str]] = []
        plants = tuple(kind for kind in PLANTS if kind in wanted)
        if plants:
            for root in natural_plants(s.seed, x, z, SOURCE_SIGHT, plants):
                found += plant_cells(s, root, plants)
        ground = tuple(kind for kind in GROUND if kind in wanted)
        if ground:
            for gx in range(x - SOURCE_SIGHT, x + SOURCE_SIGHT + 1):
                for gz in range(z - SOURCE_SIGHT, z + SOURCE_SIGHT + 1):
                    if math.hypot(gx - x, gz - z) > SOURCE_SIGHT:
                        continue
                    spot = ground_at(s.seed, gx, gz, ground)  # a lake bed's is under water: diggable leaves it
                    if spot is not None:
                        found.append(spot)
        found = [(cell, kind) for cell, kind in found if diggable(s, cell, kind)]
        unseen = tuple(kind for kind in sorted(wanted) if not any(seen == kind for _, seen in found))
        if unseen:
            found += far_sources(s, unseen)
        return sorted(found, key=lambda entry: (math.hypot(entry[0][0] - x, entry[0][2] - z), -entry[0][1], entry[0]))
    return s.sensed("making sources", look)


def in_sight(s: Situation, cell: Cell) -> bool:
    return math.hypot(cell[0] - s.here[0], cell[2] - s.here[2]) <= SOURCE_SIGHT


def gather_valid(s: Situation) -> bool:
    return not s.night and bool(sources(s))


def gather_facts(s: Situation) -> str:
    wanted = ", ".join(f"{count} {item.replace('_', ' ')}" for item, count in sorted(gathered_wanted(s).items()))
    found = sources(s)
    near = sum(1 for cell, _ in found if in_sight(s, cell))
    far = "" if near or not found else (f"; the nearest {found[0][1].replace('_', ' ')} lies "
                                        f"{round(s.distance(found[0][0]))} blocks away")
    return f"wants {wanted} for what it makes; {near} to gather within {SOURCE_SIGHT} blocks{far}"


def plan_gather(s: Situation, context: ActionContext) -> list[dict]:
    """Dig or pick up to PER_BATCH of what is wanted, nearest first; when the nearest lies beyond sight (C1),
    walk to it and dig just that one (a walk in segments where one whole walk cannot reach it: pathing's
    MAX_RANGE): the next batch finds the rest there in sight."""
    if s.night or s.brain["batches"] >= GATHER_BATCHES:
        return []
    wanted, jobs = dict(gathered_wanted(s)), []
    for cell, kind in sources(s):
        if wanted.get(kind, 0) > 0 and len(jobs) < PER_BATCH:
            if not in_sight(s, cell):
                if jobs:
                    break  # the near ones first; the far one is for a later batch
                one_walk = max(abs(cell[0] - s.here[0]), abs(cell[2] - s.here[2])) <= MAX_RANGE
                walk = whole_walk(cell, STAND) if one_walk else walk_to(cell, STAND)
                return [walk, {"kind": "mine", "target": list(cell)}]
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
