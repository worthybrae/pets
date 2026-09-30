"""W2: rain puts out a campfire under the open sky ("Weather" of the Wild World spec).

While it rains (a thunderstorm too: sky.RAINY), every campfire within DOUSE_REACH blocks of Mimo that stands under
the open sky (light.sky_open) goes out at the start of each step (`douse`, a sky effect): it becomes
`campfire_out`, which gives no light and no warmth ("The rain put out Pip's campfire.", a "fire_out" event, and
DOUSED hears of it). The `relight` step (RELIGHT_SECONDS, 1 stick, within reach) lights a doused campfire again;
cook relights one that stands within reach before it puts down another. A hearth never goes out. A doused
campfire still stands for the one a shelter's design puts beside its door (structures.STANDS_IN), so the
furnishing never tries to put another in its cell.

`wild:rain` ("Rain puts out a fire under the open sky, so keep your fire under a roof."): a pet that knows it
puts its fire in a spot with a roof (a solid block, not leaves, within ROOF_REACH above) when one is in reach
(`roofed_first`, for cook's campfire and the warm_up reflex's). A gentle pet knows it from the start.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from backend.services.blocks import CANOPY, is_solid
from backend.services.crafting import take_items
from backend.survival import sky
from backend.survival.grid import Cell, Grid
from backend.survival.light import sky_open
from backend.survival.once import log_once
from backend.survival.steps import StepFailed, StepKind, as_cell, as_point, in_reach, register_step
from backend.survival.structures import STANDS_IN
from backend.survival.wild import unlocked

if TYPE_CHECKING:
    from backend.survival.situation import Situation

logger = logging.getLogger(__name__)

DOUSE_REACH = 64.0
DOUSE_MARGIN = 16.0  # blocks Mimo may walk from where the campfires were looked up before they are looked up again
CAMPFIRES = "rain: campfires"  # their key in the tick's ActionContext.memo
RELIGHT_SECONDS = 1.0
ROOF_REACH = 4
DOUSED_BLOCK = "campfire_out"
# W2: functions (state, context, cell, at) run when the rain puts one of Mimo's campfires out (backend.survival
# .sky_wild: a knock and a wonder). One that crashes is logged once and passed over.
DOUSED: list = []


def roofed(grid: Grid, cell: Cell) -> bool:
    """A solid block that is not leaves within ROOF_REACH above the cell."""
    x, y, z = cell
    return any(is_solid(material) and material not in CANOPY
               for material in (grid.material(x, y + dy, z) for dy in range(1, ROOF_REACH + 1)))


def roofed_first(s: Situation, spots: list[tuple[Cell, bool]]) -> list[tuple[Cell, bool]]:
    """Station spots with the roofed ones first, for a pet that knows `wild:rain`; as they are otherwise."""
    if not unlocked(s, "rain"):
        return spots
    return sorted(spots, key=lambda spot: not roofed(s.grid, spot[0]))


def campfire_rows(db, x: int, z: int, reach: float) -> set[Cell]:
    """The campfires in the world's blocks within `reach` blocks of (x, z): one query."""
    box = math.ceil(reach)
    rows = db.execute("SELECT x, y, z FROM mimo_blocks WHERE material='campfire' AND x BETWEEN ? AND ? "
                      "AND z BETWEEN ? AND ?", (x - box, x + box, z - box, z + box)).fetchall()
    return {(row[0], row[1], row[2]) for row in rows if math.hypot(row[0] - x, row[2] - z) <= reach}


