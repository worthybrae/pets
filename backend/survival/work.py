"""Gathering purposes: wood from trees, stone from a staircase dug into the ground, and ores
Mimo has seen.

gather_wood chops the nearest standing tree within 24 blocks, lowest log first, until Mimo
carries 8 logs' worth of wood (craft_tools turns logs into planks), and while a shelter Mimo
started waits for blocks, that many more as logs (building.building_need). A tree is a generated
one or one grown from a sapling Mimo planted (remembered as a `tree` place); other placed logs are
something built, not a tree. Trees only come back when Mimo plants saplings (they drop from
leaves), so each batch first plants up to 2 carried saplings on open ground within reach, 3
blocks or more from any trunk or other sapling, on the natural surface (never in Mimo's own
staircase) and 2 blocks or more from a home or shelter.
gather_stone needs a pickaxe and, short of prospecting, room left to carry more cobblestone: it
digs a staircase down from where Mimo stands, one block down per stair, 2 wide and 3 tall where
that fits (L3: the owner asked for passages big enough to see into), and turns into a level tunnel
of the same size 10 blocks under the surface (or at y -3), until Mimo carries 12 cobblestone (and the blocks a
started shelter still waits for); with a stone pickaxe and no iron ore seen yet, it keeps digging
to prospect for iron regardless of room. It never digs into water, lava, bedrock, a hole or a
cave, or a block it cannot mine, and never digs up farmland, a sapling or anything Mimo built, its
door or the way in (structures.reserved). It never digs back the way it came, and never mines the
floor of an open cell below the natural surface (a stair or tunnel it dug earlier, or a cave)
unless the same stair just opened that cell, so it cannot cut its own staircase. The staircase
stays climbable, and from its fourth stair it is sheltered, so it often becomes Mimo's first home.
mine_ore walks to a remembered coal, iron, gold or diamond ore Mimo can harvest and still needs,
within 48 blocks (96 for an ore making wants: the Making final fix wave), and mines it: gold and
diamonds once it has an iron pickaxe and knows where enough lie for the pickaxe above it (L3), and
has learned about their ore (L4b, backend.survival.journal).

Late in the day, work that takes Mimo away from home scores 30 lower (purposes.late_penalty), so
sleep and go_home win at dusk: gather_wood always, gather_stone when it would start from the
surface, and mine_ore when the ore is more than 16 blocks away. craft_tools needs no trip.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from backend.services.blocks import hardness, is_replaceable, is_solid
from backend.services.crafting import BLOCKS, LOGS, TOOL_RANK, can_harvest, have
from backend.services.worldgen import terrain_height
from backend.survival.grid import Cell, Grid, supports
from backend.survival.memory import SHELTER_KINDS, cell_of, forget
from backend.survival.purposes import Purpose, late_penalty, register, underground, walk_to
from backend.survival.building import building_need
from backend.survival.creatures.harm import armor_iron, armor_wanted
from backend.survival.carrying import CARRY_STACKS, room_for
from backend.survival.farming import plant
from backend.survival.nature import SOIL
from backend.survival.once import log_once
from backend.survival.senses import ORES, by_distance, failed_columns, standing_logs, trunks_near
from backend.survival.situation import Situation
from backend.survival.steps import REACH
from backend.survival.structures import reserved

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

WOOD_GOAL = 8.0
STAND_REACH = 2.0  # close enough to the lowest log that the top one (3 higher) stays within reach
SAPLINGS_PER_BATCH = 2
SAPLING_ROOM = 3.0  # blocks between a planted sapling and any trunk or other sapling
TREE_SPACE = 6  # open cells a sapling needs above its ground for the trunk and canopy
HOME_ROOM = 2.0  # blocks between a planted sapling and a home or shelter
STONE_GOAL = 12
STAIRS_PER_BATCH = 4
TUNNEL_DEPTH = 10
LOWEST_FLOOR = -3
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
FLUIDS = ("water", "lava")
PASSAGE_TALL = 3  # cells a stair or tunnel is cut high; its second column (left of the heading) too
TREE = "tree"  # a remembered place: a sapling Mimo planted, so the tree there is its to chop
ORE_RANGE = 48.0
# The walk toward a remembered ore stops this close to it (fix round 1, item 4): a rubble cell can
# reveal an ore diagonally, up to 3.32 blocks from every floor cell around it, and REACH (4.0,
# steps.py's own mine reach) is the smallest of the reaches the mine step accepts that still covers
# that: a 3.0 reach asked for a walk closer than the ore's own floor ever let mine_ore stand, so
# the route search ran to its node limit and failed, wasted on every such ore.
ORE_REACH = REACH
ORE_FAR = 16.0  # a trip to an ore farther than this counts as outdoor work late in the day
# The Making final fix wave: an ore making wants (MORE_ORES: copper, and iron for the workshop's bars) is worth a
# longer trip; on the gate's route check the copper a pet had seen lay 67 blocks and more from home, or was the
# floor of a passage, so mine_ore never went for it and gather_stone never dug on to find more.
MAKING_ORE_RANGE = 96.0


def wood(inventory: dict) -> float:
    """Wood carried, counted in logs: a log of any wood is 1, planks a quarter, a stick an eighth."""
    return have(inventory, "oak_log") + have(inventory, "planks") / 4 + inventory.get("sticks", 0) / 8


def has_pickaxe(inventory: dict) -> bool:
    return any(inventory.get(tool, 0) > 0 for tool in TOOL_RANK)


# gather_wood -----------------------------------------------------------------------------------

def logs_to_chop(s: Situation) -> list[Cell]:
    """The nearest tree's logs: a generated tree, or one grown from a sapling Mimo planted (placed
    logs anywhere else, like a wall, are not trees)."""
    grown = {(place["x"], place["z"]) for place in s.places if place["kind"] == TREE}
    return standing_logs(s.grid, s.seed, s.here, failed_columns(s.state), grown=grown)


def wood_goal(s: Situation) -> float:
    """8 logs of wood, and the shelter's missing blocks as logs (4 planks each) on top."""
    return WOOD_GOAL + building_need(s) / 4


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
                if 1.0 <= math.dist(cell, s.here) <= REACH and sapling_fits(s, cell) and not reserved(s.grid, cell):
                    candidates.append(cell)
                    break
    spots = []
    for cell in by_distance(candidates, s.here):
        if all(math.hypot(cell[0] - tx, cell[2] - tz) >= SAPLING_ROOM for tx, tz in taken):
            spots.append(cell)
            taken.add((cell[0], cell[2]))
    return spots


