"""Where creatures live: two tables in the world database, and `Herd`, the way to them.

`creatures(id, kind, x, y, z, heading, health, state, spawned_at, next_at)`, indexed on (x, z),
holds every creature: where it stands (the cell its last move ends in), which way it faces
(radians around +y, 0 facing +z, like the viewer), its health, when it spawned and when it acts
next. `state` is JSON: its pose ("idle", "walking", "grazing", "fleeing", "swimming" or "dead"),
its last move as a timed path, its home (the spawn cell it stays near), its home chunk, how many
times it has acted (`turn`, the salt of its rolls) and when it was last hurt, calmed, caught or
killed. `creature_chunks(cx, cz, herds, animals, spawned_at, empty_since)` notes each 16x16 chunk
whose herds have spawned: how many herds its roll gave it, how many of the land animals that
spawned there are alive, and since when they have all been gone
(backend.survival.creatures.spawning).

A Grid made by grid.world_grid carries a Herd over the same connection (`grid.herd`), so steps,
planners and the creature hook all reach creatures the way they reach blocks. Reads work on a
read-only connection; a world read before its schema update (an archive from before L1) has no
creatures table and reads as having no creatures. `create_creature_tables` runs with the other
world tables (world.create_world_tables); running it again changes nothing.
"""

from __future__ import annotations

import json
import math
import sqlite3

COLUMNS = ("id", "kind", "x", "y", "z", "heading", "health", "state", "spawned_at", "next_at")
CHUNK_COLUMNS = ("cx", "cz", "herds", "animals", "spawned_at", "empty_since")


def create_creature_tables(db: sqlite3.Connection) -> None:
    """Create the creature tables. Run it inside the caller's BEGIN IMMEDIATE."""
    db.execute("CREATE TABLE IF NOT EXISTS creatures (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, x REAL NOT NULL, "
               "y REAL NOT NULL, z REAL NOT NULL, heading REAL NOT NULL DEFAULT 0, health REAL NOT NULL, "
               "state TEXT NOT NULL DEFAULT '{}', spawned_at REAL NOT NULL, next_at REAL NOT NULL)")
    db.execute("CREATE INDEX IF NOT EXISTS creatures_by_column ON creatures(x, z)")
    db.execute("CREATE TABLE IF NOT EXISTS creature_chunks (cx INTEGER NOT NULL, cz INTEGER NOT NULL, "
               "herds INTEGER NOT NULL, animals INTEGER NOT NULL DEFAULT 0, spawned_at REAL NOT NULL, "
               "empty_since REAL, PRIMARY KEY (cx, cz))")


def missing_table(error: sqlite3.OperationalError) -> bool:
    return "no such table" in str(error)


def creature_of(row) -> dict:
    creature = dict(zip(COLUMNS, tuple(row)))
    creature["state"] = json.loads(creature["state"] or "{}")
    return creature


def cell_of(creature: dict) -> tuple[int, int, int]:
    """The cell a creature stands in (where its last move ends)."""
    return round(creature["x"]), round(creature["y"]), round(creature["z"])


def dead(creature: dict) -> bool:
    return creature["state"].get("pose") == "dead"


class Herd:
    """The creatures of one world through one connection (the tick's, or a reader's)."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def near(self, x: float, z: float, reach: float) -> list[dict]:
        """Every creature, dead or alive, within `reach` blocks (horizontally) of (x, z), by id."""
        box = math.ceil(reach)
        try:
            rows = self.db.execute(f"SELECT {','.join(COLUMNS)} FROM creatures WHERE x BETWEEN ? AND ? "
                                   "AND z BETWEEN ? AND ? ORDER BY id", (x - box, x + box, z - box, z + box)).fetchall()
        except sqlite3.OperationalError as error:
            if not missing_table(error):
                raise
            return []
        found = [creature_of(row) for row in rows]
        return [creature for creature in found if math.hypot(creature["x"] - x, creature["z"] - z) <= reach]

    def get(self, number: int) -> dict | None:
        try:
            row = self.db.execute(f"SELECT {','.join(COLUMNS)} FROM creatures WHERE id=?", (number,)).fetchone()
        except sqlite3.OperationalError as error:
            if not missing_table(error):
                raise
            return None
        return None if row is None else creature_of(row)

    def add(self, kind: str, cell: tuple[int, int, int], health: float, at: float, next_at: float,
            state: dict) -> dict:
        """A new creature standing in `cell`, facing +z."""
        cursor = self.db.execute("INSERT INTO creatures(kind,x,y,z,heading,health,state,spawned_at,next_at) "
                                 "VALUES (?,?,?,?,?,?,?,?,?)",
                                 (kind, *map(float, cell), 0.0, health, json.dumps(state), at, next_at))
        return self.get(cursor.lastrowid)

    def save(self, creature: dict) -> None:
        self.db.execute("UPDATE creatures SET x=?, y=?, z=?, heading=?, health=?, state=?, next_at=? WHERE id=?",
                        (creature["x"], creature["y"], creature["z"], creature["heading"], creature["health"],
                         json.dumps(creature["state"]), creature["next_at"], creature["id"]))

    def remove(self, number: int) -> None:
        self.db.execute("DELETE FROM creatures WHERE id=?", (number,))

    def chunks(self, low: tuple[int, int], high: tuple[int, int]) -> dict[tuple[int, int], dict]:
        """The noted chunks from `low` to `high` (cx, cz, both ends included), by (cx, cz)."""
        try:
            rows = self.db.execute(f"SELECT {','.join(CHUNK_COLUMNS)} FROM creature_chunks WHERE cx BETWEEN ? AND ? "
                                   "AND cz BETWEEN ? AND ?", (low[0], high[0], low[1], high[1])).fetchall()
        except sqlite3.OperationalError as error:
            if not missing_table(error):
                raise
            return {}
        return {(row[0], row[1]): dict(zip(CHUNK_COLUMNS, tuple(row))) for row in rows}

    def note_chunk(self, chunk: tuple[int, int], herds: int, animals: int, at: float) -> None:
        """Note that a chunk's herds spawned: `herds` rolled, `animals` land animals alive. A chunk
        whose roll gave herds but where none could stand is empty from now on."""
        self.db.execute("INSERT OR IGNORE INTO creature_chunks(cx, cz, herds, animals, spawned_at, empty_since) "
                        "VALUES (?, ?, ?, ?, ?, ?)", (*chunk, herds, animals, at,
                                                      at if herds > 0 and animals == 0 else None))

    def regained(self, chunk: tuple[int, int], animals: int, at: float) -> None:
        """A herd of `animals` came back to an empty chunk (none could stand: it waits again)."""
        self.db.execute("UPDATE creature_chunks SET animals=?, empty_since=? WHERE cx=? AND cz=?",
                        (animals, None if animals else at, *chunk))

    def lost(self, chunk, at: float) -> None:
        """A land animal from `chunk` died; when it was the last, the chunk is empty from `at`."""
        if not (isinstance(chunk, list) and len(chunk) == 2):
            return
        self.db.execute("UPDATE creature_chunks SET animals = MAX(0, animals - 1) WHERE cx=? AND cz=?", tuple(chunk))
        self.db.execute("UPDATE creature_chunks SET empty_since=? WHERE cx=? AND cz=? AND animals=0 "
                        "AND empty_since IS NULL", (at, *chunk))
