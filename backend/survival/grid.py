"""Block lookups for one tick of a survival world: saved edits over the natural world.

The pathfinder and the action system ask about thousands of cells in a tick. A Grid caches
natural blocks and loads saved edits one 16x16 chunk at a time. `put` records an edit and
passes it to the world's write_block, so viewers receive it through block sync. It also keeps
each change until `take_changes` collects it, so renewal can react to what Mimo changed. Cells
that something Mimo built claims (backend.survival.structures) load the same way, chunk by chunk,
so planners that dig or till can leave them alone (`claimed`). A grid over a world database also
carries the world's creatures (`herd`, backend.survival.creatures.table.Herd), so steps and
planners reach them the way they reach blocks; a grid built from `natural` alone has none.
W2: the cells a fire burns in and their neighbours (`hot`, set by backend.survival.storms) are no way through for a
route (pathing.moves keeps out of them, like lava), yet they hold no one up: a fall or a landing goes on through
them (`passable` leaves them out; fix round 4). In winter (`frozen`, from state["sky"]: `overlay`) a natural water
cell at SEA_LEVEL that was never edited reads as ice, the surface of a lake, a river or a swamp pool: solid,
standable, walkable, and never mined (steps.start_mine), so no block is written; cave lakes lie lower and stay
water. A cell in `open_cells` (where Mimo stood or swam when the freeze came) stays water. For every other cell it
costs one integer compare. `edited` asks whether a cell was ever put, loading its chunk first, as `material` and
`claimed` do: a read of `edits` alone misses the chunks nothing has read yet.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Callable

from backend.services.block_table import write_block
from backend.services.blocks import is_plant, is_solid, is_tall
from backend.services.worldgen import SEA_LEVEL, block_at
from backend.survival.creatures.table import Herd

Cell = tuple[int, int, int]
MaterialAt = Callable[[int, int, int], str]
LoadEdits = Callable[[int, int], dict[Cell, str]]
LoadClaims = Callable[[int, int], set[Cell]]
WriteBlock = Callable[[int, int, int, str], None]
CHUNK = 16
FLUIDS = ("water", "lava")
FACES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
LADDER = "ladder"


def supports(below: str, here: str) -> bool:
    """Whether a cell with `below` beneath it and `here` in it holds up whoever stands there: water
    or a ladder below holds, so does a solid block below that is not tall (a fence, L3), and so does
    a ladder in the cell itself. The one rule `Grid.supported` and `reflexes.fall_depth` share."""
    if below in ("water", LADDER):
        return True
    if is_solid(below):
        return not is_tall(below)
    return here == LADDER


class Grid:
    """Materials by cell, with the rules Mimo's one-cell body needs.

    `natural(x, y, z)` gives the generated block. `load_edits(cx, cz)` returns the saved edits of
    one chunk and `write` stores a new edit. Tests build small worlds from `natural` alone.
    """

    def __init__(self, natural: MaterialAt, load_edits: LoadEdits | None = None, write: WriteBlock | None = None,
                 load_claims: LoadClaims | None = None):
        self._natural = natural
        self._load_edits = load_edits
        self._write = write
        self._load_claims = load_claims
        self._natural_cache: dict[Cell, str] = {}
        self._loaded_chunks: set[tuple[int, int]] = set()
        self.edits: dict[Cell, str] = {}
        self.changes: list[tuple[Cell, str, str]] = []
        self.claims: set[Cell] = set()
        self.herd: Herd | None = None
        self.hot: set[Cell] = set()  # W2: burning cells and their neighbours
        self.frozen = False  # W2: the lakes' surfaces are ice
        self.open_cells: set[Cell] = set()  # W2: water Mimo kept open where it was when the freeze came

    def _load(self, x: int, z: int) -> None:
        if self._load_edits is None:
            return
        chunk = (x // CHUNK, z // CHUNK)
        if chunk in self._loaded_chunks:
            return
        self._loaded_chunks.add(chunk)
        for cell, material in self._load_edits(*chunk).items():
            self.edits.setdefault(cell, material)
        if self._load_claims is not None:
            self.claims.update(self._load_claims(*chunk))

    def material(self, x: int, y: int, z: int) -> str:
        """The block at a cell by block_table.resolve_block's rule: an edit wins, and a natural
        plant whose cell below was edited (dug out or built on) is air."""
        self._load(x, z)
        edit = self.edits.get((x, y, z))
        if edit is not None:
            return edit
        natural = self._natural_cache.get((x, y, z))
        if natural is None:
            natural = self._natural(x, y, z)
            self._natural_cache[(x, y, z)] = natural
        if is_plant(natural) and (x, y - 1, z) in self.edits:
            return "air"
        if y == SEA_LEVEL and self.frozen and natural == "water" and (x, y, z) not in self.open_cells:
            return "ice"  # W2: a frozen lake (the overlay, never a block)
        return natural

    def overlay(self, sky: dict | None) -> None:
        """W2: the winter's ice from state["sky"] (`frozen`, `open_cells`), and the heat of the cells burning in the
        trees (`fires`: `hot`), so a grid made in a transaction keeps out of them before the storm's effect runs
        (carried N2 of W2's fourth task: a transaction's grid had no hot cells until then)."""
        sky = sky or {}
        self.frozen = bool(sky.get("frozen"))
        self.open_cells = {tuple(cell) for cell in sky.get("open_cells", ())}
        self.hot = hot_of(sky.get("fires", ()))

    def thick_ice(self, cell: Cell) -> bool:
        """W2: the winter's ice over a lake (the overlay, never a block): too thick to mine (steps.start_mine), so
        no plan digs it (W2's final review: a camp was dug in on a frozen pool). A taiga's own ice is a block, and
        mines."""
        return (self.frozen and cell[1] == SEA_LEVEL and self.material(*cell) == "ice"
                and self.natural_material(*cell) == "water")

    def natural_material(self, x: int, y: int, z: int) -> str:
        """The block worldgen put at the cell, before any edit."""
        natural = self._natural_cache.get((x, y, z))
        if natural is None:
            natural = self._natural(x, y, z)
            self._natural_cache[(x, y, z)] = natural
        return natural

    def put(self, x: int, y: int, z: int, material: str) -> None:
        before = self.material(x, y, z)
        self.edits[(x, y, z)] = material
        self.changes.append(((x, y, z), before, material))
        if self._write is not None:
            self._write(x, y, z, material)

    def take_changes(self) -> list[tuple[Cell, str, str]]:
        """(cell, before, after) for every put since the last call, oldest first."""
        changes, self.changes = self.changes, []
        return changes

    def solid(self, cell: Cell) -> bool:
        return is_solid(self.material(*cell))

    def claimed(self, cell: Cell) -> bool:
        """Part of something Mimo built: a planner that digs or tills leaves it alone."""
        self._load(cell[0], cell[2])
        return cell in self.claims

    def water(self, cell: Cell) -> bool:
        return self.material(*cell) == "water"

    def edited(self, cell: Cell) -> bool:
        """Something was put in the cell, saved or this tick. Its chunk's edits are loaded first (W2 fix round 4),
        so a cell in a chunk nothing has read yet is not taken for a natural one."""
        self._load(cell[0], cell[2])
        return cell in self.edits

    def passable(self, cell: Cell) -> bool:
        """Mimo's body fits in the cell: nothing solid, and no water or lava. A fire and the cells beside it
        (`hot`) fit it too: a fall goes on through them, and only a route keeps out (pathing.moves)."""
        material = self.material(*cell)
        return material not in FLUIDS and not is_solid(material)

    def supported(self, cell: Cell) -> bool:
        """Something holds Mimo up in this cell: the cell below is solid or water. L3: a fence below
        is too tall to stand on, and a ladder holds whoever is on it or on top of it."""
        x, y, z = cell
        return supports(self.material(x, y - 1, z), self.material(x, y, z))

    def standable(self, cell: Cell) -> bool:
        return self.passable(cell) and self.supported(cell)

    def swimming(self, cell: Cell) -> bool:
        """Mimo floats on the water surface here: its body fits and the cell below is water."""
        x, y, z = cell
        return self.passable(cell) and self.material(x, y - 1, z) == "water"

    def placed_cells(self, x: int, z: int, reach: float, materials: tuple[str, ...]) -> list[tuple[Cell, str]]:
        """Placed blocks of `materials` within `reach` blocks (horizontally) of (x, z), with their cells."""
        for cx in range(math.floor((x - reach) / CHUNK), math.floor((x + reach) / CHUNK) + 1):
            for cz in range(math.floor((z - reach) / CHUNK), math.floor((z + reach) / CHUNK) + 1):
                self._load(cx * CHUNK, cz * CHUNK)
        return [(cell, material) for cell, material in self.edits.items()
                if material in materials and math.hypot(cell[0] - x, cell[2] - z) <= reach]

    def placed_near(self, x: int, z: int, reach: float, materials: tuple[str, ...]) -> set[str]:
        """Which of `materials` have been placed within `reach` blocks (horizontally) of (x, z)."""
        return {material for _, material in self.placed_cells(x, z, reach, materials)}


def hot_of(fires) -> set[Cell]:
    """W2: the burning cells (state["sky"]["fires"]) and their face neighbours: paths keep out of them (Grid.hot)."""
    cells = set()
    for entry in fires:
        x, y, z = entry["x"], entry["y"], entry["z"]
        cells.add((x, y, z))
        cells.update((x + dx, y + dy, z + dz) for dx, dy, dz in FACES)
    return cells


def world_grid(db: sqlite3.Connection, seed: str, sky: dict | None = None) -> Grid:
    """A grid over one survival world's database, for the length of one transaction; W2: with state["sky"],
    frozen as the winter has it."""

    def load_edits(cx: int, cz: int) -> dict[Cell, str]:
        rows = db.execute("SELECT x,y,z,material FROM mimo_blocks WHERE x BETWEEN ? AND ? AND z BETWEEN ? AND ?",
                          (cx * CHUNK, cx * CHUNK + CHUNK - 1, cz * CHUNK, cz * CHUNK + CHUNK - 1)).fetchall()
        return {(row["x"], row["y"], row["z"]): row["material"] for row in rows}

    def write(x: int, y: int, z: int, material: str) -> None:
        write_block(db, x, y, z, material)

    def load_claims(cx: int, cz: int) -> set[Cell]:
        try:
            rows = db.execute("SELECT x,y,z FROM structure_cells WHERE x BETWEEN ? AND ? AND z BETWEEN ? AND ?",
                              (cx * CHUNK, cx * CHUNK + CHUNK - 1, cz * CHUNK, cz * CHUNK + CHUNK - 1)).fetchall()
        except sqlite3.OperationalError:  # a world from before M5, read without its schema update
            return set()
        return {(row[0], row[1], row[2]) for row in rows}

    grid = Grid(lambda x, y, z: block_at(x, y, z, seed), load_edits, write, load_claims)
    grid.herd = Herd(db)
    grid.overlay(sky)
    return grid
