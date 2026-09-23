"""The block table every world database shares: one row per edited cell, numbered by `seq`.

The legacy world (live_mimo.MimoStore) and every survival world (backend.survival.world) keep
their block edits here, so the viewer can page changes the same way for any life.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.services.blocks import is_plant
from backend.services.worldgen import base_material


@contextmanager
def open_db(path: str | Path, read_only: bool = False) -> Iterator[sqlite3.Connection]:
    """A connection that commits when the block succeeds. Read-only connections never write the file."""
    if read_only:
        connection = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True, timeout=10)
    else:
        connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    if not read_only:
        connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=10000")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def create_block_tables(db: sqlite3.Connection) -> None:
    """Create or migrate mimo_blocks and mimo_meta. Run it inside the caller's BEGIN IMMEDIATE."""
    db.execute("CREATE TABLE IF NOT EXISTS mimo_blocks (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, material TEXT NOT NULL, seq INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(x,y,z))")
    db.execute("CREATE TABLE IF NOT EXISTS mimo_meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
    if "seq" not in {row["name"] for row in db.execute("PRAGMA table_info(mimo_blocks)")}:
        # Worlds saved before block sync get sequence numbers in row order.
        db.execute("ALTER TABLE mimo_blocks ADD COLUMN seq INTEGER NOT NULL DEFAULT 0")
        db.execute("UPDATE mimo_blocks SET seq = rowid")
    db.execute("CREATE INDEX IF NOT EXISTS mimo_blocks_by_seq ON mimo_blocks(seq)")
    db.execute("INSERT OR IGNORE INTO mimo_meta(key, value) VALUES('blocks_seq', 0)")
    db.execute("UPDATE mimo_meta SET value = MAX(value, (SELECT COALESCE(MAX(seq), 0) FROM mimo_blocks)) WHERE key='blocks_seq'")


def write_block(db: sqlite3.Connection, x: int, y: int, z: int, material: str) -> int:
    """Every block write goes through here so viewers can fetch changes by seq."""
    db.execute("UPDATE mimo_meta SET value = value + 1 WHERE key='blocks_seq'")
    seq = db.execute("SELECT value FROM mimo_meta WHERE key='blocks_seq'").fetchone()["value"]
    db.execute("INSERT INTO mimo_blocks(x,y,z,material,seq) VALUES(?,?,?,?,?) "
               "ON CONFLICT(x,y,z) DO UPDATE SET material=excluded.material, seq=excluded.seq",
               (x, y, z, material, seq))
    return seq


def blocks_seq(db: sqlite3.Connection) -> int:
    return db.execute("SELECT value FROM mimo_meta WHERE key='blocks_seq'").fetchone()["value"]


def read_blocks_since(db: sqlite3.Connection, since: int, limit: int = 5000) -> dict:
    """Block changes after `since`, oldest first. Removed blocks come back as air."""
    limit = max(1, min(limit, 5000))
    # Read the latest seq first so a write landing mid-query is fetched next time.
    latest = blocks_seq(db)
    rows = db.execute("SELECT x,y,z,material,seq FROM mimo_blocks WHERE seq > ? AND seq <= ? "
                      "ORDER BY seq LIMIT ?", (since, latest, limit + 1)).fetchall()
    more = len(rows) > limit
    rows = rows[:limit]
    return {"seq": rows[-1]["seq"] if more else latest,
            "changes": [{"x": row["x"], "y": row["y"], "z": row["z"], "material": row["material"]} for row in rows],
            "more": more}


def resolve_block(x: int, y: int, z: int, seed: str, edits: dict[tuple[int, int, int], str]) -> str:
    """The material at a cell: its edit if any, else the natural block, with a natural
    plant resolved to air once the cell below it has been edited (dug out or built on)."""
    edit = edits.get((x, y, z))
    if edit is not None:
        return edit
    natural = base_material(x, y, z, seed)
    if is_plant(natural) and (x, y - 1, z) in edits:
        return "air"
    return natural


def material_in(db: sqlite3.Connection, x: int, y: int, z: int, seed: str) -> str:
    """Material at a cell, reading it and the cell below in one query for the plant rule."""
    rows = db.execute("SELECT y, material FROM mimo_blocks WHERE x=? AND z=? AND y IN (?, ?)",
                      (x, z, y, y - 1)).fetchall()
    edits = {(x, row["y"], z): row["material"] for row in rows}
    return resolve_block(x, y, z, seed, edits)
