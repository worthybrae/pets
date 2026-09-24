"""What a life remembers, kept in its own world database: places, known recipes and facts.

Places are cells worth coming back to, each with the time it was found and last visited:
- home: the first sheltered spot Mimo found (until M5 builds a real one); only ever one
- shelter: other sheltered spots (one per 8 blocks, counting home)
- ore: an ore block Mimo saw, with its material as the note (exact cells)
- danger: a drop or lava Mimo refused to step into, the note says which (one per 2 blocks)
- water: a body of water Mimo swam in (one per 16 blocks)
- food: a patch of wild food Mimo picked from (one per 8 blocks), with data {"ripe": ripe plants
  it still had, "seen_at": when}
- fire: a campfire or furnace Mimo placed and left, the note says which (exact cells)
- farm: where Mimo tilled its first plot (one per 16 blocks)
A place's `data` is a JSON object that `update_place` merges into. Places are read in a bounded
box around a cell, since memory keeps growing. Recipes are the ones Mimo crafted or smelted
successfully; facts are things it learned, like that red mushrooms are poisonous.

M5: what Mimo built. The `structures` table keeps each structure it started (kind, name, anchor,
status "building" or "done", and its design as JSON) and `structure_cells` every cell the design
claims, with its part and block, so damage can be found and diggers leave it alone
(backend.survival.structures). When a shelter is done, `set_home` moves home into it, noted
"built" (BUILT); the old home is remembered as a shelter.

Where Mimo has been: `memory_explored` counts the visits to each 8x8-block patch of ground
(rx = x // 8, rz = z // 8) and keeps the time of the last one. The brain marks the patches along
every walk or swim and the patch Mimo stands in after any other step (backend.survival.exploring);
explore heads for the patches it has seen least, and the viewer's minimap greys out the rest.

A new life's world starts with empty tables: that is what "fresh start" wipes.
"""

from __future__ import annotations

import json
import math
import sqlite3

from backend.survival.grid import Cell

SHELTER_KINDS = ("home", "shelter")
# A new place this close to a known place of the listed kinds is that same place.
SAME_PLACE: dict[str, tuple[float, tuple[str, ...]]] = {
    "shelter": (8.0, SHELTER_KINDS),
    "danger": (2.0, ("danger",)),
    "water": (16.0, ("water",)),
    "food": (8.0, ("food",)),
    "farm": (16.0, ("farm",)),
}
PLACE_COLUMNS = ("kind", "x", "y", "z", "note", "found_at", "visited_at", "data")
PATCH = 8  # explored ground is remembered in patches of 8x8 blocks


def create_memory_tables(db: sqlite3.Connection) -> None:
    """Create the memory tables, or bring older ones up to date. Run it inside the caller's
    BEGIN IMMEDIATE; running it again changes nothing."""
    db.execute("CREATE TABLE IF NOT EXISTS memory_places (kind TEXT NOT NULL, x INTEGER NOT NULL, "
               "y INTEGER NOT NULL, z INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', found_at REAL NOT NULL, "
               "visited_at REAL, data TEXT NOT NULL DEFAULT '{}', PRIMARY KEY (kind, x, y, z))")
    if "data" not in {row[1] for row in db.execute("PRAGMA table_info(memory_places)")}:
        # Worlds from M3 remember their places without data.
        db.execute("ALTER TABLE memory_places ADD COLUMN data TEXT NOT NULL DEFAULT '{}'")
    db.execute("CREATE INDEX IF NOT EXISTS memory_places_by_column ON memory_places(x, z)")
    db.execute("CREATE TABLE IF NOT EXISTS memory_recipes (recipe TEXT PRIMARY KEY, learned_at REAL NOT NULL, "
               "uses INTEGER NOT NULL DEFAULT 1)")
    db.execute("CREATE TABLE IF NOT EXISTS memory_knowledge (subject TEXT NOT NULL, fact TEXT NOT NULL, "
               "learned_at REAL NOT NULL, PRIMARY KEY (subject, fact))")
    db.execute("CREATE TABLE IF NOT EXISTS structures (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, "
               "name TEXT NOT NULL, x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, status TEXT NOT NULL, "
               "started_at REAL NOT NULL, built_at REAL, data TEXT NOT NULL DEFAULT '{}')")
    db.execute("CREATE TABLE IF NOT EXISTS structure_cells (x INTEGER NOT NULL, y INTEGER NOT NULL, "
               "z INTEGER NOT NULL, structure INTEGER NOT NULL, part TEXT NOT NULL, block TEXT NOT NULL, "
               "PRIMARY KEY (x, y, z))")
    db.execute("CREATE INDEX IF NOT EXISTS structure_cells_by_column ON structure_cells(x, z)")
    db.execute("CREATE TABLE IF NOT EXISTS memory_explored (rx INTEGER NOT NULL, rz INTEGER NOT NULL, "
               "visits INTEGER NOT NULL, last_at REAL NOT NULL, PRIMARY KEY (rx, rz))")