def sapling_fits(s: Situation, cell: Cell) -> bool:
    """Soil on the natural surface (never the floor of Mimo's staircase, a tunnel or a cave), at
    least HOME_ROOM from a home or shelter, with room for a tree above."""
    x, y, z = cell
    if y - 1 < terrain_height(x, z, s.seed) or s.grid.material(x, y - 1, z) not in SOIL["sapling"]:
        return False
    if any(place["kind"] in SHELTER_KINDS and math.dist(cell, cell_of(place)) < HOME_ROOM for place in s.places):
        return False
    return all(is_replaceable(material) and material != "water"
               for material in (s.grid.material(x, y + dy, z) for dy in range(TREE_SPACE)))


def plant_saplings(s: Situation) -> list[dict]:
    count = min(SAPLINGS_PER_BATCH, s.count("sapling"))
    if count <= 0:
        return []
    return [plant(cell, "sapling") for cell in sapling_spots(s)[:count]]


def plan_wood(s: Situation, context: ActionContext) -> list[dict]:
    if wood(s.inventory) >= wood_goal(s):
        return []
    logs = logs_to_chop(s)
    if not logs:
        return []
    return [*plant_saplings(s), walk_to(logs[0], STAND_REACH), *({"kind": "mine", "target": list(log)} for log in logs)]


register(Purpose(
    "gather_wood", "gather wood", "Chop the nearest tree for logs, the start of every tool.",
    valid=lambda s: wood(s.inventory) < wood_goal(s) and bool(logs_to_chop(s)),
    facts=wood_facts, score=wood_score, plan=plan_wood,
    thoughts=("I need wood. That tree looks good.", "Wood first. Everything starts with wood.")))


# gather_stone ----------------------------------------------------------------------------------

def look(grid: Grid, changed: dict[Cell, str], cell: Cell) -> str:
    return changed.get(cell) or grid.material(*cell)


def side_of(heading: tuple[int, int]) -> tuple[int, int]:
    """The direction to the left of `heading`: where a passage's second column goes."""
    return -heading[1], heading[0]


