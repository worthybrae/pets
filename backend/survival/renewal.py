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
     from it), unless a crop grows on it by then;
   - a planted sapling grows into a tree after 1 game day if there is room for the trunk and
     canopy (worldgen's tree shape) clear of Mimo, the cell above its head, any home or shelter
     (and the cell above it) and every cell something Mimo built claims (Grid.claimed: its
     walls, roof, room, door and torch cells), and tries again every 10 game minutes until there is;
   - a log that goes (chopped, or any other way) leaves the leaves that no longer reach a log
     within 4 steps (through leaves and logs) to decay 1 to 6 game minutes later. A decaying
     leaf may drop a sapling (1 in 12) or an apple (1 in 20), which Mimo gathers when it is
     within 16 blocks, and it is kept in state["decays"] so the viewer can show a puff;
   - a picked mushroom comes back on forest floor in its chunk after a game day, one per chunk
     per game day and at most 3 in the chunk, never in a claimed cell.
2. Applies every entry due by then, oldest first. An entry only happens while its cell still
   holds what it grows from (the unripe bush, the crop one stage earlier, the bare farmland);
   otherwise it is dropped. A crop stage that happens schedules the next one from its own due
   time, so a long catch-up still grows a crop through every stage. An entry whose apply
   crashes is tried again 10 game minutes later and dropped after 5 crashes (`failures`).
3. Lets fish stocks recover, one fish per region per game day (nature.recover_fish).
Mined ore never comes back: nothing schedules it.
"""

from __future__ import annotations

import logging
import math
import sqlite3

from backend.services.blocks import is_replaceable
from backend.services.crafting import add_item
from backend.services.worldgen import biome_at, is_leaf, terrain_height
from backend.survival import nature
from backend.survival.clock import DAY_SECONDS
from backend.survival.grid import CHUNK, Cell, Grid
from backend.survival.memory import SHELTER_KINDS, cell_of, places
from backend.survival.once import log_once
from backend.survival.senses import LOG, TRUNK_HEIGHT

logger = logging.getLogger(__name__)

BERRY_REGROW = 2 * DAY_SECONDS
CROP_STAGE_WET = 12 * 60.0
CROP_STAGE_DRY = 36 * 60.0
FARMLAND_REVERT = 2 * DAY_SECONDS
WATER_REACH = 4
MAX_APPLIED = 512  # entries one call applies at most; the rest wait for the next call
LEAF_REACH = 4
DECAY_SECONDS = (60.0, 360.0)
DECAY_CHANNEL = 36
DROP_REACH = 16.0
DECAYS_KEPT = 24
FAILED_RETRY = 600.0  # game seconds before an entry whose apply crashed is tried again
FAILED_LIMIT = 5  # crashes after which the entry is dropped
SAPLING_GROWS = DAY_SECONDS
SAPLING_RETRY = 600.0
CANOPY_REACH = 2  # blocks the canopy spreads from the trunk
MUSHROOM_RESPAWN = DAY_SECONDS
MUSHROOM_CAP = 3
MUSHROOM_SPOT_CHANNEL = 37
FOREST_FLOOR = ("grass", "moss")
NEIGHBOURS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))

Entry = tuple[Cell, str, float]


def create_growth_table(db: sqlite3.Connection) -> None:
    """Create the growth table, or add the `failures` column to one made before it existed. Run it
    inside the caller's BEGIN IMMEDIATE."""
    db.execute("CREATE TABLE IF NOT EXISTS growth (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, "
               "block TEXT NOT NULL, ready_at REAL NOT NULL, failures INTEGER, PRIMARY KEY (x, y, z))")
    if "failures" not in {row[1] for row in db.execute("PRAGMA table_info(growth)")}:
        db.execute("ALTER TABLE growth ADD COLUMN failures INTEGER")
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


def step_to(cell: Cell, offset: tuple[int, int, int]) -> Cell:
    return cell[0] + offset[0], cell[1] + offset[1], cell[2] + offset[2]


def leaf_supported(grid: Grid, leaf: Cell) -> bool:
    """A log within 4 steps of the leaf, counting through leaves and logs."""
    seen, frontier = {leaf}, [leaf]
    for _ in range(LEAF_REACH):
        ahead = []
        for cell in frontier:
            for offset in NEIGHBOURS:
                near = step_to(cell, offset)
                if near in seen:
                    continue
                seen.add(near)
                material = grid.material(*near)
                if material == LOG:
                    return True
                if material == "leaves":
                    ahead.append(near)
        frontier = ahead
    return False


def orphaned_leaves(grid: Grid, log: Cell) -> list[Cell]:
    """Leaves within 4 steps (through leaves) of a log that went, which no longer reach a log."""
    seen, frontier, found = {log}, [log], []
    for _ in range(LEAF_REACH):
        ahead = []
        for cell in frontier:
            for offset in NEIGHBOURS:
                near = step_to(cell, offset)
                if near not in seen and grid.material(*near) == "leaves":
                    ahead.append(near)
                    found.append(near)
                seen.add(near)
        frontier = ahead
    return [leaf for leaf in found if not leaf_supported(grid, leaf)]


def decay_seconds(seed: str, leaf: Cell, at: float) -> float:
    low, high = DECAY_SECONDS
    return low + (high - low) * nature.roll(seed, leaf, DECAY_CHANNEL, int(at))


def tree_cells(sapling: Cell) -> tuple[list[Cell], list[Cell]]:
    """The trunk (from the sapling's cell up) and canopy cells of a tree grown from `sapling`,
    in worldgen's shape: 4 logs, then leaves 5 and 6 above the ground."""
    x, y, z = sapling
    ground = y - 1
    trunk = [(x, y + dy, z) for dy in range(TRUNK_HEIGHT)]
    canopy = [(x + dx, ground + dy, z + dz) for dy in (5, 6) for dx in range(-2, 3) for dz in range(-2, 3)
              if is_leaf(dx, dy, dz)]
    return trunk, canopy


def open_cell(material: str) -> bool:
    """Air, or a plant that gives way (never water)."""
    return material != "water" and is_replaceable(material)


def tree_fits(grid: Grid, sapling: Cell) -> bool:
    """Room for the tree: its trunk above the sapling open, its canopy open or leaves already, and
    none of it (the sapling's own cell included) in a cell something Mimo built claims."""
    trunk, canopy = tree_cells(sapling)
    return (not any(grid.claimed(cell) for cell in trunk + canopy)
            and all(open_cell(grid.material(*cell)) for cell in trunk[1:])
            and all(open_cell(grid.material(*cell)) or grid.material(*cell) == "leaves" for cell in canopy))


def grow_tree(grid: Grid, sapling: Cell) -> None:
    trunk, canopy = tree_cells(sapling)
    for cell in trunk:
        grid.put(*cell, LOG)
    for cell in canopy:
        if open_cell(grid.material(*cell)):
            grid.put(*cell, "leaves")


def forest_floor(grid: Grid, seed: str, chunk: tuple[int, int], at: float,
                 avoid: frozenset[Cell] = frozenset()) -> Cell | None:
    """An open cell on forest grass or moss in the chunk, picked by the roll; None if 8 tries miss.
    A cell in `avoid` (already scheduled there, or already chosen earlier in this batch) is
    skipped in favour of the next attempt, so two picks in one chunk in one call land apart, and
    so is a cell something Mimo built claims."""
    cx, cz = chunk
    for attempt in range(8):
        pick = nature.roll(seed, (cx, attempt, cz), MUSHROOM_SPOT_CHANNEL, int(at))
        x, z = cx * CHUNK + int(pick * CHUNK), cz * CHUNK + int(pick * CHUNK * CHUNK) % CHUNK
        if biome_at(x, z, seed) != "forest":
            continue
        y = terrain_height(x, z, seed) + 1
        cell = (x, y, z)
        if cell in avoid or grid.claimed(cell):
            continue
        if grid.material(x, y, z) == "air" and grid.material(x, y - 1, z) in FOREST_FLOOR:
            return cell
    return None


def mushrooms_in_chunk(grid: Grid, seed: str, chunk: tuple[int, int]) -> int:
    """Mushrooms standing on the chunk's surface."""
    cx, cz = chunk
    return sum(1 for x in range(cx * CHUNK, cx * CHUNK + CHUNK) for z in range(cz * CHUNK, cz * CHUNK + CHUNK)
               if grid.material(x, terrain_height(x, z, seed) + 1, z) in nature.MUSHROOMS)


def respawn_mushroom(db: sqlite3.Connection, grid: Grid, seed: str, picked: Cell, kind: str, at: float,
                     scale: float, chosen: set[Cell]) -> None:
    """Schedule a mushroom on forest floor in the picked one's chunk: a game day after the latest
    one already coming there, so a chunk regrows at most one per game day. A spot already
    scheduled in the chunk, or already claimed earlier in `chosen` this batch, is avoided so two
    picks in the same chunk in one call get different cells; `chosen` is updated in place."""
    chunk = (picked[0] // CHUNK, picked[2] // CHUNK)
    x0, z0 = chunk[0] * CHUNK, chunk[1] * CHUNK
    rows = db.execute("SELECT x, y, z, ready_at FROM growth WHERE block IN (?, ?) AND x BETWEEN ? AND ? "
                      "AND z BETWEEN ? AND ?", (*nature.MUSHROOMS, x0, x0 + CHUNK - 1, z0, z0 + CHUNK - 1)).fetchall()
    avoid = chosen | {(row[0], row[1], row[2]) for row in rows}
    spot = forest_floor(grid, seed, chunk, at, avoid)
    if spot is None:
        return
    chosen.add(spot)
    ready_at = later(at, MUSHROOM_RESPAWN, scale)
    if rows:
        ready_at = max(ready_at, later(max(row[3] for row in rows), MUSHROOM_RESPAWN, scale))
    schedule(db, spot, kind, ready_at, keep_earlier=True)


def react(db: sqlite3.Connection, grid: Grid, state: dict, changes: list[tuple[Cell, str, str]], at: float,
          scale: float) -> None:
    """Schedule what the changed blocks will turn into."""
    seed = state.get("world_seed", "0")
    chosen: set[Cell] = set()
    for cell, before, after in changes:
        x, y, z = cell
        grown = nature.next_stage(after)
        if before == LOG and after != LOG:
            for leaf in orphaned_leaves(grid, cell):
                schedule(db, leaf, "air", later(at, decay_seconds(seed, leaf, at), scale), keep_earlier=True)
        if before in nature.MUSHROOMS and after == "air":
            respawn_mushroom(db, grid, seed, cell, before, at, scale, chosen)
        if after == "sapling":
            schedule(db, cell, LOG, later(at, SAPLING_GROWS, scale))
        elif after == "berry_bush":
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
    elif block == LOG:
        if here == "sapling":
            trunk, canopy = tree_cells(cell)
            if tree_fits(grid, cell) and not kept_clear(db, state, cell).intersection(trunk + canopy):
                grow_tree(grid, cell)
                events.append((ready_at, "grow", "A sapling grew into a tree."))
            else:
                schedule(db, cell, LOG, later(ready_at, SAPLING_RETRY, scale))
    elif block == "air":
        if here == "leaves" and not leaf_supported(grid, cell):
            grid.put(*cell, "air")
            decay(state, cell, ready_at)
    elif block in nature.MUSHROOMS:
        seed = state.get("world_seed", "0")
        if (here == "air" and grid.material(x, y - 1, z) in FOREST_FLOOR and not grid.claimed(cell)
                and mushrooms_in_chunk(grid, seed, (x // CHUNK, z // CHUNK)) < MUSHROOM_CAP):
            grid.put(*cell, block)


def pet_cell(state: dict) -> Cell:
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def kept_clear(db: sqlite3.Connection, state: dict, sapling: Cell) -> set[Cell]:
    """Cells a tree grown from `sapling` must leave open: Mimo's cell and the one above its head,
    and each home or shelter near enough for the canopy to reach, with the cell above it."""
    stands = [pet_cell(state)] + [cell_of(place) for place in places(db, SHELTER_KINDS, around=sapling,
                                                                     reach=CANOPY_REACH)]
    return {(x, y + dy, z) for x, y, z in stands for dy in (0, 1)}


def decay(state: dict, leaf: Cell, at: float) -> None:
    """A leaf decayed: Mimo gathers what it dropped if it is near, and the viewer gets a puff."""
    position = state["position"]
    if math.hypot(leaf[0] - position["x"], leaf[2] - position["z"]) <= DROP_REACH:
        for item in nature.chance_drops(state.get("world_seed", "0"), leaf, "leaves"):
            add_item(state["inventory"], item)
    puff = {"x": leaf[0], "y": leaf[1], "z": leaf[2], "at": round(at, 3)}
    state["decays"] = [*state.get("decays", []), puff][-DECAYS_KEPT:]


def put_off(db: sqlite3.Connection, entry: Entry, at: float, scale: float) -> None:
    """An entry whose apply crashed: try it again FAILED_RETRY game seconds after `at`, so the same
    catch-up does not retry it, and drop it after its FAILED_LIMIT-th crash."""
    cell, _, ready_at = entry
    db.execute("UPDATE growth SET failures = COALESCE(failures, 0) + 1, ready_at = ? "
               "WHERE x=? AND y=? AND z=? AND ready_at=?", (later(at, FAILED_RETRY, scale), *cell, ready_at))
    db.execute("DELETE FROM growth WHERE x=? AND y=? AND z=? AND failures >= ?", (*cell, FAILED_LIMIT))


def renew(state: dict, context, at: float) -> None:
    """The world's own changes up to `at` (see the module docstring). Needs the tick's database.

    Each due entry is applied and only then deleted, inside its own try/except: a crash in
    apply_entry (or the grid's write callback) is logged once and puts that row off for 10 game
    minutes (put_off), instead of losing the row's effect and half-applying the batch; after 5
    crashes the row is dropped. A row that fails is not retried within this same call, and the
    loop stops as soon as a pass consumes no row, so a row that keeps failing costs a few queries,
    not one per MAX_APPLIED. grid.take_changes() always runs (even if something above still slips
    through), so renewal's own writes are never left for the next call's react() to mistake for
    Mimo's.
    """
    db, grid = context.db, context.grid
    if db is None:
        return
    scale = context.clock_at(at)["time_scale"]
    try:
        react(db, grid, state, grid.take_changes(), at, scale)
        applied = 0
        failed: set[Cell] = set()
        while applied < MAX_APPLIED:
            consumed = 0
            for entry in due(db, at, MAX_APPLIED - applied):
                cell, _, ready_at = entry
                if cell not in failed:
                    try:
                        apply_entry(db, grid, state, entry, scale, context.events)
                        # Match ready_at too: apply_entry may have rescheduled a new entry at the
                        # same cell (a crop's next stage, a sapling's retry), and only the row we
                        # just consumed should go.
                        db.execute("DELETE FROM growth WHERE x=? AND y=? AND z=? AND ready_at=?", (*cell, ready_at))
                        consumed += 1
                    except Exception as error:
                        log_once(logger, "renewal entry", error)
                        failed.add(cell)
                        try:
                            put_off(db, entry, at, scale)
                        except Exception as error:
                            log_once(logger, "renewal retry", error)
                applied += 1
            if not consumed:
                break
    finally:
        grid.take_changes()  # renewal's own writes need no reaction
    nature.recover_fish(state, at, scale)