def places(db: sqlite3.Connection, kinds: tuple[str, ...] | None = None, around: Cell | None = None,
           reach: float | None = None) -> list[dict]:
    """Remembered places, oldest first, as dicts with kind, x, y, z, note, found_at, visited_at and
    data. With `around` and `reach`, only the places in the square column of that reach around it."""
    clauses, params = [], []
    if kinds:
        clauses.append(f"kind IN ({','.join('?' * len(kinds))})")
        params.extend(kinds)
    if around is not None and reach is not None:
        box = math.ceil(reach)
        clauses.append("x BETWEEN ? AND ? AND z BETWEEN ? AND ?")
        params.extend((around[0] - box, around[0] + box, around[2] - box, around[2] + box))
    query = f"SELECT {','.join(PLACE_COLUMNS)} FROM memory_places"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    rows = db.execute(query + " ORDER BY found_at, rowid", params).fetchall()
    return [place_of(row) for row in rows]


def place_of(row) -> dict:
    place = dict(zip(PLACE_COLUMNS, tuple(row)))
    place["data"] = json.loads(place["data"] or "{}")
    return place


def update_place(db: sqlite3.Connection, kind: str, cell: Cell, data: dict) -> bool:
    """Merge `data` into what Mimo remembers about a place. False when it does not remember it."""
    row = db.execute("SELECT data FROM memory_places WHERE kind=? AND x=? AND y=? AND z=?", (kind, *cell)).fetchone()
    if row is None:
        return False
    merged = {**json.loads(row[0] or "{}"), **data}
    db.execute("UPDATE memory_places SET data=? WHERE kind=? AND x=? AND y=? AND z=?", (json.dumps(merged), kind, *cell))
    return True


def remember(db: sqlite3.Connection, kind: str, cell: Cell, at: float, note: str = "") -> bool:
    """Remember a place. False when it is already known: home is only ever one place, and a spot
    close to a known one (SAME_PLACE) counts as that one."""
    x, y, z = cell
    if kind == "home":
        if db.execute("SELECT 1 FROM memory_places WHERE kind='home'").fetchone():
            return False
    elif kind in SAME_PLACE:
        reach, kinds = SAME_PLACE[kind]
        box = math.ceil(reach)
        rows = db.execute(f"SELECT x,y,z FROM memory_places WHERE kind IN ({','.join('?' * len(kinds))}) "
                          "AND x BETWEEN ? AND ? AND z BETWEEN ? AND ?",
                          (*kinds, x - box, x + box, z - box, z + box)).fetchall()
        if any(math.dist(tuple(row), cell) <= reach for row in rows):
            return False
    cursor = db.execute("INSERT OR IGNORE INTO memory_places(kind,x,y,z,note,found_at) VALUES (?,?,?,?,?,?)",
                        (kind, x, y, z, note, at))
    return cursor.rowcount == 1


