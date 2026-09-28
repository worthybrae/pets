"""Paths for a one-cell Mimo: 3D A* over cells.

Mimo moves to one of its 4 horizontal neighbors at a time: on the same level, one step up
when the cell above its head is free, or off a ledge down at most 3 cells; and (L3) straight up
or down a ladder. Nothing steps onto a fence (Grid.supported). Swimming happens
on the water surface (the cell below Mimo is water) and costs 3 times as much as walking.
A route never enters a cell that is itself water, so Mimo never plans to put its head under, nor (W2) a
burning cell or one beside it (Grid.hot).
A search expands at most 20,000 cells and stays within 96 blocks of the start on each
horizontal axis. Farther targets are reached in segments toward waypoints.
"""

from __future__ import annotations

import heapq
import math
from itertools import count
from typing import Callable, Iterator

from backend.survival.grid import LADDER, Cell, Grid

MAX_NODES = 20_000
MAX_RANGE = 96
MAX_DROP = 3
SWIM_COST = 3.0
WALK_SECONDS = 0.3
SWIM_SECONDS = 0.9
# A far target gets a waypoint this many blocks along the way, inside MAX_RANGE.
SEGMENT = 88
# A segment ends on any cell this close to its waypoint (horizontal Manhattan distance).
WAYPOINT_SLACK = 3
HORIZONTAL = ((1, 0), (-1, 0), (0, 1), (0, -1))


def moves(grid: Grid, cell: Cell) -> Iterator[Cell]:
    """Cells Mimo can reach from `cell` in one move. W2: never into or through a burning cell or one beside it
    (`grid.hot`, like lava; fix round 4: here, not in Grid.passable, so a fall or a landing still goes through)."""
    hot = getattr(grid, "hot", None)
    passable = grid.passable if not hot else (lambda at: at not in hot and grid.passable(at))
    x, y, z = cell
    headroom: bool | None = None
    for dx, dz in HORIZONTAL:
        level = (x + dx, y, z + dz)
        if passable(level):
            if grid.supported(level):
                yield level
                continue
            for drop in range(1, MAX_DROP + 1):
                lower = (level[0], y - drop, level[2])
                if not passable(lower):
                    break
                if grid.supported(lower):
                    yield lower
                    break
            continue
        if headroom is None:
            headroom = passable((x, y + 1, z))
        up = (level[0], y + 1, level[2])
        if headroom and passable(up) and grid.supported(up):
            yield up
    if grid.material(x, y, z) == LADDER and grid.material(x, y + 1, z) == LADDER and not (hot and (x, y + 1, z) in hot):
        yield x, y + 1, z  # L3: climb the ladder
    if grid.material(x, y - 1, z) == LADDER and not (hot and (x, y - 1, z) in hot):
        yield x, y - 1, z  # and down it


def move_cost(grid: Grid, cell: Cell) -> float:
    return SWIM_COST if grid.swimming(cell) else 1.0


def trace(came_from: dict[Cell, Cell | None], cell: Cell) -> list[Cell]:
    cells = []
    while came_from[cell] is not None:
        cells.append(cell)
        cell = came_from[cell]
    cells.reverse()
    return cells


def find_path(grid: Grid, start: Cell, is_goal: Callable[[Cell], bool], toward: Cell, slack: int = 0,
              max_nodes: int = MAX_NODES, max_range: int = MAX_RANGE) -> tuple[list[Cell], bool]:
    """A* from `start` to the cheapest cell where `is_goal` holds.

    The estimate is the horizontal Manhattan distance to `toward`, less `slack` (how far a goal
    cell may lie from `toward`), so it never overestimates. Ties go to the cell nearer the goal.
    Returns the cells after the start and whether a goal was reached. When the budget runs out
    first, the route leads to the explored cell with the lowest estimate ([] if that is the start).
    """

    def estimate(cell: Cell) -> int:
        return max(0, abs(cell[0] - toward[0]) + abs(cell[2] - toward[2]) - slack)

    order = count()
    frontier = [(estimate(start), estimate(start), next(order), 0.0, start)]
    came_from: dict[Cell, Cell | None] = {start: None}
    best_cost = {start: 0.0}
    nearest, nearest_estimate = start, estimate(start)
    expanded = 0
    while frontier and expanded < max_nodes:
        _, remaining, _, cost, cell = heapq.heappop(frontier)
        if cost > best_cost[cell]:
            continue
        if is_goal(cell):
            return trace(came_from, cell), True
        expanded += 1
        if remaining < nearest_estimate:
            nearest, nearest_estimate = cell, remaining
        for step in moves(grid, cell):
            if abs(step[0] - start[0]) > max_range or abs(step[2] - start[2]) > max_range:
                continue
            new_cost = cost + move_cost(grid, step)
            if new_cost < best_cost.get(step, math.inf):
                best_cost[step] = new_cost
                came_from[step] = cell
                guess = estimate(step)
                heapq.heappush(frontier, (new_cost + guess, guess, next(order), new_cost, step))
    return trace(came_from, nearest), False


def route(grid: Grid, start: Cell, target: Cell, reach: float = 0.0,
          max_nodes: int = MAX_NODES) -> tuple[list[Cell], bool]:
    """A route from `start` toward `target`, expanding at most `max_nodes` cells.

    With reach 0 the route ends on `target`; otherwise on any cell other than `target` within
    `reach` blocks of it. A target more than MAX_RANGE blocks away on either axis is approached
    one segment at a time: the route ends near a waypoint SEGMENT blocks along the way and
    `reached` is False. The caller walks the segment and asks again. A smaller `max_nodes` (L2: a
    fight step's own search, backend.survival.actions.FIGHT_STEP_NODES) ends sooner, with the
    route to the explored cell nearest the goal when it runs out first.
    """
    dx, dz = target[0] - start[0], target[2] - start[2]
    if max(abs(dx), abs(dz)) > MAX_RANGE:
        share = SEGMENT / max(abs(dx), abs(dz))
        waypoint = (start[0] + round(dx * share), start[1], start[2] + round(dz * share))
        cells, _ = find_path(grid, start,
                             lambda cell: abs(cell[0] - waypoint[0]) + abs(cell[2] - waypoint[2]) <= WAYPOINT_SLACK,
                             waypoint, slack=WAYPOINT_SLACK, max_nodes=max_nodes)
        return cells, False
    if reach <= 0:
        return find_path(grid, start, lambda cell: cell == target, target, max_nodes=max_nodes)
    return find_path(grid, start, lambda cell: cell != target and math.dist(cell, target) <= reach,
                     target, slack=math.ceil(reach * math.sqrt(2)), max_nodes=max_nodes)


def timed_path(grid: Grid, start: Cell, cells: list[Cell], started_at: float, scale: float = 1.0) -> list[dict]:
    """The start and each cell after it with the time Mimo gets there. Water-surface cells say so.
    `scale` (MIMO_ACTION_SCALE) makes every move that many times shorter."""
    at = started_at
    path = [{"x": start[0], "y": start[1], "z": start[2], "at": started_at}]
    for cell in cells:
        swim = grid.swimming(cell)
        at = round(at + (SWIM_SECONDS if swim else WALK_SECONDS) / scale, 3)
        entry = {"x": cell[0], "y": cell[1], "z": cell[2], "at": at}
        if swim:
            entry["swim"] = True
        path.append(entry)
    return path