def cut(grid: Grid, changed: dict[Cell, str], cell: Cell, surface: int, inventory: dict,
        opened: set[Cell]) -> str | None:
    """How one cell of a passage opens: "" when it is open already, its block when Mimo mines it, or
    None when it must stay: water or lava, something Mimo built or tends (or the cell over it), a
    block Mimo cannot mine, or the floor of an open cell below the natural surface that this stair
    did not open."""
    x, y, z = cell
    material = look(grid, changed, cell)
    if material in FLUIDS or reserved(grid, cell) or reserved(grid, (x, y + 1, z)):
        return None
    if not is_solid(material):
        return ""
    if hardness(material) is None or not can_harvest(material, inventory):
        return None
    above = (x, y + 1, z)
    if above not in opened and above[1] <= surface and not is_solid(look(grid, changed, above)):
        return None
    return material


def stair(grid: Grid, changed: dict[Cell, str], at: Cell, heading: tuple[int, int], inventory: dict,
          seed: str) -> tuple[list[dict], Cell, int] | None:
    """One stair down (or, deep enough, one level tunnel step) from `at` toward `heading`, cut 3 cells
    tall in Mimo's column and in the column to the left of the heading, so the passage is 2 wide and
    3 tall where that fits.

    Mimo's column must open where it will stand and, on a stair down, the headroom over that: when
    either cannot be cut the way is blocked and this returns None. Every other cell (the third one
    up, and the side column, which is only cut over solid ground) opens where it can and stays where
    it cannot, so the passage narrows or lowers there. Those widening cells break into rubble Mimo
    leaves behind (`rubble` mine steps), so a stair yields what a narrow one did (resolution 17),
    except an ore or a surface log: left standing, since either is worth a trip on purpose and a
    rubble cell drops nothing (fix round 1, item 3 and the minors).
    Returns the steps, top cells first, where Mimo ends up and how many cobblestone the mining
    yields. `changed` holds the cells earlier stairs of
    the same plan opened. A block whose cell above is open below the natural surface is the floor of
    a passage (an earlier stair or tunnel, or a cave): it is never mined, unless this stair opened
    that cell.
    """
    x, y, z = at
    nx, nz = x + heading[0], z + heading[1]
    surface = terrain_height(nx, nz, seed)
    down = y - 1 >= max(LOWEST_FLOOR, surface - TUNNEL_DEPTH)
    to = (nx, y - 1, nz) if down else (nx, y, nz)
    if not supports(look(grid, changed, (nx, to[1] - 1, nz)), look(grid, changed, to)):
        return None  # a hole or a cave below, or a fence that would not hold Mimo: never dig into it
    columns = [(nx, nz, surface, 2 if down else 1)]  # (x, z, its surface, how many lowest cells it needs)
    sx, sz = nx + side_of(heading)[0], nz + side_of(heading)[1]
    if is_solid(look(grid, changed, (sx, to[1] - 1, sz))):
        columns.append((sx, sz, terrain_height(sx, sz, seed), 0))
    steps, stones, opened = [], 0, set()
    for cx, cz, top, needed in columns:
        for dy in reversed(range(PASSAGE_TALL)):
            cell = (cx, to[1] + dy, cz)
            block = cut(grid, changed, cell, top, inventory, opened)
            if block is None:
                if dy < needed:
                    return None
                continue
            if block:
                keep = dy < needed  # the cells Mimo walks through; it leaves the rest as rubble
                if not keep and (block in ORES or block in LOGS):
                    continue  # an ore or a surface log is worth a trip on purpose: leave it standing
                steps.append({"kind": "mine", "target": list(cell), **({} if keep else {"rubble": True})})
                stones += 1 if keep and BLOCKS.get(block, {}).get("drop") == "cobblestone" else 0
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
        if digs(s, heading):
            return heading
    return None


def digs(s: Situation, heading: tuple[int, int]) -> bool:
    """Whether a batch toward `heading` would mine at least one cell: on Mimo's own staircase, a
    heading already dug all the way down still lets `stair` succeed (it just walks the open
    stairs), and the last heading always wins over an untried one, so gather_stone and go_home
    took turns over a batch that dug nothing. Plans the batch the same way plan_stone does, with
    no route search, so it stays cheap."""
    changed: dict[Cell, str] = {}
    at = s.here
    for _ in range(STAIRS_PER_BATCH):
        result = stair(s.grid, changed, at, heading, s.inventory, s.seed)
        if result is None:
            return False
        more, at, _ = result
        if any(step["kind"] == "mine" for step in more):
            return True
    return False


