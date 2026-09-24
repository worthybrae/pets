"""Trapped: a staircase out of a pit Mimo cannot walk out of.

Routes can drop 3 blocks but climb only 1, so Mimo can walk into a pit it cannot leave. When a
step fails and at least two walks found no path -- two of the current purpose since it was chosen
(walks that got partway in between do not matter), or (L3 final fix wave) any two within the last
TRAP_WINDOW game seconds, whatever purposes planned them -- the brain checks whether Mimo is
trapped (one search from the tick's budget). Mimo is trapped when it stands below the natural
surface and no cell at or above it, and no home, is reachable within SURFACE_SEARCH cells
(`way_out`, a flood of Mimo's moves). Before the L3 final fix wave the check needed two failures
of one purpose, when each purpose in a pit gives up after one, and it counted only pits of fewer
than 256 cells, when a cave pocket Mimo walked into down its own stairs held 393: a pet was
stranded in one for most of a game day.
The way out is a staircase up, one block up per step: mine the block over Mimo's head
and the stair cell when they are solid, and place a carried block where a stair has nothing to
stand on (mined dirt and stone go into the stock too). Where they fit (L3), the two cells over each
stair and the three beside it (left of the heading, over solid ground) open too, so the way out is
2 wide and 3 tall like Mimo's own stairs; a cell that cannot be mined there is left, the same rule
as work.cut: never something Mimo built or tends (or the cell above it), and never an ore or a
surface log, left standing for Mimo to gather later (fix round 1). A cell that is open already
needs no mining, so it is used whether or not it is claimed: Mimo trapped in its shelter's room or
passage walks out through them (L3 final fix wave). The cell over a stair is the
next stair's headroom and is kept; the other widening cells break into rubble Mimo leaves behind.
It tries the four directions and takes the
first staircase that brings Mimo above the natural surface within 24 stairs, at most once per 60
real seconds. There is no jump step, so a narrow shaft in rock Mimo cannot mine, with no blocks
to place, stays a trap.
"""

from __future__ import annotations

from collections import deque

from backend.services.blocks import hardness, is_replaceable, is_solid
from backend.services.crafting import BLOCKS, LOGS, can_harvest
from backend.services.worldgen import terrain_height
from backend.survival.actions import ActionContext, take_search
from backend.survival.grid import Cell, Grid, supports
from backend.survival.memory import cell_of
from backend.survival.pathing import moves
from backend.survival.purposes import walk_to
from backend.survival.senses import ORES
from backend.survival.situation import in_tick
from backend.survival.steps import as_cell
from backend.survival.structures import reserved
from backend.survival.triggers import ensure_brain
from backend.survival.work import side_of

# L3 final fix wave: the cells `way_out` floods at most looking for the surface or home (the seed-11
# pocket the fix was for held 393). Over 180 real cave floors a flood that finds no way out costs
# about 6 ms with the ground already loaded (28 ms at most) and 60 ms loading it (295 ms at most,
# about what one failed 20,000-cell path search costs, and it spends one from the tick's budget).
SURFACE_SEARCH = 2000
TRAP_WINDOW = 300.0  # game seconds: two walks with no path this close together check for a trap
MAX_STAIRS = 24
ESCAPE_RETRY = 60.0
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
FLUIDS = ("water", "lava")
# Blocks Mimo will place to stand on, cheapest first.
PLACEABLE = ("dirt", "cobblestone", "sand", "gravel", "clay", "planks", "birch_planks", "spruce_planks", "stone_bricks",
             "oak_log", "birch_log", "spruce_log")


def walks_failed_twice(state: dict, at: float, scale: float = 1.0) -> bool:
    """At least two walks failed with no path: of the current purpose since it was chosen, or of
    any purpose within the last TRAP_WINDOW game seconds (`scale` is game seconds per real one)."""
    brain = ensure_brain(state)
    since = brain["chosen_at"] if brain["chosen_at"] is not None else float("-inf")
    failed = [entry for entry in state["recent_actions"]
              if entry.get("kind") == "walk" and entry.get("result") == "failed" and entry.get("code") == "no_path"]
    of_purpose = [entry for entry in failed
                  if entry.get("purpose") == brain["purpose"] and entry.get("ended_at", since) >= since]
    lately = [entry for entry in failed if (at - entry.get("ended_at", float("-inf"))) * scale <= TRAP_WINDOW]
    return len(of_purpose) >= 2 or len(lately) >= 2


def on_surface(cell: Cell, seed: str) -> bool:
    """Mimo stands at or above the natural surface there (not in a staircase, tunnel or cave)."""
    return cell[1] > terrain_height(cell[0], cell[2], seed)


def way_out(grid: Grid, start: Cell, seed: str, homes: frozenset[Cell] | set[Cell] = frozenset(),
            limit: int = SURFACE_SEARCH) -> bool:
    """Whether Mimo can walk from `start` to a cell at or above the natural surface, or to one of
    `homes`, looking at no more than `limit` cells, nearest first. False means trapped."""
    seen, frontier = {start}, deque([start])
    while frontier:
        cell = frontier.popleft()
        if cell in homes or on_surface(cell, seed):
            return True
        for step in moves(grid, cell):
            if step not in seen and len(seen) < limit:
                seen.add(step)
                frontier.append(step)
    return False


