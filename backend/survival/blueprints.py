"""The building generator: designs for what Mimo builds, from its site, materials and style.

A design is a Blueprint: an ordered list of Planned cells (cell, part, block) that the planner
places one block at a time, floor first, then the walls (bottom row, then top), the roof and the
fittings, plus the cells that matter afterwards: where Mimo lives inside (`inside`), where it
stands to build (`stands`), the door gap and the cell in front of it, and the cells that must
stay open (the passage from the door to the home cell). Everything comes from the inputs alone,
so the same site, style and materials always give the same design, and tests need no world.

Inputs (spec section 8):
- the site: flat-enough natural ground near home, read through the Grid so Mimo's own digging
  and building count (`find_site`). Every column must be untouched ground: never farmland, a
  sapling, water, a dug stair or anything built, and never next to a dug column (a way out);
- the size tier: 3x3, 4x3 or 5x4 inside and two blocks high, the largest the materials cover
  and creativity allows;
- the materials Mimo has: planks and cobblestone first, then other stone and loose blocks, dirt
  as a last resort. Logs beyond the 2 Mimo keeps count as the 4 planks each makes. A design
  names the block each cell prefers; when that block runs short any other building block stands
  in for it;
- style knobs (`style_for`): roof shape (flat, gable, dome), wall material, window pattern and
  door side. Creativity makes a fancier roof and windows likelier and allows bigger tiers,
  thrift prefers cobblestone walls to planks, and the world seed breaks ties, so two pets with
  the same traits still build differently.

A shelter's inside is enclosed on every side with a roof over all of it, so every inside cell
passes the server's shelter check (vitals.is_sheltered). Fittings: a bed and a chest in the back
corners, a campfire outside beside the door, up to four torches at the outside corners and (L2) a
door in the lower cell of the door gap, which Mimo walks through and creatures never do. A
farm is a rectangle of 3x3 to 5x5 plots on flat tillable ground, as near its center as it fits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from backend.services.blocks import is_replaceable, is_solid
from backend.services.crafting import PLANKS_OF, STAND_INS
from backend.services.worldgen import hash32
from backend.survival.grid import Cell, Grid

ROOFS = ("flat", "gable", "dome")
DOOR_SIDES = ("north", "east", "south", "west")
TIERS = ((3, 3), (4, 3), (5, 4))  # (width across the door side, depth), inside
# Blocks a structure can be built from, in the order they stand in for each other; dirt is last.
BUILDING = ("cobblestone", "planks", "birch_planks", "spruce_planks", "stone_bricks", "brick", "limestone",
            "sandstone", "basalt", "moss", "clay", "sand", "gravel", "dirt")
LOGS_KEPT = 2  # logs Mimo never turns into building planks: a campfire's worth
STRUCTURAL = ("floor", "wall", "roof")
FITTINGS = ("bed", "chest", "campfire", "torch")
# Parts that must stay open: the door gap, the way in from outside and on to the home cell.
KEEP_OPEN = ("door", "front", "passage")
SITE_RANGE = 12  # blocks from the site's center to where the search starts
CLEARANCE = 5  # open cells a shelter's inside needs above its floor (room for the tallest roof)
SCAN = 6  # blocks above and below the reference height a column's ground is looked for
FARM_REACH = 6  # blocks from the farm's center (beside water, or home) a farm's corner may move
TILLABLE = ("grass", "dirt", "moss")
NAMES = {"flat": "Snug", "gable": "Peaked", "dome": "Round"}
NOUNS = {"planks": "Cabin", "cobblestone": "Cottage", "dirt": "Burrow"}


@dataclass(frozen=True)
class Style:
    roof: str  # "flat", "gable" or "dome"
    wall: str  # the wall block it prefers
    roof_block: str  # the roof block it prefers
    windows: str  # "none" or "sides" (a gap high in the middle of each side wall)
    doors: tuple[str, ...]  # door sides to try, best first


@dataclass(frozen=True)
class Planned:
    cell: Cell
    part: str  # floor, wall, roof, bed, chest, campfire, torch, plot; door, front, passage or room (kept free)
    block: str  # the block it wants; floor, wall and roof take any building block when it runs short


@dataclass(frozen=True)
class Blueprint:
    kind: str  # "shelter" or "farm"
    name: str
    anchor: Cell  # the inside cell Mimo lives in (a shelter), or the middle plot's ground (a farm)
    cells: tuple[Planned, ...]
    stands: tuple[Cell, ...] = ()  # where Mimo stands to build, inside
    front: Cell | None = None  # the cell in front of the door, outside
    style: dict = field(default_factory=dict)

    def parts(self, *parts: str) -> list[Planned]:
        return [planned for planned in self.cells if planned.part in parts]

    def one(self, part: str) -> Cell | None:
        found = self.parts(part)
        return found[0].cell if found else None

    def to_data(self) -> dict:
        return {"kind": self.kind, "name": self.name, "anchor": list(self.anchor),
                "cells": [[*planned.cell, planned.part, planned.block] for planned in self.cells],
                "stands": [list(cell) for cell in self.stands], "front": list(self.front) if self.front else None,
                "style": dict(self.style)}


def from_data(data: dict) -> Blueprint:
    """A Blueprint back from Blueprint.to_data (the structures table keeps it as JSON)."""
    return Blueprint(
        kind=data["kind"], name=data["name"], anchor=tuple(data["anchor"]),
        cells=tuple(Planned((x, y, z), part, block) for x, y, z, part, block in data["cells"]),
        stands=tuple(tuple(cell) for cell in data.get("stands", [])),
        front=tuple(data["front"]) if data.get("front") else None, style=dict(data.get("style", {})))


def with_door(blueprint: Blueprint) -> Blueprint:
    """A shelter designed before doors (L2) gets one in the lower cell of its door gap, so build_shelter
    furnishes old homes too; any other design comes back as it is."""
    gap = blueprint.parts("door")
    if blueprint.kind != "shelter" or not gap or any(planned.block == "door" for planned in gap):
        return blueprint
    lowest = min(gap, key=lambda planned: planned.cell[1])
    return replace(blueprint, cells=tuple(Planned(planned.cell, planned.part, "door") if planned is lowest else planned
                                          for planned in blueprint.cells))


# Style and materials ---------------------------------------------------------------------------

def roll(seed: str, salt: int, channel: int) -> float:
    """A number in [0, 1) fixed by the world seed, a salt (which structure) and a channel."""
    return hash32(salt, 0, 0, seed, 40 + channel) / 4294967296


def style_for(traits: dict, seed: str, salt: int = 0) -> Style:
    """Style knobs from traits and the world seed: creativity makes a fancy roof and windows
    likelier and mixes the roof block, thrift prefers cobblestone walls, the seed breaks ties."""
    creativity, thrift = float(traits.get("creativity", 50)), float(traits.get("thrift", 50))
    fancy = roll(seed, salt, 1) * 100 < creativity
    roof = ROOFS[1 + int(roll(seed, salt, 2) * 2)] if fancy else "flat"
    wall = "cobblestone" if thrift >= 50 else "planks"
    other = "planks" if wall == "cobblestone" else "cobblestone"
    roof_block = other if creativity >= 50 else wall
    windows = "sides" if roll(seed, salt, 3) * 100 < creativity else "none"
    turn = int(roll(seed, salt, 4) * 4)
    return Style(roof, wall, roof_block, windows, DOOR_SIDES[turn:] + DOOR_SIDES[:turn])


def supplies(inventory: dict) -> dict[str, int]:
    """Building blocks Mimo has, with each log beyond the LOGS_KEPT it keeps for a campfire or a
    tool's sticks counted as the 4 planks of its own wood it makes (oak logs are the ones kept first)."""
    have = {block: inventory.get(block, 0) for block in BUILDING if inventory.get(block, 0) > 0}
    keep = LOGS_KEPT
    for log, planks in PLANKS_OF.items():
        spare = inventory.get(log, 0) - keep
        keep = max(0, -spare)
        if spare > 0:
            have[planks] = have.get(planks, 0) + 4 * spare
    return have