def prospecting(s: Situation) -> bool:
    """Digging on for iron: Mimo has a stone pickaxe, still wants iron and has seen none. Making: or for
    an ore MORE_ORES wants that it knows none of it could go for (`in_reach`: the final fix wave; copper
    seen only far off, or as a passage's floor, counts as none; coal lies in any staircase's walls), with
    a stone pickaxe or better."""
    seen = {place["note"] for place in s.places if place["kind"] == "ore"}
    iron = s.count("stone_pickaxe") > 0 and "iron_ore" in wanted_ores(s) and "iron_ore" not in seen
    more = pickaxe_rank(s.inventory) >= TOOL_RANK["stone_pickaxe"] and any(
        not in_reach(s, ore) for ore in more_ores(s) if ore != "coal_ore")
    return iron or more


# Making: functions of the Situation giving more cobblestone gather_stone digs for (what making needs).
MORE_STONE: list = []


def stone_goal(s: Situation) -> float:
    """12 cobblestone, and the shelter's missing blocks on top; Making: and what MORE_STONE add (one that
    crashes adds nothing, logged once)."""
    more = 0.0
    for extra in MORE_STONE:
        try:
            more += float(extra(s))
        except Exception as error:
            log_once(logger, "more stone", error)
    return STONE_GOAL + building_need(s) + more


def wants_stone(s: Situation) -> bool:
    """A pickaxe, and either room left to carry more cobblestone with less than the goal carried
    yet (digging for a stone Mimo cannot even carry would only be thrown away), or prospecting on
    for iron regardless of room."""
    if not has_pickaxe(s.inventory):
        return False
    normal = s.count("cobblestone") < stone_goal(s) and room_for(s.inventory, "cobblestone", CARRY_STACKS) > 0
    return normal or prospecting(s)


def stone_score(s: Situation) -> float:
    """Starting a new staircase from the surface is outdoor work; digging on underground is not."""
    late = late_penalty(s, outdoors=not underground(s))
    if s.count("cobblestone") >= stone_goal(s) and prospecting(s):  # prospecting for iron
        return 40.0 + s.trait("curiosity") / 10 - late
    return 50.0 + s.trait("diligence") / 10 + s.trait("thrift") / 20 - late


def stone_facts(s: Situation) -> str:
    if s.count("cobblestone") >= stone_goal(s) and prospecting(s):
        return f"{s.count('cobblestone')} cobblestone carried; digging on for iron ore, none seen yet"
    return f"{s.count('cobblestone')} cobblestone carried, a pickaxe in hand"


def plan_stone(s: Situation, context: ActionContext) -> list[dict]:
    cobblestone = s.count("cobblestone")
    if not wants_stone(s):
        return []
    goal = math.inf if prospecting(s) else stone_goal(s)
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

def pickaxe_rank(inventory: dict) -> int:
    """The rank of the best pickaxe Mimo carries (crafting.TOOL_RANK), 0 with none."""
    return max((rank for tool, rank in TOOL_RANK.items() if inventory.get(tool, 0) > 0), default=0)


def ladder_ores(inventory: dict) -> set[str]:
    """What the pickaxe ladder counts in Mimo's arms toward its next pickaxe (`wanted_ores`): gold ore
    and gold ingots, from an iron pickaxe until a gold one; nothing otherwise. The L4b final fix wave's
    (b): an expedition's packing put them in the chest at home (expedition.packed_kept), and mine_ore
    then went after gold that lay in the chest; they stay on Mimo now."""
    rank = pickaxe_rank(inventory)
    return {"gold_ore", "gold_ingot"} if TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["gold_pickaxe"] else set()


# L4: functions of (Situation, ore) that let mine_ore go for any ore of that kind Mimo remembers,
# not only once it knows where enough lie (diamonds as Mimo's goal, backend.survival.life_goals).
EAGER: list = []


def eager(s: Situation, ore: str) -> bool:
    """One of EAGER wants `ore` now; one that crashes counts as no (logged once)."""
    for wants in EAGER:
        try:
            if wants(s, ore):
                return True
        except Exception as error:
            log_once(logger, "eager for ore", error)
    return False


# Making: functions of the Situation giving more ores mine_ore goes after now (copper, for what Mimo
# makes: backend.survival.making).
MORE_ORES: list = []


def more_ores(s: Situation) -> list[str]:
    """The ores MORE_ORES want now; one that crashes wants none (logged once)."""
    found: list[str] = []
    for wants in MORE_ORES:
        try:
            found += [ore for ore in wants(s) if ore not in found]
        except Exception as error:
            log_once(logger, "more ores", error)
    return found