def forget(db: sqlite3.Connection, kind: str, cell: Cell) -> None:
    """Forget a place. A home Mimo built is never forgotten: only set_home moves it."""
    db.execute("DELETE FROM memory_places WHERE kind=? AND x=? AND y=? AND z=? "
               "AND NOT (kind='home' AND note=?)", (kind, *cell, BUILT))


def visit(db: sqlite3.Connection, cell: Cell, at: float, reach: int = 2) -> None:
    """Mark every place within `reach` cells (on each axis) of `cell` as visited now."""
    x, y, z = cell
    db.execute("UPDATE memory_places SET visited_at=? WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? "
               "AND z BETWEEN ? AND ?", (at, x - reach, x + reach, y - reach, y + reach, z - reach, z + reach))


def learn(db: sqlite3.Connection, recipe: str, at: float) -> bool:
    """Count a recipe Mimo used successfully. True the first time."""
    cursor = db.execute("INSERT OR IGNORE INTO memory_recipes(recipe, learned_at) VALUES (?, ?)", (recipe, at))
    if cursor.rowcount == 1:
        return True
    db.execute("UPDATE memory_recipes SET uses = uses + 1 WHERE recipe=?", (recipe,))
    return False


def known_recipes(db: sqlite3.Connection) -> list[str]:
    return [row[0] for row in db.execute("SELECT recipe FROM memory_recipes ORDER BY learned_at, recipe").fetchall()]


def know(db: sqlite3.Connection, subject: str, fact: str, at: float) -> bool:
    """Learn that `subject` is `fact` (red_mushroom is "poisonous"). True the first time."""
    cursor = db.execute("INSERT OR IGNORE INTO memory_knowledge(subject, fact, learned_at) VALUES (?, ?, ?)",
                        (subject, fact, at))
    return cursor.rowcount == 1


def known(db: sqlite3.Connection, fact: str) -> list[str]:
    """Every subject Mimo learned is `fact`, first learned first."""
    return [row[0] for row in db.execute("SELECT subject FROM memory_knowledge WHERE fact=? "
                                         "ORDER BY learned_at, subject", (fact,)).fetchall()]


# Where Mimo has been ---------------------------------------------------------------------------

Patch = tuple[int, int]


def patch_of(x: int, z: int) -> Patch:
    """The 8x8 patch of ground a column lies in."""
    return x // PATCH, z // PATCH


def mark_explored(db: sqlite3.Connection, patches, at: float, quiet_since: float | None = None) -> list[Patch]:
    """Count a visit to each distinct patch now (visits + 1, last_at = at): one upsert each. With
    `quiet_since`, a patch last visited after then is left as it is. Returns the patches visited for
    the first time, in the order given."""
    distinct = list(dict.fromkeys(patches))
    if not distinct:
        return []
    xs, zs = [rx for rx, _ in distinct], [rz for _, rz in distinct]
    seen = {tuple(row) for row in db.execute(
        "SELECT rx, rz FROM memory_explored WHERE rx BETWEEN ? AND ? AND rz BETWEEN ? AND ?",
        (min(xs), max(xs), min(zs), max(zs))).fetchall()}
    since = math.inf if quiet_since is None else quiet_since
    db.executemany("INSERT INTO memory_explored(rx, rz, visits, last_at) VALUES (?, ?, 1, ?) "
                   "ON CONFLICT(rx, rz) DO UPDATE SET visits = visits + 1, last_at = excluded.last_at "
                   "WHERE memory_explored.last_at <= ?",
                   [(rx, rz, at, since) for rx, rz in distinct])
    return [patch for patch in distinct if patch not in seen]


