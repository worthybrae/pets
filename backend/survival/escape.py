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
stand on (mined dirt and stone go into the stock too, while they fit in Mimo's arms: L4b final fix
wave, follow-up 2 -- with full arms the dug block is left behind, carrying's rule, and a staircase
that counted on placing it failed "no dirt to place" twice, leaving a pet in a cave for a game day
until a skitter caught it). Where they fit (L3), the two cells over each
stair and the three beside it (left of the heading, over solid ground) open too, so the way out is
2 wide and 3 tall like Mimo's own stairs; a cell that cannot be mined there is left, the same rule
as work.cut: never something Mimo built or tends (or the cell above it), and never an ore or a
surface log, left standing for Mimo to gather later (fix round 1). A cell that is open already
needs no mining, so it is used whether or not it is claimed: Mimo trapped in its shelter's room or
passage walks out through them (L3 final fix wave). The cell over a stair is the
next stair's headroom and is kept; the other widening cells break into rubble Mimo leaves behind.
It tries the four directions and takes the
first staircase that brings Mimo above the natural surface within 24 stairs, at most once per
ESCAPE_RETRY game seconds (W2, the controller's ruling on the W2 dry run: it was 60 server seconds, a
game day at MIMO_TIME_SCALE 60, so a pet in its own staircase at dusk slept the night in it and dug out
after dawn; at 1x nothing changes). There is no jump step, so a narrow shaft in rock Mimo cannot mine, with no blocks
to place, stays a trap.