def pick_block(wanted: str, have: dict[str, int]) -> str | None:
    """The block to place for a cell that wants `wanted`: it or what stands in for it (other planks for
    planks), else the first building block left."""
    for block in (wanted, *STAND_INS.get(wanted, ())):
        if have.get(block, 0) > 0:
            return block
    return next((block for block in BUILDING if have.get(block, 0) > 0), None)


def name_for(style: Style) -> str:
    return f"{NAMES[style.roof]} {NOUNS.get(style.wall, 'Hut')}"


# Sites -----------------------------------------------------------------------------------------

@dataclass
class Ground:
    """What one column offers: its natural ground height and how many open cells stand above it.
    `ground` is None when the column cannot be built on (water, a plant or fitting in the way,
    placed or dug blocks, a cave under it, nothing found near the reference height)."""
    ground: int | None
    open_above: int
    dug: bool


def open_cell(material: str) -> bool:
    return material != "water" and is_replaceable(material)


def look_at(grid: Grid, x: int, z: int, reference: int) -> Ground:
    """Scan the column down from SCAN above `reference` for the first block that is not open."""
    top = reference + SCAN
    for y in range(top, reference - SCAN - 1, -1):
        material = grid.material(x, y, z)
        if open_cell(material):
            continue
        natural = grid.natural_material(x, y, z)
        dug = is_solid(grid.natural_material(x, y + 1, z))
        firm = (is_solid(material) and material == natural and not dug and grid.solid((x, y - 1, z))
                and not any(grid.claimed((x, y + dy, z)) for dy in range(0, CLEARANCE + 1)))
        return Ground(y if firm else None, top - y, dug)
    return Ground(None, 0, False)


