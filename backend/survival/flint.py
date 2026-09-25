"""gather_flint: dig gravel for flint, the tip of every arrow (L3; L2's flint is one mined gravel in 8).

Mimo wants flint while it has a bow (or the 3 string one takes), carries fewer than FLINT_WANTED
flint and fewer arrows than make_gear keeps (backend.survival.creatures.gear), and (L4b) only once
it learned that gravel hides flint (backend.survival.journal). Gravel lines lake and
river beds, lies in patches on shores, in the taiga and on alpine scree, and on cave floors
(backend.services.worldgen). gather_flint digs the nearest gravel Mimo can stand by: natural gravel
ground within 24 blocks with open air over it (never under water), and any gravel within reach of
where it stands (a cave floor, or a seam its passage cut), nearest first, up to 8 a batch and 3
batches a choice, until a flint turns up. Gravel within 4 blocks of where a step just failed, and
what Mimo built or tends (structures.reserved), are left alone. It is day work in the work band: 45
plus a tenth of caution.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, surface_material, terrain_height
from backend.survival.creatures.gear import ARROWS_WANTED
from backend.survival.foraging import reach_steps
from backend.survival.grid import Cell
from backend.survival.purposes import Purpose, register
from backend.survival.senses import by_distance, near_failure
from backend.survival.situation import Situation
from backend.survival.steps import REACH
from backend.survival.structures import reserved

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

FLINT_WANTED = 2
GRAVEL_SIGHT = 24
GRAVEL_PER_BATCH = 8
FLINT_BATCHES = 3


def wants_flint(s: Situation) -> bool:
    """A bow (or the string for one), fewer than FLINT_WANTED flint and fewer arrows than wanted."""
    archer = s.count("bow") > 0 or s.count("string") >= 3
    return archer and s.count("flint") < FLINT_WANTED and s.count("arrow") < ARROWS_WANTED


def diggable(s: Situation, cell: Cell) -> bool:
    """Gravel that is still there, with open air over it (not water), nobody's floor that Mimo built
    or tends, and no failed step nearby."""
    x, y, z = cell
    over = s.grid.material(x, y + 1, z)
    return (s.grid.material(*cell) == "gravel" and s.grid.passable((x, y + 1, z)) and over != "water"
            and not reserved(s.grid, cell) and not near_failure(s.state, cell))


def gravel_near(s: Situation) -> list[Cell]:
    """Gravel Mimo can dig, nearest first (see the module docstring)."""
    def look() -> list[Cell]:
        x, y, z = s.here
        found = set()
        for gx in range(x - GRAVEL_SIGHT, x + GRAVEL_SIGHT + 1):
            for gz in range(z - GRAVEL_SIGHT, z + GRAVEL_SIGHT + 1):
                if math.hypot(gx - x, gz - z) > GRAVEL_SIGHT:
                    continue
                height = terrain_height(gx, gz, s.seed)
                if height >= SEA_LEVEL and surface_material(gx, gz, s.seed) == "gravel":
                    found.add((gx, height, gz))
        reach = int(REACH)
        found.update((x + dx, y + dy, z + dz) for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1)
                     for dz in range(-reach, reach + 1) if s.grid.material(x + dx, y + dy, z + dz) == "gravel")
        return [cell for cell in by_distance(found, s.here) if diggable(s, cell)]
    return s.sensed("gravel", look)


def flint_valid(s: Situation) -> bool:
    """L4b: only once Mimo learned that gravel hides flint (backend.survival.journal)."""
    return not s.night and "gravel" in s.lessons and wants_flint(s) and bool(gravel_near(s))


def plan_flint(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= FLINT_BATCHES or not wants_flint(s):
        return []
    cells = gravel_near(s)[:GRAVEL_PER_BATCH]
    return reach_steps(s, [(cell, [{"kind": "mine", "target": list(cell)}]) for cell in cells])


register(Purpose(
    "gather_flint", "dig gravel for flint", "Dig gravel nearby until a flint turns up, for arrows.",
    valid=flint_valid,
    facts=lambda s: f"{len(gravel_near(s))} gravel to dig within {GRAVEL_SIGHT} blocks; carrying {s.count('flint')} flint",
    score=lambda s: 45.0 + s.trait("caution") / 10, plan=plan_flint,
    thoughts=("A flint would tip my arrows.", "There's gravel over there. Flint hides in gravel.")))
