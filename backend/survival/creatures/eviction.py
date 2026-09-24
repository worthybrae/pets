"""Creatures out of what Mimo built (L2).

Creatures never step into a cell something Mimo built claims (creatures.moves.steps),
but one can be standing in one already: a rabbit that wandered onto the site before the walls
went up. When a shelter's door goes in (building.note_building), every creature inside the
shelter's claimed cells is put out just beyond the cell in front of the door, so the shelter is
Mimo's alone from then on; with nowhere to stand out there it is removed.
"""

from __future__ import annotations

from backend.survival.blueprints import Blueprint
from backend.survival.creatures.table import cell_of, dead
from backend.survival.grid import Cell, Grid

EVICT_REACH = 8.0  # blocks from the shelter's home cell that its claimed cells lie within
OUT_STEPS = 3  # cells straight out past the front cell where a creature may be put


def outside(grid: Grid, blueprint: Blueprint) -> Cell | None:
    """The first cell straight out past the cell in front of the door where a creature can stand."""
    door, front = blueprint.one("door"), blueprint.front
    if door is None or front is None:
        return None
    dx, dz = front[0] - door[0], front[2] - door[2]
    for step in range(1, OUT_STEPS + 1):
        x, z = front[0] + dx * step, front[2] + dz * step
        for y in range(front[1] + 2, front[1] - 3, -1):
            cell = (x, y, z)
            if grid.standable(cell) and not grid.swimming(cell) and not grid.claimed(cell):
                return cell
    return None


def evict(grid: Grid, blueprint: Blueprint) -> list[dict]:
    """Put every living creature standing in a cell the shelter claims outside it. Returns them."""
    herd = grid.herd
    if herd is None:
        return []
    ax, _, az = blueprint.anchor
    out = outside(grid, blueprint)
    moved = []
    for creature in herd.near(ax, az, EVICT_REACH):
        if dead(creature) or not grid.claimed(cell_of(creature)):
            continue
        if out is None:
            herd.remove(creature["id"])
            continue
        creature["x"], creature["y"], creature["z"] = map(float, out)
        creature["state"].update(path=None, pose="idle", home=list(out))
        herd.save(creature)
        moved.append(creature)
    return moved
