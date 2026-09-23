"""The life registry: one row per life in MIMO_DATA_DIR/lives.sqlite3 (default /data).

Life 1 is the legacy world at MIMO_DB_PATH. The first time the survival code starts it is
registered as retired. It is only ever read through read-only connections.
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.services.block_table import open_db
from backend.services.live_mimo import DEFAULT_DB
from backend.services.worldgen import LEGACY_WORLD_SEED
from backend.survival.eggs import roll_egg
from backend.survival.world import SurvivalWorld, new_survival_state

LIFE_COLUMNS = ("id", "name", "kind", "db_path", "seed", "spawn_x", "spawn_z", "born_at", "died_at",
                "cause", "egg", "traits")


class LifeConflict(RuntimeError):
    """A pet is already alive, so no egg can hatch."""


# Registry paths whose schema this process has already initialized, so building a
# `LifeRegistry` for a GET request does not take a write lock on every call.
_schema_ready: set[Path] = set()
_schema_lock = threading.Lock()


def data_dir() -> Path:
    return Path(os.environ.get("MIMO_DATA_DIR") or "/data")


def legacy_db_path() -> Path:
    return Path(os.environ.get("MIMO_DB_PATH") or DEFAULT_DB)


def read_legacy_life(path: Path) -> dict | None:
    """Name, seed, position, birth and traits of the legacy world, read without writing to it."""
    if not path.exists():
        return None
    try:
        with open_db(path, read_only=True) as db:
            row = db.execute("SELECT data FROM mimo_state WHERE id=1").fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    state = json.loads(row["data"])
    return {"name": state.get("name", "Mimo"), "seed": state.get("world_seed", LEGACY_WORLD_SEED),
            "x": round(state["position"]["x"]), "z": round(state["position"]["z"]),
            "born_at": state["born_at"], "traits": state.get("personality", {})}


def _life(row: sqlite3.Row) -> dict:
    life = {key: row[key] for key in LIFE_COLUMNS}
    life["egg"] = json.loads(life["egg"]) if life["egg"] else None
    life["traits"] = json.loads(life["traits"]) if life["traits"] else {}
    life["alive"] = life["died_at"] is None
    return life


class LifeRegistry:
    def __init__(self, directory: str | Path | None = None, legacy_path: str | Path | None = None,
                 timestamp: float | None = None):
        self.directory = Path(directory) if directory is not None else data_dir()
        self.legacy_path = Path(legacy_path) if legacy_path is not None else legacy_db_path()
        self.path = self.directory / "lives.sqlite3"
        self.directory.mkdir(parents=True, exist_ok=True)
        resolved = self.path.resolve()
        if resolved not in _schema_ready:
            with _schema_lock:
                if resolved not in _schema_ready:
                    self.initialize(time.time() if timestamp is None else timestamp)
                    _schema_ready.add(resolved)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with open_db(self.path) as connection:
            yield connection

    def initialize(self, timestamp: float) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS lives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('legacy', 'survival')),
                db_path TEXT NOT NULL,
                seed TEXT NOT NULL,
                spawn_x INTEGER NOT NULL,
                spawn_z INTEGER NOT NULL,
                born_at REAL NOT NULL,
                died_at REAL,
                cause TEXT,
                egg TEXT,
                traits TEXT NOT NULL)""")
            db.execute("CREATE TABLE IF NOT EXISTS pending_egg (id INTEGER PRIMARY KEY CHECK (id=1), "
                       "egg TEXT NOT NULL, rolled_at REAL NOT NULL)")
            if db.execute("SELECT COUNT(*) AS count FROM lives").fetchone()["count"]:
                return
            legacy = read_legacy_life(self.legacy_path)
            if legacy:
                # Retire today's Mimo as life 1. Its file stays where it is and is never written.
                db.execute("INSERT INTO lives(id,name,kind,db_path,seed,spawn_x,spawn_z,born_at,died_at,cause,egg,traits) "
                           "VALUES (1,?,'legacy',?,?,?,?,?,?,'retired',NULL,?)",
                           (legacy["name"], str(self.legacy_path.resolve()), legacy["seed"], legacy["x"], legacy["z"],
                            legacy["born_at"], timestamp, json.dumps(legacy["traits"])))

    def world_path(self, life: dict) -> Path:
        """Survival worlds are stored relative to the data directory; the legacy path is absolute."""
        path = Path(life["db_path"])
        return path if path.is_absolute() else self.directory / path

    def list_lives(self) -> list[dict]:
        with self.connect() as db:
            return [_life(row) for row in db.execute("SELECT * FROM lives ORDER BY id DESC").fetchall()]

    def get(self, life_id: int) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM lives WHERE id=?", (life_id,)).fetchone()
        return _life(row) if row else None

    def active_life(self) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM lives WHERE kind='survival' AND died_at IS NULL "
                             "ORDER BY id DESC LIMIT 1").fetchone()
        return _life(row) if row else None

    def last_life(self) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM lives ORDER BY id DESC LIMIT 1").fetchone()
        return _life(row) if row else None

    def names(self) -> set[str]:
        with self.connect() as db:
            return {row["name"] for row in db.execute("SELECT name FROM lives").fetchall()}

    def pending_egg(self, rng: random.Random, timestamp: float | None = None) -> dict:
        """The egg waiting to hatch. It is rolled once, then kept until it hatches."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT egg FROM pending_egg WHERE id=1").fetchone()
            if row:
                return json.loads(row["egg"])
            egg = roll_egg(rng)
            db.execute("INSERT INTO pending_egg(id, egg, rolled_at) VALUES (1, ?, ?)",
                       (json.dumps(egg), time.time() if timestamp is None else timestamp))
            return egg

    def create_life(self, *, name: str, seed: str, spawn: dict, born_at: float, egg: dict, traits: dict) -> dict:
        """Add a survival life and its world in one step, and use up the pending egg."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM lives WHERE kind='survival' AND died_at IS NULL").fetchone():
                raise LifeConflict("A pet is already alive")
            life_id = db.execute(
                "INSERT INTO lives(name,kind,db_path,seed,spawn_x,spawn_z,born_at,egg,traits) "
                "VALUES (?,'survival','',?,?,?,?,?,?)",
                (name, seed, spawn["x"], spawn["z"], born_at, json.dumps(egg), json.dumps(traits))).lastrowid
            relative = Path("lives") / f"{life_id}.sqlite3"
            SurvivalWorld.create(self.directory / relative, new_survival_state(
                name=name, seed=seed, spawn=spawn, born_at=born_at, traits=traits))
            db.execute("UPDATE lives SET db_path=? WHERE id=?", (str(relative), life_id))
            db.execute("DELETE FROM pending_egg")
            return _life(db.execute("SELECT * FROM lives WHERE id=?", (life_id,)).fetchone())

    def mark_dead(self, life_id: int, died_at: float, cause: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE lives SET died_at=?, cause=? WHERE id=? AND died_at IS NULL", (died_at, cause, life_id))
