"""Light levels (spec L2, "Light levels"): what keeps the dark creatures away.

A cell's light is the brighter of its sky light and its block light, from 0 (pitch dark) to 15.
- Sky light is 15 by day (dawn, day and dusk) and 4 at night for a cell open to the sky, and 0
  for a covered one. A cell is open to the sky when nothing solid stands in the column over it
  up to SKY_SCAN cells above the natural ground (any leaves let the sky through: blocks.is_canopy;
  L3: SKY_SCAN clears the highest tree or rock the generator stands on a column): a cave, a tunnel
  and the inside of a roofed shelter are covered, a pit Mimo dug is not (`sky_open`).
- Block light comes from placed torches (14), lanterns (15), campfires (13) and furnaces (13) and
  fades by one level per block of Manhattan distance, walls or not. It is worked out on demand
  from the light blocks near a spot, never stored (`Lights`).
Hostile creatures spawn only where the light is 7 or less (DARK), so torches around home keep the
yard safe; a kind that burns does so under the open sky by day (backend.survival.creatures).
"""

from __future__ import annotations

from backend.services.blocks import CANOPY, is_solid
from backend.services.worldgen import FEATURE_TOP, LAVA_LEVEL, lava_in_chunk, terrain_height
from backend.survival.grid import Cell, Grid

SKY_DAY = 15
SKY_NIGHT = 4
DARK = 7  # hostiles spawn only where the light is this or less
BLOCK_LIGHT = {"torch": 14, "lantern": 15, "campfire": 13, "furnace": 13, "candle": 12}  # Making: candles
LIGHT_REACH = max(BLOCK_LIGHT.values())  # the farthest any block light carries
# Cells over the natural ground (or the cell, when it is higher) that can cover a cell: 8, and in any
# case more than the highest tree or rock the generator makes (L3).
SKY_SCAN = max(8, FEATURE_TOP + 1)
SEE_THROUGH = CANOPY  # L3: every kind of leaves, by the registry's `canopy`
LAVA_LIGHT = 15  # L3: lava the generator made lights the cave round it
# Fix round 2: farther lava than this (Manhattan, from LAVA_LEVEL) could not lift a cell past DARK
# regardless, so the dark verdict (darkness.spots, via Lights.dark) need never look past it, unlike
# an exact light level (Lights.at), which still wants the full LAVA_LIGHT reach.
DARK_LAVA_REACH = LAVA_LIGHT - DARK - 1


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

    def __init__(self, grid: Grid, center: Cell, reach: float, seed: str | None = None):
        x, _, z = center
        self.grid, self.seed = grid, seed  # L3: with the seed, lava the generator made lights too
        self.sources = [(cell, BLOCK_LIGHT[material])
                        for cell, material in grid.placed_cells(x, z, reach + LIGHT_REACH, tuple(BLOCK_LIGHT))]

    def at(self, cell: Cell) -> int:
        """The exact block light at `cell`: the brightest source less its Manhattan distance, at
        least 0, folding in lava the generator made when there is a seed. Fix round 2: this used to
        skip the lava scan when it could not change whether the cell reads as dark, which was a
        correct shortcut for the one caller that only ever asked that (darkness.spots) but made
        `at` itself report a wrong exact number near lava at low light. That caller now has its own
        `dark`, which keeps the shortcut (narrower still); `at` stays exact for every other use."""
        x, y, z = cell
        level = max([level - abs(x - sx) - abs(y - sy) - abs(z - sz) for (sx, sy, sz), level in self.sources] + [0])
        return max(level, lava_light(self.grid, self.seed, cell)) if self.seed is not None else level

    def dark(self, cell: Cell) -> bool:
        """L3, fix round 2: whether `cell`'s block light (placed lights and lava) is DARK or under
        -- all darkness.spots (the only caller) asks of it. Placed lights are exact and already
        gathered (`self.sources`); lava uses `lava_dark`'s narrower-than-`lava_light` reach, since
        lava farther than that could not push this cell past DARK regardless of the exact number."""
        x, y, z = cell
        level = max([level - abs(x - sx) - abs(y - sy) - abs(z - sz) for (sx, sy, sz), level in self.sources] + [0])
        if level > DARK:
            return False
        return self.seed is None or not lava_dark(self.grid, self.seed, cell)


def lava_light(grid: Grid, seed: str, cell: Cell) -> int:
    """L3: the light at `cell` from lava the generator made (worldgen.lava_in_chunk) that is still
    there, LAVA_LIGHT less its Manhattan distance, at least 0. Lava lies only at LAVA_LEVEL, so a cell
    LAVA_LIGHT or more above it costs nothing, and the chunks are generated once."""
    x, y, z = cell
    reach = LAVA_LIGHT - abs(y - LAVA_LEVEL)
    best = 0
    if reach <= 0:
        return best
    for cx in range((x - reach) // 16, (x + reach) // 16 + 1):
        for cz in range((z - reach) // 16, (z + reach) // 16 + 1):
            for lx, ly, lz in lava_in_chunk(cx, cz, seed):
                level = LAVA_LIGHT - abs(x - lx) - abs(y - ly) - abs(z - lz)
                if level > best and grid.material(lx, ly, lz) == "lava":
                    best = level
    return best


def lava_dark(grid: Grid, seed: str, cell: Cell) -> bool:
    """L3, fix round 2: whether lava the generator made (still there) lifts `cell`'s light past
    DARK -- the only thing `Lights.dark` (darkness.spots' only caller) needs -- without working
    out the exact level `lava_light` does. Lava farther than DARK_LAVA_REACH (Manhattan, from
    LAVA_LEVEL) could not push a cell past DARK regardless, so this touches far fewer chunks on a
    cold cache than `lava_light`'s full LAVA_LIGHT reach, and it stops at the first lava cell that
    clears DARK instead of finding the brightest."""
    x, y, z = cell
    reach = DARK_LAVA_REACH - abs(y - LAVA_LEVEL)
    if reach < 0:
        return False
    for cx in range((x - reach) // 16, (x + reach) // 16 + 1):
        for cz in range((z - reach) // 16, (z + reach) // 16 + 1):
            for lx, ly, lz in lava_in_chunk(cx, cz, seed):
                level = LAVA_LIGHT - abs(x - lx) - abs(y - ly) - abs(z - lz)
                if level > DARK and grid.material(lx, ly, lz) == "lava":
                    return True
    return False


def light_at(grid: Grid, seed: str, cell: Cell, night: bool, lights: Lights | None = None) -> int:
    """The light level of `cell`: the brighter of sky light and block light."""
    lights = lights if lights is not None else Lights(grid, cell, 0, seed)
    return max(sky_light(grid, seed, cell, night), lights.at(cell))


def dark(grid: Grid, seed: str, cell: Cell, night: bool, lights: Lights | None = None) -> bool:
    """Dark enough for hostile creatures to spawn: light 7 or less."""
    return light_at(grid, seed, cell, night, lights) <= DARK
