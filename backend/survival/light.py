"""Light levels (spec L2, "Light levels"): what keeps the dark creatures away.

A cell's light is the brighter of its sky light and its block light, from 0 (pitch dark) to 15.
- Sky light is 15 by day (dawn, day and dusk) and 4 at night for a cell open to the sky, and 0
  for a covered one. A cell is open to the sky when nothing solid stands in the column over it
  up to SKY_SCAN cells above the natural ground (leaves let the sky through): a cave, a tunnel
  and the inside of a roofed shelter are covered, a pit Mimo dug is not (`sky_open`).
- Block light comes from placed torches (14), lanterns (15), campfires (13) and furnaces (13) and
  fades by one level per block of Manhattan distance, walls or not. It is worked out on demand
  from the light blocks near a spot, never stored (`Lights`).
Hostile creatures spawn only where the light is 7 or less (DARK), so torches around home keep the
yard safe; a kind that burns does so under the open sky by day (backend.survival.creatures).
"""

from __future__ import annotations

from backend.services.blocks import is_solid
from backend.services.worldgen import terrain_height
from backend.survival.grid import Cell, Grid

SKY_DAY = 15
SKY_NIGHT = 4
DARK = 7  # hostiles spawn only where the light is this or less
BLOCK_LIGHT = {"torch": 14, "lantern": 15, "campfire": 13, "furnace": 13}
LIGHT_REACH = max(BLOCK_LIGHT.values())  # the farthest any block light carries
SKY_SCAN = 8  # cells over the natural ground (or the cell, when it is higher) that can cover a cell
SEE_THROUGH = ("leaves",)


def sky_open(grid: Grid, seed: str, cell: Cell) -> bool:
    """Nothing solid but leaves over the cell, up to SKY_SCAN cells above the natural ground."""
    x, y, z = cell
    top = max(y, terrain_height(x, z, seed)) + SKY_SCAN
    for above in range(y + 1, top + 1):
        material = grid.material(x, above, z)
        if is_solid(material) and material not in SEE_THROUGH:
            return False
    return True


def sky_light(grid: Grid, seed: str, cell: Cell, night: bool) -> int:
    if not sky_open(grid, seed, cell):
        return 0
    return SKY_NIGHT if night else SKY_DAY


class Lights:
    """The light blocks placed within `reach` blocks of a spot (plus how far light carries), looked
    up once, so the block light of every cell near the spot costs no further reads."""

    def __init__(self, grid: Grid, center: Cell, reach: float):
        x, _, z = center
        self.sources = [(cell, BLOCK_LIGHT[material])
                        for cell, material in grid.placed_cells(x, z, reach + LIGHT_REACH, tuple(BLOCK_LIGHT))]

    def at(self, cell: Cell) -> int:
        """The block light at `cell`: the brightest source less its Manhattan distance, at least 0."""
        x, y, z = cell
        return max([level - abs(x - sx) - abs(y - sy) - abs(z - sz) for (sx, sy, sz), level in self.sources] + [0])


def light_at(grid: Grid, seed: str, cell: Cell, night: bool, lights: Lights | None = None) -> int:
    """The light level of `cell`: the brighter of sky light and block light."""
    lights = lights if lights is not None else Lights(grid, cell, 0)
    return max(sky_light(grid, seed, cell, night), lights.at(cell))


def dark(grid: Grid, seed: str, cell: Cell, night: bool, lights: Lights | None = None) -> bool:
    """Dark enough for hostile creatures to spawn: light 7 or less."""
    return light_at(grid, seed, cell, night, lights) <= DARK
