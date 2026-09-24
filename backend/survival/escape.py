"""Trapped: a staircase out of a pit Mimo cannot walk out of.

Routes can drop 3 blocks but climb only 1, so Mimo can walk into a pit it cannot leave. When a
step fails and at least two walks of the current purpose have failed with no path since it was
chosen (walks that got partway in between do not matter), the brain floods Mimo's moves from
where it stands (one search from the tick's budget): if fewer than 256 cells are reachable, Mimo
is trapped. The way out is a staircase up, one block up per step: mine the block over Mimo's head
and the stair cell when they are solid, and place a carried block where a stair has nothing to
stand on (mined dirt and stone go into the stock too). It tries the four directions and takes the
first staircase that brings Mimo above the natural surface within 24 stairs, at most once per 60
real seconds. There is no jump step, so a narrow shaft in rock Mimo cannot mine, with no blocks
to place, stays a trap.
"""

from __future__ import annotations

from backend.services.blocks import hardness, is_replaceable, is_solid
from backend.services.crafting import BLOCKS, can_harvest
from backend.services.worldgen import terrain_height
from backend.survival.actions import ActionContext, take_search
from backend.survival.grid import Cell, Grid
from backend.survival.pathing import moves
from backend.survival.purposes import walk_to
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain

TRAPPED_LIMIT = 256
MAX_STAIRS = 24
ESCAPE_RETRY = 60.0
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
FLUIDS = ("water", "lava")
# Blocks Mimo will place to stand on, cheapest first.
PLACEABLE = ("dirt", "cobblestone", "sand", "gravel", "clay", "planks", "birch_planks", "spruce_planks", "stone_bricks",
             "oak_log", "birch_log", "spruce_log")


def walks_failed_twice(state: dict) -> bool:
    """At least two walks of the current purpose failed with no path since it was chosen."""
    brain = ensure_brain(state)
    since = brain["chosen_at"] if brain["chosen_at"] is not None else float("-inf")
    failed = [entry for entry in state["recent_actions"]
              if entry.get("kind") == "walk" and entry.get("result") == "failed" and entry.get("code") == "no_path"
              and entry.get("purpose") == brain["purpose"] and entry.get("ended_at", since) >= since]
    return len(failed) >= 2


def reachable_count(grid: Grid, start: Cell, limit: int) -> int:
    """How many cells Mimo can walk to from `start` (itself included), counting up to `limit`."""
    seen, frontier = {start}, [start]
    while frontier and len(seen) < limit:
        for step in moves(grid, frontier.pop()):
            if step not in seen:
                seen.add(step)
                frontier.append(step)
    return min(len(seen), limit)


def look(grid: Grid, changed: dict[Cell, str], cell: Cell) -> str:
    return changed.get(cell) or grid.material(*cell)


def open_up(grid: Grid, changed: dict[Cell, str], cell: Cell, stock: dict, steps: list[dict]) -> bool:
    """Make `cell` open, mining it if it is solid. False for fluids and blocks Mimo cannot mine."""
    material = look(grid, changed, cell)
    if material in FLUIDS:
        return False
    if not is_solid(material):
        return True
    if hardness(material) is None or not can_harvest(material, stock):
        return False
    steps.append({"kind": "mine", "target": list(cell)})
    changed[cell] = "air"
    drop = BLOCKS.get(material, {}).get("drop")
    if drop:
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
        support = (stair[0], stair[1] - 1, stair[2])
        if not is_solid(look(grid, changed, support)):
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
    None when the flood fill needs a path search and none is left this tick.
    """
    brain = ensure_brain(state)
    if not walks_failed_twice(state):
        return []
    if brain["escaped_at"] is not None and at - brain["escaped_at"] < ESCAPE_RETRY:
        return []
    if not take_search(context):
        return None
    here = as_cell(state["position"])
    if reachable_count(context.grid, here, TRAPPED_LIMIT) >= TRAPPED_LIMIT:
        return []
    steps = escape_plan(context.grid, here, state["inventory"], state["world_seed"])
    if not steps:
        return []
    brain.update(escaped_at=at, replans=0, planned_at=at)
    context.events.append((at, "trapped", f"{state['name']} is stuck in a pit and starts digging out."))
    return [{**step, "purpose": "escape"} for step in steps]