def campfires_near(context, x: int, z: int) -> list[Cell]:
    """The campfires placed within DOUSE_REACH blocks, in cell order. Without a database, the grid's own edits.
    With one, a query of the world's blocks (loading every chunk that far into the grid would cost the tick each
    step), made once a transaction (fix round 4: it was once a step, a fire's short steps sixty times) and kept in
    the tick's ActionContext.memo: it reaches DOUSE_MARGIN blocks farther, is made again once Mimo has walked
    farther than that from where it was made, and gains every campfire put since. Every one is put through the
    grid (cook's, a camp's, warm_up's, a relit one), in Mimo's actions just before the sky's step, so it is among
    the grid's changes here, before renewal takes them."""
    grid = context.grid
    db = getattr(context, "db", None)
    if db is None:
        return [cell for cell, _ in grid.placed_cells(x, z, DOUSE_REACH, ("campfire",))]
    memo = getattr(context, "memo", None)
    kept = None if memo is None else memo.get(CAMPFIRES)
    if kept is None or math.hypot(x - kept[0], z - kept[1]) > DOUSE_MARGIN:
        kept = (x, z, campfire_rows(db, x, z, DOUSE_REACH + DOUSE_MARGIN))
        if memo is not None:
            memo[CAMPFIRES] = kept
    kept[2].update(cell for cell, _, after in grid.changes if after == "campfire")
    return sorted(cell for cell in kept[2] if math.hypot(cell[0] - x, cell[2] - z) <= DOUSE_REACH)


def douse(state: dict, context, at: float) -> None:
    """sky.EFFECTS: while it rains, the campfires near Mimo under the open sky go out."""
    if not sky.raining(state):
        memo = getattr(context, "memo", None)
        if memo is not None:
            memo.pop(CAMPFIRES, None)  # the next spell of rain looks them up afresh
        return
    grid, position = context.grid, state["position"]
    seed = state.get("world_seed", "0")
    for cell in campfires_near(context, math.floor(position["x"]), math.floor(position["z"])):
        if grid.material(*cell) != "campfire" or not sky_open(grid, seed, cell):
            continue
        grid.put(*cell, DOUSED_BLOCK)
        context.events.append((at, "fire_out", f"The rain put out {state['name']}'s campfire."))
        state["last_thought"] = "Oh no, the rain put my fire out!"
        for hears in DOUSED:
            try:
                hears(state, context, cell, at)
            except Exception as error:
                log_once(logger, "doused", error)


def start_relight(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = as_cell(spec["target"])
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    if grid.material(*target) != DOUSED_BLOCK:
        raise StepFailed("no doused campfire there", "gone")
    if state["inventory"].get("sticks", 0) < 1:
        raise StepFailed("no stick to light it with", "missing_item")
    return {"kind": "relight", "started_at": at, "ends_at": round(at + RELIGHT_SECONDS / scale, 3),
            "target": as_point(target)}


def finish_relight(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = as_cell(step["target"])
    if grid.material(*target) != DOUSED_BLOCK:
        raise StepFailed("the doused campfire is gone", "gone")
    state["inventory"] = take_items(state["inventory"], {"sticks": 1})
    grid.put(*target, "campfire")
    state["last_thought"] = "There, the fire's going again."
    return None


def relight_steps(s: Situation, reach: float) -> list[dict]:
    """The step that relights a doused campfire in reach of Mimo (steps.in_reach, not one out in the rain), or [].
    `reach` only bounds the look for doused campfires (Grid.placed_cells' broad phase): the step is planned only for
    one in reach from where Mimo stands, however large `reach` is."""
    if s.count("sticks") < 1:
        return []
    x, _, z = s.here
    rainy = sky.raining(s.state)
    for cell, _ in sorted(s.grid.placed_cells(x, z, reach, (DOUSED_BLOCK,)), key=lambda found: s.distance(found[0])):
        if in_reach(s.here, cell) and not (rainy and sky_open(s.grid, s.seed, cell)):
            return [{"kind": "relight", "target": list(cell)}]
    return []


register_step(StepKind("relight", start_relight, finish_relight, "building", working=True, cell_field="target"))
STANDS_IN["campfire"] = (*STANDS_IN.get("campfire", ("campfire",)), DOUSED_BLOCK)
sky.EFFECTS.append(douse)