def enough_known(s: Situation, ore: str, have: int, need: int = 3) -> bool:
    """Mimo has fewer than `need` of what `ore` gives, and with the ores of that kind it remembers it
    would have enough: one trip then gets them all (L3's gold and diamonds, needed 3 at a time).
    L4: while a goal wants the ore (EAGER), any one it remembers will do."""
    known = sum(1 for place in s.places if place["kind"] == "ore" and place["note"] == ore)
    if have < need and known >= 1 and eager(s, ore):
        return True
    return have < need <= have + known


def wanted_ores(s: Situation) -> tuple[str, ...]:
    """Coal until Mimo carries 8; iron until it has 3 ore or ingots (or an iron pickaxe or better),
    and then, once a creature has hurt it (L4: or while armor is its goal), as much as the iron
    armor it lacks takes; with an iron pickaxe (L3), gold (until a gold pickaxe or better) and
    diamonds (until a diamond pickaxe), but only once it knows where enough lie for a pickaxe
    (`enough_known`; L4: any one it knows while diamonds are its goal) and (L4b) has learned about
    their ore by seeing it (backend.survival.journal)."""
    wanted, rank = [], pickaxe_rank(s.inventory)
    if s.count("coal") < 8:
        wanted.append("coal_ore")
    iron = 3 if rank < TOOL_RANK["iron_pickaxe"] else armor_iron(s.inventory) if armor_wanted(s.state) else 0
    if s.count("iron_ore", "iron_ingot") < iron:
        wanted.append("iron_ore")
    if (TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["gold_pickaxe"] and "gold_ore" in s.lessons
            and enough_known(s, "gold_ore", s.count("gold_ore", "gold_ingot"))):
        wanted.append("gold_ore")
    if (TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["diamond_pickaxe"] and "diamond_ore" in s.lessons
            and enough_known(s, "diamond_ore", s.count("diamond"))):
        wanted.append("diamond_ore")
    wanted += [ore for ore in more_ores(s) if ore not in wanted]  # Making: copper
    return tuple(wanted)


def passage_floor(s: Situation, cell: Cell) -> bool:
    """The block is the floor of an open cell below the natural surface: a stair or tunnel Mimo dug,
    or a cave. Mining it can cut Mimo's way back up (a stair one step higher is then out of reach),
    so ores there are left alone, as `stair` leaves such floors alone."""
    x, y, z = cell
    return y + 1 <= terrain_height(x, z, s.seed) and not is_solid(s.grid.material(x, y + 1, z))


def reachable_ores(s: Situation, kinds) -> list[dict]:
    """Remembered ores of `kinds` Mimo could go for: within ORE_RANGE blocks (MAKING_ORE_RANGE for one
    making wants, MORE_ORES), not the floor of a passage."""
    making, (x, _, z) = set(more_ores(s)), s.here

    def reach(ore: str) -> float:
        return MAKING_ORE_RANGE if ore in making else ORE_RANGE

    return [place for place in s.places if place["kind"] == "ore" and place["note"] in kinds
            and math.hypot(place["x"] - x, place["z"] - z) <= reach(place["note"])
            and not passage_floor(s, cell_of(place))]


def in_reach(s: Situation, ore: str) -> bool:
    """Mimo knows an ore of this kind it could go for (`reachable_ores`)."""
    return bool(reachable_ores(s, (ore,)))


def ore_targets(s: Situation) -> list[dict]:
    """Remembered, wanted ores Mimo can harvest within 48 blocks (96 for one making wants), nearest first,
    leaving out ores that are the floor of a passage."""
    found = [place for place in reachable_ores(s, wanted_ores(s)) if can_harvest(place["note"], s.inventory)]
    return sorted(found, key=lambda place: s.distance(cell_of(place)))


def ore_score(s: Situation) -> float:
    """A trip to a far ore is outdoor work late in the day; a near one is not."""
    targets = ore_targets(s)
    iron = any(place["note"] in ("iron_ore", "gold_ore", "diamond_ore") for place in targets)
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
    "mine_ore", "mine ore", "Go back to coal, iron, gold or diamond ore seen while digging and mine it.",
    valid=lambda s: bool(ore_targets(s)), facts=ore_facts, score=ore_score, plan=plan_ore,
    thoughts=("I remember seeing ore down there.", "That ore will make something good.")))
