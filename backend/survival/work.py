"""Gathering purposes: wood from trees, stone from a staircase dug into the ground, and ores
Mimo has seen.

gather_wood chops the nearest standing tree within 24 blocks, lowest log first, until Mimo
carries 8 logs' worth of wood (craft_tools turns logs into planks). Trees only come back when
Mimo plants saplings (they drop from leaves), so each batch first plants up to 2 carried
saplings on open ground within reach, 3 blocks or more from any trunk or other sapling.
gather_stone needs a pickaxe:
it digs a staircase down from where Mimo stands, two blocks per stair, and turns into a level
tunnel 10 blocks under the surface (or at y -3), until Mimo carries 12 cobblestone; with a stone
pickaxe and no iron ore seen yet, it keeps digging to prospect for iron. It never digs into
water, lava, bedrock, a hole or a cave, or a block it cannot mine, and never digs up farmland or
a sapling. It never digs back the way it came, and never mines the floor of an open cell below
the natural surface (a stair or tunnel it dug earlier, or a cave) unless the same stair just
opened that cell, so it cannot cut its own staircase. The staircase stays climbable, and from
its third stair it is sheltered, so it often becomes Mimo's first home.
mine_ore walks to a remembered coal or iron ore Mimo can harvest and still needs, within 48
blocks, and mines it.

Late in the day, work that takes Mimo away from home scores 30 lower (purposes.late_penalty), so
sleep and go_home win at dusk: gather_wood always, gather_stone when it would start from the
surface, and mine_ore when the ore is more than 16 blocks away. craft_tools needs no trip.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.blocks import hardness, is_replaceable, is_solid
from backend.services.crafting import BLOCKS, TOOL_RANK, can_harvest
from backend.services.worldgen import terrain_height
from backend.survival.grid import Cell, Grid
from backend.survival.memory import cell_of, forget
from backend.survival.purposes import Purpose, late_penalty, register, underground, walk_to
from backend.survival.farming import plant
from backend.survival.nature import SOIL
from backend.survival.senses import by_distance, failed_columns, standing_logs, trunks_near
from backend.survival.situation import Situation
from backend.survival.steps import REACH

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

WOOD_GOAL = 8.0
STAND_REACH = 2.0  # close enough to the lowest log that the top one (3 higher) stays within reach
SAPLINGS_PER_BATCH = 2
SAPLING_ROOM = 3.0  # blocks between a planted sapling and any trunk or other sapling
TREE_SPACE = 6  # open cells a sapling needs above its ground for the trunk and canopy
STONE_GOAL = 12
STAIRS_PER_BATCH = 4
TUNNEL_DEPTH = 10
LOWEST_FLOOR = -3
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
FLUIDS = ("water", "lava")
TENDED = ("farmland", "sapling")  # Mimo's own plots and plantings
ORE_RANGE = 48.0
ORE_REACH = 3.0
ORE_FAR = 16.0  # a trip to an ore farther than this counts as outdoor work late in the day


def wood(inventory: dict) -> float:
    """Wood carried, counted in logs: a log is 1, a plank a quarter, a stick an eighth."""
    return inventory.get("oak_log", 0) + inventory.get("planks", 0) / 4 + inventory.get("sticks", 0) / 8


def has_pickaxe(inventory: dict) -> bool:
    return any(inventory.get(tool, 0) > 0 for tool in TOOL_RANK)


# gather_wood -----------------------------------------------------------------------------------

def logs_to_chop(s: Situation) -> list[Cell]:
    return standing_logs(s.grid, s.seed, s.here, failed_columns(s.state))


def wood_score(s: Situation) -> float:
    base = 65.0 if wood(s.inventory) < 3 else 40.0
    return base + s.trait("diligence") / 10 + s.trait("thrift") / 20 - late_penalty(s)


def wood_facts(s: Situation) -> str:
    logs = logs_to_chop(s)
    tree = f"a tree {round(s.distance(logs[0]))} blocks away" if logs else "no tree near"
    return f"{wood(s.inventory):g} logs of wood carried, {tree}"


def sapling_spots(s: Situation) -> list[Cell]:
    """Open grass, dirt or moss within reach with room for a tree above, nearest first, and each
    SAPLING_ROOM from every trunk, sapling and other spot."""
    x, y, z = s.here
    taken = trunks_near(s.grid, s.seed, x, z, REACH + SAPLING_ROOM)
    candidates = []
    for dx in range(-4, 5):
        for dz in range(-4, 5):
            for cell in ((x + dx, y, z + dz), (x + dx, y + 1, z + dz), (x + dx, y - 1, z + dz)):
                if 1.0 <= math.dist(cell, s.here) <= REACH and sapling_fits(s, cell):
                    candidates.append(cell)
                    break
    spots = []
    for cell in by_distance(candidates, s.here):
        if all(math.hypot(cell[0] - tx, cell[2] - tz) >= SAPLING_ROOM for tx, tz in taken):
            spots.append(cell)
            taken.add((cell[0], cell[2]))
    return spots


def sapling_fits(s: Situation, cell: Cell) -> bool:
    x, y, z = cell
    if s.grid.material(x, y - 1, z) not in SOIL["sapling"]:
        return False
    return all(is_replaceable(material) and material != "water"
               for material in (s.grid.material(x, y + dy, z) for dy in range(TREE_SPACE)))


def plant_saplings(s: Situation) -> list[dict]:
    count = min(SAPLINGS_PER_BATCH, s.count("sapling"))
    if count <= 0:
        return []
    return [plant(cell, "sapling") for cell in sapling_spots(s)[:count]]


def plan_wood(s: Situation, context: ActionContext) -> list[dict]:
    if wood(s.inventory) >= WOOD_GOAL:
        return []
    logs = logs_to_chop(s)
    if not logs:
        return []
    return [*plant_saplings(s), walk_to(logs[0], STAND_REACH), *({"kind": "mine", "target": list(log)} for log in logs)]


register(Purpose(
    "gather_wood", "gather wood", "Chop the nearest tree for logs, the start of every tool.",
    valid=lambda s: wood(s.inventory) < WOOD_GOAL and bool(logs_to_chop(s)),
    facts=wood_facts, score=wood_score, plan=plan_wood,
    thoughts=("I need wood. That tree looks good.", "Wood first. Everything starts with wood.")))


# gather_stone ----------------------------------------------------------------------------------

def look(grid: Grid, changed: dict[Cell, str], cell: Cell) -> str:
    return changed.get(cell) or grid.material(*cell)


def stair(grid: Grid, changed: dict[Cell, str], at: Cell, heading: tuple[int, int], inventory: dict,
          seed: str) -> tuple[list[dict], Cell, int] | None:
    """One stair down (or, deep enough, one level tunnel step) from `at` toward `heading`.

    Returns the steps, where Mimo ends up and how many cobblestone the mining yields, or None
    when the way is blocked. `changed` holds the cells earlier stairs of the same plan opened.
    A block whose cell above is open below the natural surface is the floor of a passage (an
    earlier stair or tunnel, or a cave): it is never mined, unless this stair opened that cell.
    """
    x, y, z = at
    nx, nz = x + heading[0], z + heading[1]
    surface = terrain_height(nx, nz, seed)
    down = y - 1 >= max(LOWEST_FLOOR, surface - TUNNEL_DEPTH)
    to = (nx, y - 1, nz) if down else (nx, y, nz)
    if not is_solid(look(grid, changed, (nx, to[1] - 1, nz))):
        return None  # a hole or a cave below: never dig into it
    steps, stones, opened = [], 0, set()
    for cell in ([(nx, y, nz), to] if down else [to]):
        material = look(grid, changed, cell)
        if material in FLUIDS:
            return None
        if material in TENDED or look(grid, changed, (nx, cell[1] + 1, nz)) in TENDED:
            return None  # never dig up Mimo's farm or a sapling it planted
        if not is_solid(material):
            continue
        if hardness(material) is None or not can_harvest(material, inventory):
            return None
        above = (nx, cell[1] + 1, nz)
        if above not in opened and above[1] <= surface and not is_solid(look(grid, changed, above)):
            return None  # the floor of an open cell underground
        steps.append({"kind": "mine", "target": list(cell)})
        stones += 1 if BLOCKS.get(material, {}).get("drop") == "cobblestone" else 0
        changed[cell] = "air"
        opened.add(cell)
    steps.append(walk_to(to))
    return steps, to, stones


def dig_heading(s: Situation) -> tuple[int, int] | None:
    """Where to dig: the last heading if it still works, else toward the highest ground nearby,
    but never straight back the way the last heading came (that would dig up its own stairs)."""
    x, _, z = s.here
    headings = sorted(DIRECTIONS, key=lambda d: -terrain_height(x + 3 * d[0], z + 3 * d[1], s.seed))
    last = s.brain.get("dig_heading")
    if last:
        last, back = tuple(last), (-last[0], -last[1])
        headings = [last, *(heading for heading in headings if heading not in (last, back))]
    for heading in headings:
        if stair(s.grid, {}, s.here, heading, s.inventory, s.seed) is not None:
            return heading
    return None


def prospecting(s: Situation) -> bool:
    """Digging on for iron: Mimo has a stone pickaxe, still wants iron and has seen none."""
    return (s.count("stone_pickaxe") > 0 and "iron_ore" in wanted_ores(s)
            and not any(place["kind"] == "ore" and place["note"] == "iron_ore" for place in s.places))


def wants_stone(s: Situation) -> bool:
    return has_pickaxe(s.inventory) and (s.count("cobblestone") < STONE_GOAL or prospecting(s))


def stone_score(s: Situation) -> float:
    """Starting a new staircase from the surface is outdoor work; digging on underground is not."""
    late = late_penalty(s, outdoors=not underground(s))
    if s.count("cobblestone") >= STONE_GOAL:  # prospecting for iron
        return 40.0 + s.trait("curiosity") / 10 - late
    return 50.0 + s.trait("diligence") / 10 + s.trait("thrift") / 20 - late


def stone_facts(s: Situation) -> str:
    if s.count("cobblestone") >= STONE_GOAL:
        return f"{s.count('cobblestone')} cobblestone carried; digging on for iron ore, none seen yet"
    return f"{s.count('cobblestone')} cobblestone carried, a pickaxe in hand"


def plan_stone(s: Situation, context: ActionContext) -> list[dict]:
    cobblestone = s.count("cobblestone")
    if not wants_stone(s):
        return []
    goal = math.inf if prospecting(s) else STONE_GOAL
    heading = dig_heading(s)
    if heading is None:
        return []
    s.brain["dig_heading"] = list(heading)
    changed: dict[Cell, str] = {}
    steps, at = [], s.here
    for _ in range(STAIRS_PER_BATCH):
        result = stair(s.grid, changed, at, heading, s.inventory, s.seed)
        if result is None:
            break
        more, at, stones = result
        steps.extend(more)
        cobblestone += stones
        if cobblestone >= goal:
            break
    return steps


register(Purpose(
    "gather_stone", "gather stone", "Dig a staircase into the ground for cobblestone, and on for iron ore.",
    valid=lambda s: wants_stone(s) and dig_heading(s) is not None,
    facts=stone_facts, score=stone_score, plan=plan_stone,
    thoughts=("Time to dig for stone.", "Stone makes better tools than wood.")))


# mine_ore --------------------------------------------------------------------------------------

def wanted_ores(s: Situation) -> tuple[str, ...]:
    """Coal until Mimo carries 8; iron until it has 3 ore or ingots (or an iron pickaxe)."""
    wanted = []
    if s.count("coal") < 8:
        wanted.append("coal_ore")
    if s.count("iron_ore", "iron_ingot") < 3 and not s.count("iron_pickaxe"):
        wanted.append("iron_ore")
    return tuple(wanted)


def passage_floor(s: Situation, cell: Cell) -> bool:
    """The block is the floor of an open cell below the natural surface: a stair or tunnel Mimo dug,
    or a cave. Mining it can cut Mimo's way back up (a stair one step higher is then out of reach),
    so ores there are left alone, as `stair` leaves such floors alone."""
    x, y, z = cell
    return y + 1 <= terrain_height(x, z, s.seed) and not is_solid(s.grid.material(x, y + 1, z))


def ore_targets(s: Situation) -> list[dict]:
    """Remembered, wanted ores Mimo can harvest within 48 blocks, nearest first, leaving out ores
    that are the floor of a passage."""
    wanted, (x, _, z) = wanted_ores(s), s.here
    found = [place for place in s.places
             if place["kind"] == "ore" and place["note"] in wanted and can_harvest(place["note"], s.inventory)
             and math.hypot(place["x"] - x, place["z"] - z) <= ORE_RANGE and not passage_floor(s, cell_of(place))]
    return sorted(found, key=lambda place: s.distance(cell_of(place)))


def ore_score(s: Situation) -> float:
    """A trip to a far ore is outdoor work late in the day; a near one is not."""
    targets = ore_targets(s)
    iron = any(place["note"] == "iron_ore" for place in targets)
    far = bool(targets) and s.distance(cell_of(targets[0])) > ORE_FAR
    return (50.0 + s.trait("bravery") / 10 + s.trait("curiosity") / 20 + (15.0 if iron else 0.0)
            - late_penalty(s, outdoors=far))


def ore_facts(s: Situation) -> str:
    targets = ore_targets(s)
    nearest = targets[0]
    return (f"{len(targets)} ores remembered; the nearest is {nearest['note'].replace('_', ' ')} "
            f"{round(s.distance(cell_of(nearest)))} blocks away")


def plan_ore(s: Situation, context: ActionContext) -> list[dict]:
    """Walk within reach of the nearest wanted ore and mine it. Ores that are gone are forgotten."""
    for place in ore_targets(s):
        cell = cell_of(place)
        if s.grid.material(*cell) != place["note"]:
            if s.db is not None:
                forget(s.db, "ore", cell)
            continue
        steps = [] if s.distance(cell) <= REACH else [walk_to(cell, ORE_REACH)]
        return [*steps, {"kind": "mine", "target": list(cell)}]
    return []


register(Purpose(
    "mine_ore", "mine ore", "Go back to coal or iron ore seen while digging and mine it.",
    valid=lambda s: bool(ore_targets(s)), facts=ore_facts, score=ore_score, plan=plan_ore,
    thoughts=("I remember seeing ore down there.", "That ore will make something good.")))