def look(grid: Grid, changed: dict[Cell, str], cell: Cell) -> str:
    return changed.get(cell) or grid.material(*cell)


def open_up(grid: Grid, changed: dict[Cell, str], cell: Cell, stock: dict, steps: list[dict],
            rubble: bool = False) -> bool:
    """Make `cell` open, mining it if it is solid. False for fluids, and for a solid block Mimo built
    or tends (or under one, the same rule as work.cut) or cannot mine. An open cell needs no mining,
    so it is used even when claimed: the check once came first and blocked the shelter's own room
    and passage, the cells Mimo must walk through (L3 final fix wave). A `rubble` cell
    is also left standing when it holds an ore or a surface log (fix round 1, items 3 and the
    minors): those are worth collecting on purpose, not losing to a widening cell with no drop.
    A `rubble` cell that is mined is left behind, so it adds nothing to the stock."""
    x, y, z = cell
    material = look(grid, changed, cell)
    if material in FLUIDS:
        return False
    if not is_solid(material):
        return True  # nothing to mine: an open cell is used even when claimed (L3 final fix wave)
    if reserved(grid, cell) or reserved(grid, (x, y + 1, z)):
        return False
    if hardness(material) is None or not can_harvest(material, stock):
        return False
    if rubble and (material in ORES or material in LOGS):
        return False
    steps.append({"kind": "mine", "target": list(cell), **({"rubble": True} if rubble else {})})
    changed[cell] = "air"
    drop = BLOCKS.get(material, {}).get("drop")
    if drop and not rubble:
        stock[drop] = stock.get(drop, 0) + 1
    return True


def staircase(grid: Grid, here: Cell, heading: tuple[int, int], inventory: dict, seed: str) -> list[dict] | None:
    """Stairs up from `here` toward `heading` until Mimo stands above the natural surface, or None."""
    changed: dict[Cell, str] = {}
    stock, steps = dict(inventory), []
    x, y, z = here
    dx, dz = heading
    for i in range(1, MAX_STAIRS + 1):
        below = (x + (i - 1) * dx, y + i - 1, z + (i - 1) * dz)
        stair = (x + i * dx, y + i, z + i * dz)
        headroom = (below[0], below[1] + 1, below[2])
        if not (open_up(grid, changed, headroom, stock, steps) and open_up(grid, changed, stair, stock, steps)):
            return None
        open_up(grid, changed, (stair[0], stair[1] + 1, stair[2]), stock, steps)  # the next stair's headroom
        open_up(grid, changed, (stair[0], stair[1] + 2, stair[2]), stock, steps, rubble=True)
        sx, sz = side_of(heading)
        side = (stair[0] + sx, stair[1], stair[2] + sz)
        if is_solid(look(grid, changed, (side[0], side[1] - 1, side[2]))):
            for dy in (0, 1, 2):
                open_up(grid, changed, (side[0], side[1] + dy, side[2]), stock, steps, rubble=True)
        support = (stair[0], stair[1] - 1, stair[2])
        if not supports(look(grid, changed, support), look(grid, changed, stair)):
            block = next((item for item in PLACEABLE if stock.get(item, 0) > 0), None)
            if block is None or not is_replaceable(look(grid, changed, support)):
                return None
            steps.append({"kind": "place", "target": list(support), "block": block})
            stock[block] -= 1
            changed[support] = block
        steps.append(walk_to(stair))
        if stair[1] > terrain_height(stair[0], stair[2], seed):
            return steps
    return None


def escape_plan(grid: Grid, here: Cell, inventory: dict, seed: str) -> list[dict]:
    """The first staircase out, trying the four directions in turn; [] when none works."""
    for heading in DIRECTIONS:
        steps = staircase(grid, here, heading, inventory, seed)
        if steps:
            return steps
    return []


def plan_escape(state: dict, context: ActionContext, at: float) -> list[dict] | None:
    """A staircase out when Mimo is trapped, its steps tagged "escape".

    [] when Mimo is not trapped, tried to escape less than a minute ago, or has no way out.
    None when the trap check needs a search and none is left this tick.
    """
    brain = ensure_brain(state)
    if not walks_failed_twice(state, at, context.clock_at(at)["time_scale"]):
        return []
    if brain["escaped_at"] is not None and at - brain["escaped_at"] < ESCAPE_RETRY:
        return []
    here, seed = as_cell(state["position"]), state["world_seed"]
    if on_surface(here, seed):
        return []
    if not take_search(context):
        return None
    homes = {cell_of(place) for place in in_tick(state, context, at).places if place["kind"] == "home"}
    if way_out(context.grid, here, seed, homes):
        return []
    steps = escape_plan(context.grid, here, state["inventory"], seed)
    if not steps:
        return []
    brain.update(escaped_at=at, replans=0, planned_at=at)
    context.events.append((at, "trapped", f"{state['name']} is stuck in a pit and starts digging out."))
    return [{**step, "purpose": "escape"} for step in steps]
