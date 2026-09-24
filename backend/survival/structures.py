"""What Mimo built, and the cells no other plan may touch.

A structure starts when a building purpose plans its first batch: `start` stores its design
(backend.survival.blueprints) in the structures table and claims every cell of it in
structure_cells (backend.survival.memory), including the cells that must stay open: the door
gap and the passage from the door to the home cell. From then on:
- `todo` lists the cells still waiting for their block, in build order. A finished shelter with
  a floor, wall or roof block missing is damaged, and build_shelter repairs it (`damaged`); a
  door gap or passage something was put in is `blocked`, and build_shelter clears it.
- `reserved` is the one rule every planner that digs, tills, plants or puts a station down
  follows: it keeps off whatever something Mimo built claims (walls, roof, floor, fittings, the
  door gap, the passage and the home cell) and off Mimo's farm plots and saplings (TENDED).
  Regrowth keeps off claimed cells too (backend.survival.renewal).
- `clearing` gives the mine step that takes a plant a block cannot replace (a mushroom, a
  sapling, a berry bush, a crop) out of a cell before a batch builds there.
"""

from __future__ import annotations

import sqlite3

from backend.services.blocks import hardness, is_plant, is_replaceable, is_solid
from backend.survival.blueprints import FITTINGS, KEEP_OPEN, STRUCTURAL, Blueprint, Planned, from_data, with_door
from backend.survival.grid import Cell, Grid
from backend.survival.memory import add_structure

TENDED = ("farmland", "sapling")  # Mimo's own plots and plantings


def reserved(grid: Grid, cell: Cell) -> bool:
    """Part of something Mimo built or tends: no plan digs, tills, plants or puts a station there."""
    return grid.claimed(cell) or grid.material(*cell) in TENDED


def start(db: sqlite3.Connection, grid: Grid, blueprint: Blueprint, at: float) -> int:
    """Remember a structure Mimo starts building and claim its cells at once, so plans made later
    in the same tick keep off them too."""
    cells = [(planned.cell, planned.part, planned.block) for planned in blueprint.cells]
    number = add_structure(db, blueprint.kind, blueprint.name, blueprint.anchor, at, blueprint.to_data(), cells)
    grid.claims.update(planned.cell for planned in blueprint.cells)
    return number


def blueprint_of(structure: dict) -> Blueprint:
    return with_door(from_data(structure["data"]))


def missing(grid: Grid, planned: Planned) -> bool:
    """The cell still waits for its block: a floor, wall, roof or plot that is not solid (natural
    ground used as a wall counts), a fitting that is not there."""
    material = grid.material(*planned.cell)
    if planned.part in STRUCTURAL:
        return not is_solid(material)
    if planned.part == "plot":
        return material != "farmland"
    if planned.part == "door":  # L2: the gap's lower cell waits for its door; the one above stays open
        return planned.block == "door" and material != "door"
    return planned.part in FITTINGS and material != planned.block


def todo(grid: Grid, blueprint: Blueprint, parts: tuple[str, ...] = STRUCTURAL) -> list[Planned]:
    """The cells of these parts still waiting for their block, in build order."""
    return [planned for planned in blueprint.parts(*parts) if missing(grid, planned)]


def blocked(grid: Grid, blueprint: Blueprint) -> list[Cell]:
    """Door gap and passage cells something solid was put in."""
    return [planned.cell for planned in blueprint.parts(*KEEP_OPEN) if is_solid(grid.material(*planned.cell))]


def damaged(grid: Grid, blueprint: Blueprint) -> bool:
    return bool(todo(grid, blueprint)) or bool(blocked(grid, blueprint))


def clearing(grid: Grid, cell: Cell) -> list[dict]:
    """A mine step for a plant that stands in `cell` and that a placed block cannot replace, so
    it can be built on (nothing for air, grass, flowers or anything solid)."""
    material = grid.material(*cell)
    if is_plant(material) and not is_replaceable(material) and hardness(material) is not None:
        return [{"kind": "mine", "target": list(cell)}]
    return []


def structure_at(db: sqlite3.Connection, cell: Cell) -> int | None:
    """The structure that claims `cell`, if any."""
    row = db.execute("SELECT structure FROM structure_cells WHERE x=? AND y=? AND z=?", tuple(cell)).fetchone()
    return None if row is None else row[0]