class Survey:
    """Columns looked at once and remembered, for one site search."""

    def __init__(self, grid: Grid, reference: int):
        self.grid, self.reference = grid, reference
        self.columns: dict[tuple[int, int], Ground] = {}

    def at(self, x: int, z: int) -> Ground:
        found = self.columns.get((x, z))
        if found is None:
            found = self.columns[(x, z)] = look_at(self.grid, x, z, self.reference)
        return found

    def height(self, x: int, z: int) -> int | None:
        return self.at(x, z).ground

    def room(self, x: int, z: int, up_to: int) -> bool:
        """Every cell from just above the column's ground up to height `up_to` is open."""
        column = self.at(x, z)
        return column.ground is not None and column.ground + column.open_above >= up_to

    def dug_near(self, x: int, z: int) -> bool:
        """A dug column (a stair or hole Mimo made) beside this one: keep the way out clear."""
        return any(self.at(x + dx, z + dz).dug for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def local_to_world(side: str, origin: tuple[int, int], size: tuple[int, int], i: int, j: int) -> tuple[int, int]:
    """(x, z) of local (i, j): i runs across the door side, j from the front (-1 is the front
    wall) to the back. `origin` is the smallest (x, z) inside; the door faces `side`."""
    width, depth = size
    ox, oz = origin
    if side == "north":
        return ox + i, oz + j
    if side == "south":
        return ox + width - 1 - i, oz + depth - 1 - j
    if side == "west":
        return ox + j, oz + width - 1 - i
    return ox + depth - 1 - j, oz + i


@dataclass(frozen=True)
class Site:
    origin: tuple[int, int]
    floor: int  # the ground height inside; Mimo stands at floor + 1
    size: tuple[int, int]
    side: str
    grounds: dict  # (i, j) -> ground height, for every column the design uses

    def world(self, i: int, j: int, y: int) -> Cell:
        x, z = local_to_world(self.side, self.origin, self.size, i, j)
        return x, y, z


def roof_heights(roof: str, width: int, depth: int) -> dict[tuple[int, int], int]:
    """The roof's height above the floor over each inside column: 3 over the walls' top, higher
    toward the middle for a gable (a ridge from front to back) or a dome."""
    heights = {}
    for i in range(width):
        for j in range(depth):
            if roof == "gable":
                rise = min(i, width - 1 - i)
            elif roof == "dome":
                rise = min(i, width - 1 - i, j, depth - 1 - j, 1)
            else:
                rise = 0
            heights[(i, j)] = 3 + rise
    return heights


def door_column(size: tuple[int, int]) -> int:
    return (size[0] - 1) // 2


def check_site(survey: Survey, origin: tuple[int, int], size: tuple[int, int], side: str,
               roof: str) -> Site | None:
    """The site with the inside's local corner at `origin` and the door on `side`, or None when
    the ground there does not suit a shelter."""
    width, depth = size

    def where(i: int, j: int) -> tuple[int, int]:
        return local_to_world(side, origin, size, i, j)

    grounds: dict[tuple[int, int], int] = {}
    floor = survey.height(*where(0, 0))
    if floor is None:
        return None
    top = max(roof_heights(roof, width, depth).values())
    for i in range(width):
        for j in range(depth):
            x, z = where(i, j)
            if survey.height(x, z) != floor or not survey.room(x, z, floor + top):
                return None
            grounds[(i, j)] = floor
    door = door_column(size)
    for i in range(-1, width + 1):
        for j in range(-1, depth + 1):
            if 0 <= i < width and 0 <= j < depth:
                continue
            x, z = where(i, j)
            ground = survey.height(x, z)
            if ground is None or abs(ground - floor) > 1 or not survey.room(x, z, floor + top):
                return None
            if (i, j) == (door, -1) and ground != floor:
                return None
            if survey.dug_near(x, z):
                return None
            grounds[(i, j)] = ground
    x, z = where(door, -2)
    ground = survey.height(x, z)
    if ground is None or not floor - 1 <= ground <= floor or not survey.room(x, z, floor + 2) \
            or survey.dug_near(x, z):
        return None
    grounds[(door, -2)] = ground
    for i, j in ((door + 1, -2), (door - 1, -2), (-2, -2), (width + 1, -2), (-2, depth + 1), (width + 1, depth + 1)):
        ground = survey.height(*where(i, j))
        if ground is not None and floor - 1 <= ground <= floor + 1 and survey.room(*where(i, j), ground + 1):
            grounds[(i, j)] = ground
    return Site(origin, floor, size, side, grounds)


def find_site(grid: Grid, center: Cell, size: tuple[int, int], sides: tuple[str, ...], roof: str,
              reach: int = SITE_RANGE) -> Site | None:
    """The nearest site to `center` (its inside's middle closest first) where a shelter of `size`
    fits with its door on one of `sides` (tried in order)."""
    survey = Survey(grid, center[1] - 1)
    cx, _, cz = center
    width, depth = size
    candidates = []
    for dx in range(-reach, reach + 1):
        for dz in range(-reach, reach + 1):
            if math.hypot(dx, dz) <= reach:
                candidates.append((math.hypot(dx, dz), dx, dz))
    for _, dx, dz in sorted(candidates):
        for side in sides:
            span = (width, depth) if side in ("north", "south") else (depth, width)
            origin = (cx + dx - (span[0] - 1) // 2, cz + dz - (span[1] - 1) // 2)
            site = check_site(survey, origin, size, side, roof)
            if site is not None:
                return site
    return None


# Shelters --------------------------------------------------------------------------------------

def shelter(site: Site, style: Style, name: str) -> Blueprint:
    """The shelter's cells in build order: floor under low wall columns, walls (bottom row, then
    top), the roof (lowest first), then the bed, the campfire, the chest and the torches."""
    width, depth = site.size
    floor, door = site.floor, door_column(site.size)
    heights = roof_heights(style.roof, width, depth)
    ring = [(i, j) for j in range(-1, depth + 1) for i in range(-1, width + 1)
            if not (0 <= i < width and 0 <= j < depth)]
    cells: list[Planned] = []
    for i, j in ring:
        if site.grounds[(i, j)] < floor:
            cells.append(Planned(site.world(i, j, floor), "floor", "dirt"))
    middle = (depth - 1) // 2
    for y in (1, 2):
        for i, j in ring:
            if i == door and j == -1:
                continue
            if y == 2 and style.windows == "sides" and i in (-1, width) and j == middle:
                continue
            if y == 1 and site.grounds[(i, j)] > floor:
                cells.append(Planned(site.world(i, j, floor + 1), "wall", "natural"))
                continue
            cells.append(Planned(site.world(i, j, floor + y), "wall", style.wall))
    if style.roof == "gable":
        for i in range(width):
            for y in range(3, heights[(i, 0)]):
                for j in (-1, depth):
                    cells.append(Planned(site.world(i, j, floor + y), "wall", style.wall))
    for (i, j), height in sorted(heights.items(), key=lambda item: (item[1], item[0][1], item[0][0])):
        cells.append(Planned(site.world(i, j, floor + height), "roof", style.roof_block))
    cells.append(Planned(site.world(0, depth - 1, floor + 1), "bed", "bed"))
    for i in (door + 1, door - 1):
        if (i, -2) in site.grounds and site.grounds[(i, -2)] <= floor:
            cells.append(Planned(site.world(i, -2, site.grounds[(i, -2)] + 1), "campfire", "campfire"))
            break
    cells.append(Planned(site.world(width - 1, depth - 1, floor + 1), "chest", "chest"))
    for i, j in ((-2, -2), (width + 1, -2), (-2, depth + 1), (width + 1, depth + 1)):
        if (i, j) in site.grounds:
            cells.append(Planned(site.world(i, j, site.grounds[(i, j)] + 1), "torch", "torch"))
    home = (door, middle)
    for y in (1, 2):  # L2: a door in the lower cell of the gap; the cell above it stays open
        cells.append(Planned(site.world(door, -1, floor + y), "door", "door" if y == 1 else "air"))
    front = site.world(door, -2, site.grounds[(door, -2)] + 1)
    cells.append(Planned(front, "front", "air"))
    cells.append(Planned((front[0], front[1] + 1, front[2]), "front", "air"))
    passage = {(door, j) for j in range(0, middle + 1)}
    for j in range(depth):
        for i in range(width):
            if (i, j) in passage:
                cells.append(Planned(site.world(i, j, floor + 1), "passage", "air"))
            elif (i, j) not in ((0, depth - 1), (width - 1, depth - 1)):
                cells.append(Planned(site.world(i, j, floor + 1), "room", "air"))
            cells.append(Planned(site.world(i, j, floor + 2), "room", "air"))
    taken = {(0, depth - 1), (width - 1, depth - 1)}
    stands = [site.world(i, j, floor + 1) for j in range(depth) for i in range(width) if (i, j) not in taken]
    stands.sort(key=lambda cell: math.dist(cell, site.world(*home, floor + 1)))
    return Blueprint("shelter", name, site.world(*home, floor + 1), tuple(cells), tuple(stands), front,
                     {"roof": style.roof, "wall": style.wall, "roof_block": style.roof_block,
                      "windows": style.windows, "door": site.side, "size": list(site.size)})


def bill(blueprint: Blueprint, grid: Grid | None = None) -> int:
    """How many blocks the floor, walls and roof still need (natural ground counts as wall)."""
    needed = 0
    for planned in blueprint.parts(*STRUCTURAL):
        if planned.block == "natural":
            continue
        if grid is None or not is_solid(grid.material(*planned.cell)):
            needed += 1
    return needed


def design_shelter(grid: Grid, seed: str, center: Cell, traits: dict, inventory: dict, owner: str,
                   salt: int = 0) -> Blueprint | None:
    """A shelter near `center`: the largest tier creativity allows and the materials cover (else
    the smallest), on the nearest site that fits it."""
    style = style_for(traits, seed, salt)
    have = sum(supplies(inventory).values())
    allowed = 1 + (float(traits.get("creativity", 50)) >= 60) + (float(traits.get("creativity", 50)) >= 80)
    sizes = list(reversed(TIERS[:allowed]))
    for size in sizes:
        site = find_site(grid, center, size, style.doors, style.roof)
        if site is None:
            continue
        design = shelter(site, style, f"{owner}'s {name_for(style)}")
        if bill(design, grid) <= have or size == TIERS[0]:
            return design
    return None


# Farms -----------------------------------------------------------------------------------------

def farm_ground(survey: Survey, x: int, z: int, floor: int) -> bool:
    """Untouched tillable ground at `floor` with room above it."""
    grid = survey.grid
    return (survey.height(x, z) == floor and grid.material(x, floor, z) in TILLABLE
            and open_cell(grid.material(x, floor + 1, z)))


def design_farm(grid: Grid, center: Cell, size: int, owner: str, tilled: tuple[Cell, ...] = (),
                reach: int = FARM_REACH) -> Blueprint | None:
    """A size x size rectangle of plots on flat tillable ground, the nearest to `center` (a ground
    cell: beside water, or home). With `tilled` (the farmland of the farm Mimo keeps, `center`
    its first plot) the rectangle covers `center` and as much of that farmland as it can, so the
    old farm grows instead of a second one starting."""
    survey = Survey(grid, center[1])
    cx, cy, cz = center
    old = {(x, z) for x, y, z in tilled if y == cy}
    best = None
    for dx in range(-reach, reach + 1):
        for dz in range(-reach, reach + 1):
            ox, oz = cx + dx - (size - 1) // 2, cz + dz - (size - 1) // 2
            ground = [(ox + i, oz + j) for i in range(size) for j in range(size)]
            if tilled and (cx, cz) not in ground:
                continue
            floor = cy if tilled else survey.height(ox, oz)
            if floor is None or not all((x, z) in old or farm_ground(survey, x, z, floor) for x, z in ground):
                continue
            key = (-len(old.intersection(ground)), math.hypot(dx, dz), dx, dz)
            if best is None or key < best[0]:
                best = (key, [(x, floor, z) for x, z in ground])
    if best is None:
        return None
    plots = best[1]
    return Blueprint("farm", f"{owner}'s farm", plots[len(plots) // 2],
                     tuple(Planned(cell, "plot", "farmland") for cell in plots), style={"size": [size, size]})