def explored(db: sqlite3.Connection, around: Cell, reach: float) -> dict[Patch, tuple[int, float]]:
    """{(rx, rz): (visits, last_at)} for the visited patches in the square of `reach` blocks around
    a cell. A world read before its schema update (an archive) has explored nothing."""
    low_x, low_z = patch_of(math.floor(around[0] - reach), math.floor(around[2] - reach))
    high_x, high_z = patch_of(math.ceil(around[0] + reach), math.ceil(around[2] + reach))
    try:
        rows = db.execute("SELECT rx, rz, visits, last_at FROM memory_explored "
                          "WHERE rx BETWEEN ? AND ? AND rz BETWEEN ? AND ?", (low_x, high_x, low_z, high_z)).fetchall()
    except sqlite3.OperationalError as error:
        if "no such table" not in str(error):
            raise
        return {}
    return {(row[0], row[1]): (row[2], row[3]) for row in rows}


def cell_of(place: dict) -> Cell:
    return place["x"], place["y"], place["z"]


def nearest(found: list[dict], here: Cell, kinds: tuple[str, ...], max_distance: float = math.inf) -> dict | None:
    """The closest remembered place of these kinds by horizontal distance, within `max_distance`."""
    best: tuple[float, dict] | None = None
    for place in found:
        if place["kind"] not in kinds:
            continue
        distance = math.hypot(place["x"] - here[0], place["z"] - here[2])
        if distance <= max_distance and (best is None or distance < best[0]):
            best = (distance, place)
    return best[1] if best else None


# What Mimo built (M5) -------------------------------------------------------------------------

BUILT = "built"  # the note on a home Mimo built itself
STRUCTURE_COLUMNS = ("id", "kind", "name", "x", "y", "z", "status", "started_at", "built_at", "data")


def set_home(db: sqlite3.Connection, cell: Cell, at: float, note: str = BUILT) -> None:
    """Make `cell` home, noted `note`: the shelter Mimo built. remember() never moves home, since
    the first sheltered spot stays home until Mimo builds a better one. The old home is
    remembered as a shelter."""
    old = db.execute("SELECT x, y, z FROM memory_places WHERE kind='home'").fetchone()
    db.execute("DELETE FROM memory_places WHERE kind='home'")
    if old is not None and tuple(old) != tuple(cell):
        db.execute("INSERT OR IGNORE INTO memory_places(kind,x,y,z,note,found_at) VALUES ('shelter',?,?,?,'',?)",
                   (*tuple(old), at))
    db.execute("DELETE FROM memory_places WHERE kind='shelter' AND x=? AND y=? AND z=?", tuple(cell))
    db.execute("INSERT INTO memory_places(kind,x,y,z,note,found_at) VALUES ('home',?,?,?,?,?)", (*cell, note, at))


def add_structure(db: sqlite3.Connection, kind: str, name: str, anchor: Cell, at: float, data: dict,
                  cells: list[tuple[Cell, str, str]]) -> int:
    """Remember a structure Mimo started building and the (cell, part, block) cells it claims."""
    cursor = db.execute("INSERT INTO structures(kind,name,x,y,z,status,started_at,data) VALUES (?,?,?,?,?,?,?,?)",
                        (kind, name, *anchor, "building", at, json.dumps(data)))
    number = cursor.lastrowid
    db.executemany("INSERT OR REPLACE INTO structure_cells(x,y,z,structure,part,block) VALUES (?,?,?,?,?,?)",
                   [(*cell, number, part, block) for cell, part, block in cells])
    return number


def structures(db: sqlite3.Connection, kinds: tuple[str, ...] | None = None) -> list[dict]:
    """Every structure Mimo started, oldest first, as dicts with its design decoded in `data`."""
    query, params = f"SELECT {','.join(STRUCTURE_COLUMNS)} FROM structures", []
    if kinds:
        query += f" WHERE kind IN ({','.join('?' * len(kinds))})"
        params.extend(kinds)
    rows = db.execute(query + " ORDER BY id", params).fetchall()
    found = []
    for row in rows:
        structure = dict(zip(STRUCTURE_COLUMNS, tuple(row)))
        structure["data"] = json.loads(structure["data"] or "{}")
        found.append(structure)
    return found


def finish_structure(db: sqlite3.Connection, number: int, at: float) -> None:
    db.execute("UPDATE structures SET status='done', built_at=? WHERE id=?", (at, number))