L4b final fix wave, C1: a cell above the natural surface is free only when Mimo can walk from it to
more than POCKET cells (`free`). Worldgen's decorations (a sand dune, a granite boulder) leave 1x1
pits whose floor lies above the natural surface; a walk dropped a pet into one, every cell above
the surface counted as free, so no staircase was dug and it starved there (seed 21, fake Jev, day
9). Such a pit is a trap now: `plan_escape` checks it (the small flood needs no search from the
tick's budget), `way_out` looks past it, and a staircase ends only on a stair that is free once its
own digging is done (`Dug`).

Its steps carry `keep: "escape"`, so a new choice landing mid-escape (apply_choice's kept_steps)
keeps digging out instead of cutting the escape short (follow-up fix, the minors). Unlike a
portable station's mine-back `keep: True`, that only rides out a new choice: a step that fails on
its own still ends the escape and is charged to last_failure like any other step (actions.fail;
follow-up 2, item 3).
"""

from __future__ import annotations

from collections import deque

from backend.services.blocks import hardness, is_replaceable, is_solid
from backend.services.crafting import BLOCKS, LOGS, can_harvest
from backend.services.worldgen import terrain_height
from backend.survival.actions import ActionContext, take_search
from backend.survival.carrying import CARRY_STACKS, room_for
from backend.survival.grid import FLUIDS, Cell, Grid, supports
from backend.survival.home import home_cell
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
ESCAPE_RETRY = 60.0  # game seconds between two escapes (W2: they were server seconds)
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
# L4b final fix wave, C1: a cell above the natural surface from which Mimo can walk to no more than
# this many cells (itself included) is a pit, not open ground. The seed-21 pit held 1.
POCKET = 16
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


def roomy(grid: Grid | Dug, start: Cell, limit: int = POCKET) -> bool:
    """Mimo can walk from `start` to more than `limit` cells (itself included): not a pit (C1)."""
    seen, frontier = {start}, deque([start])
    while frontier:
        for step in moves(grid, frontier.popleft()):
            if step not in seen:
                seen.add(step)
                if len(seen) > limit:
                    return True
                frontier.append(step)
    return False


def free(grid: Grid | Dug, cell: Cell, seed: str) -> bool:
    """Open ground: above the natural surface, and not a pit there (`roomy`, C1)."""
    return on_surface(cell, seed) and roomy(grid, cell)


def way_out(grid: Grid, start: Cell, seed: str, homes: frozenset[Cell] | set[Cell] = frozenset(),
            limit: int = SURFACE_SEARCH) -> bool:
    """Whether Mimo can walk from `start` to open ground (`free`: above the natural surface and not
    a pit there), or to one of `homes`, looking at no more than `limit` cells, nearest first. False
    means trapped."""
    seen, frontier = {start}, deque([start])
    while frontier:
        cell = frontier.popleft()
        if cell in homes or free(grid, cell, seed):
            return True
        for step in moves(grid, cell):
            if step not in seen and len(seen) < limit:
                seen.add(step)
                frontier.append(step)
    return False


def look(grid: Grid, changed: dict[Cell, str], cell: Cell) -> str:
    return changed.get(cell) or grid.material(*cell)


class Dug:
    """The grid as a staircase plan would leave it: the cells it mines or places (`changed`) over
    the rest, with the few Grid rules `pathing.moves` reads (C1: a stair is checked for a pit
    with its own digging done)."""

    def __init__(self, grid: Grid, changed: dict[Cell, str]):
        self.grid, self.changed = grid, changed

    def material(self, x: int, y: int, z: int) -> str:
        return look(self.grid, self.changed, (x, y, z))

    def passable(self, cell: Cell) -> bool:
        material = self.material(*cell)
        return material not in FLUIDS and not is_solid(material)

    def supported(self, cell: Cell) -> bool:
        x, y, z = cell
        return supports(self.material(x, y - 1, z), self.material(x, y, z))

    def standable(self, cell: Cell) -> bool:
        return self.passable(cell) and self.supported(cell)


def open_up(grid: Grid, changed: dict[Cell, str], cell: Cell, stock: dict, steps: list[dict],
            rubble: bool = False) -> bool:
    """Make `cell` open, mining it if it is solid. False for fluids, and for a solid block Mimo built
    or tends (or under one, the same rule as work.cut) or cannot mine. An open cell needs no mining,
    so it is used even when claimed: the check once came first and blocked the shelter's own room
    and passage, the cells Mimo must walk through (L3 final fix wave). A `rubble` cell
    is also left standing when it holds an ore or a surface log (fix round 1, items 3 and the
    minors): those are worth collecting on purpose, not losing to a widening cell with no drop.
    A `rubble` cell that is mined is left behind, so it adds nothing to the stock, and so is a mined
    block that does not fit in Mimo's arms (carrying.room_for; follow-up 2)."""
    x, y, z = cell
    material = look(grid, changed, cell)
    if material in FLUIDS:
        return False
    if not is_solid(material):
        return True  # nothing to mine: an open cell is used even when claimed (L3 final fix wave)
    if reserved(grid, cell) or reserved(grid, (x, y + 1, z)):
        return False
    if hardness(material) is None or not can_harvest(material, stock) or grid.thick_ice(cell):  # W2: a lake's ice
        return False
    if rubble and (material in ORES or material in LOGS):
        return False
    steps.append({"kind": "mine", "target": list(cell), **({"rubble": True} if rubble else {})})
    changed[cell] = "air"
    drop = BLOCKS.get(material, {}).get("drop")
    if drop and not rubble and room_for(stock, drop, CARRY_STACKS) >= 1:
        stock[drop] = stock.get(drop, 0) + 1
    return True


def staircase(grid: Grid, here: Cell, heading: tuple[int, int], inventory: dict, seed: str) -> list[dict] | None:
    """Stairs up from `here` toward `heading` until Mimo stands on open ground (`free` once the
    stairs are dug: above the natural surface, and not a pit there, C1), or None."""
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
        if free(Dug(grid, changed), stair, seed):
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
    None when the trap check needs a search and none is left this tick. On open ground (`free`,
    whose small flood needs no search) Mimo is not trapped; in a pit above the surface it may be (C1).
    """
    brain = ensure_brain(state)
    scale = context.clock_at(at)["time_scale"]
    if not walks_failed_twice(state, at, scale):
        return []
    if brain["escaped_at"] is not None and (at - brain["escaped_at"]) * scale < ESCAPE_RETRY:
        return []
    here, seed = as_cell(state["position"]), state["world_seed"]
    if free(context.grid, here, seed):
        return []
    if not take_search(context):
        return None
    home = home_cell(in_tick(state, context, at))  # L4a final fix wave, I1: the one home lookup
    homes = {home} if home is not None else set()
    if way_out(context.grid, here, seed, homes):
        return []
    steps = escape_plan(context.grid, here, state["inventory"], seed)
    if not steps:
        return []
    brain.update(escaped_at=at, replans=0, planned_at=at)
    context.events.append((at, "trapped", f"{state['name']} is stuck in a pit and starts digging out."))
    # `keep: "escape"`, so apply_choice and the reflex it resumes into (kept_steps) never cut an
    # escape short the moment the next choice lands (follow-up fix, the minors: a new choice 9
    # game seconds into a 41-step escape dropped the rest of it, and the pocket took 24 more
    # purpose changes and a second escape to get out of). That protection is only against a new
    # choice: unlike a portable station's mine-back `keep: True`, a failure of the escape's own
    # step is still charged to last_failure and drops the rest of the escape (actions.fail;
    # follow-up 2, item 3), the same as any plan that turns out wrong.
    return [{**step, "purpose": "escape", "keep": "escape"} for step in steps]
