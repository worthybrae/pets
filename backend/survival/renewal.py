"""Renewal: the world regrows on its own clock, whatever Mimo is doing.

Each world database keeps a `growth` table of changes due later: (x, y, z, block, ready_at),
one per cell, with `ready_at` in server time. `renew` is part of the world, not of Mimo's mind:
advance_world runs it after every catch-up chunk of actions (at most 60 game seconds), so a
long gap regrows the world in time order. Each call:

1. Reacts to the blocks Mimo's steps changed since the last call (Grid.take_changes):
   - a picked berry bush turns ripe again after 2 game days;
   - a crop grows one stage every 12 game minutes when water lies within 4 blocks of its
     farmland, and every 36 game minutes otherwise;
   - farmland turns back into dirt after 2 game days without a crop (tilled, or a crop taken
     from it), unless a crop grows on it by then.
2. Applies every entry due by then, oldest first. An entry only happens while its cell still
   holds what it grows from (the unripe bush, the crop one stage earlier, the bare farmland);
   otherwise it is dropped. A crop stage that happens schedules the next one from its own due
   time, so a long catch-up still grows a crop through every stage.
3. Lets fish stocks recover, one fish per region per game day (nature.recover_fish).
Mined ore never comes back: nothing schedules it.
"""

from __future__ import annotations

import sqlite3

from backend.survival import nature
from backend.survival.clock import DAY_SECONDS
from backend.survival.grid import Cell, Grid

BERRY_REGROW = 2 * DAY_SECONDS
CROP_STAGE_WET = 12 * 60.0
CROP_STAGE_DRY = 36 * 60.0
FARMLAND_REVERT = 2 * DAY_SECONDS
WATER_REACH = 4
MAX_APPLIED = 512  # entries one call applies at most; the rest wait for the next call

Entry = tuple[Cell, str, float]


def create_growth_table(db: sqlite3.Connection) -> None:
    """Create the growth table. Run it inside the caller's BEGIN IMMEDIATE."""
    db.execute("CREATE TABLE IF NOT EXISTS growth (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, "
               "block TEXT NOT NULL, ready_at REAL NOT NULL, PRIMARY KEY (x, y, z))")
    db.execute("CREATE INDEX IF NOT EXISTS growth_by_time ON growth(ready_at)")


def schedule(db: sqlite3.Connection, cell: Cell, block: str, ready_at: float, keep_earlier: bool = False) -> None:
    """Make `cell` turn into `block` at `ready_at`, replacing what was due there (or, with
    `keep_earlier`, leaving an entry that is already due there alone)."""
    verb = "INSERT OR IGNORE" if keep_earlier else "INSERT OR REPLACE"
    db.execute(f"{verb} INTO growth(x, y, z, block, ready_at) VALUES (?, ?, ?, ?, ?)", (*cell, block, ready_at))


def due(db: sqlite3.Connection, until: float, limit: int) -> list[Entry]:
    rows = db.execute("SELECT x, y, z, block, ready_at FROM growth WHERE ready_at <= ? "
                      "ORDER BY ready_at, x, y, z LIMIT ?", (until, limit)).fetchall()
    return [((row[0], row[1], row[2]), row[3], row[4]) for row in rows]


def scheduled(db: sqlite3.Connection) -> list[Entry]:
    """Every entry, soonest first (for tests and checks)."""
    return due(db, float("inf"), 1_000_000)


def later(at: float, game_seconds: float, scale: float) -> float:
    return at + game_seconds / scale


def watered(grid: Grid, farmland: Cell) -> bool:
    """Water within 4 blocks of the farmland, at its level or one above or below."""
    x, y, z = farmland
    return any(grid.water((x + dx, y + dy, z + dz)) for dy in (0, -1, 1)
               for dx in range(-WATER_REACH, WATER_REACH + 1) for dz in range(-WATER_REACH, WATER_REACH + 1))


def stage_seconds(grid: Grid, crop: Cell) -> float:
    x, y, z = crop
    return CROP_STAGE_WET if watered(grid, (x, y - 1, z)) else CROP_STAGE_DRY


def react(db: sqlite3.Connection, grid: Grid, state: dict, changes: list[tuple[Cell, str, str]], at: float,
          scale: float) -> None:
    """Schedule what the changed blocks will turn into."""
    for cell, before, after in changes:
        x, y, z = cell
        grown = nature.next_stage(after)
        if after == "berry_bush":
            schedule(db, cell, "berry_bush_ripe", later(at, BERRY_REGROW, scale))
        elif grown is not None:
            schedule(db, cell, grown, later(at, stage_seconds(grid, cell), scale))
        elif after == "farmland":
            schedule(db, cell, "dirt", later(at, FARMLAND_REVERT, scale))
        elif nature.crop_stage(before) is not None and grid.material(x, y - 1, z) == "farmland":
            schedule(db, (x, y - 1, z), "dirt", later(at, FARMLAND_REVERT, scale))


def apply_entry(db: sqlite3.Connection, grid: Grid, state: dict, entry: Entry, scale: float,
                events: list) -> None:
    """Make one due change happen if its cell still holds what it grows from."""
    cell, block, ready_at = entry
    x, y, z = cell
    here = grid.material(*cell)
    stage = nature.crop_stage(block)
    if block == "berry_bush_ripe":
        if here == "berry_bush":
            grid.put(*cell, block)
    elif stage is not None:
        crop, number = stage
        if here == f"{crop}_{number - 1}" and grid.material(x, y - 1, z) == "farmland":
            grid.put(*cell, block)
            grown = nature.next_stage(block)
            if grown is not None:
                schedule(db, cell, grown, later(ready_at, stage_seconds(grid, cell), scale))
    elif block == "dirt":
        if here == "farmland" and nature.crop_stage(grid.material(x, y + 1, z)) is None:
            grid.put(*cell, "dirt")


def renew(state: dict, context, at: float) -> None:
    """The world's own changes up to `at` (see the module docstring). Needs the tick's database."""
    db, grid = context.db, context.grid
    if db is None:
        return
    scale = context.clock_at(at)["time_scale"]
    react(db, grid, state, grid.take_changes(), at, scale)
    applied = 0
    while applied < MAX_APPLIED:
        entries = due(db, at, MAX_APPLIED - applied)
        if not entries:
            break
        for entry in entries:
            db.execute("DELETE FROM growth WHERE x=? AND y=? AND z=?", entry[0])
            apply_entry(db, grid, state, entry, scale, context.events)
            applied += 1
    grid.take_changes()  # renewal's own writes need no reaction
    nature.recover_fish(state, at, scale)
