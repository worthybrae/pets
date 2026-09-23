"""A survival life's world database: the shared block table, Mimo's state and its events.

Each survival life has its own file (MIMO_DATA_DIR/lives/<id>.sqlite3). The single
survival_state row holds position, vitals, inventory, care budget and death as JSON.
Writers use `transaction()` so the worker's tick and the owner's actions never overwrite
each other.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.services.block_table import (
    blocks_seq, create_block_tables, material_in, open_db, read_blocks_since, write_block,
)
from backend.services.blocks import is_replaceable
from backend.services.crafting import BLOCKS, craft, smelt, take_items
from backend.services.worldgen import WORLD_MAX_Y, WORLD_MIN_Y, terrain_height
from backend.survival.vitals import START_VITALS

COORDINATE_LIMIT = 30_000
BLOCK_TYPES = set(BLOCKS) | {"air"}
STATION_REACH = 6
MACHINES = ("crafting_table", "furnace")
MACHINE_OFFSETS = ((2, 0), (0, 2), (-2, 0), (0, -2), (3, 0), (0, 3), (-3, 0), (0, -3))


class WorldMissing(RuntimeError):
    """The registry points at a world database file that does not exist."""


class LifeOver(RuntimeError):
    """The pet in this world has died, so it cannot be greeted, helped or cared for."""


# Paths whose schema is already known to exist, so a writable open does not re-run
# `create_world_tables` (and its `BEGIN IMMEDIATE`) on every request. One process only
# ever needs to do this once per path: either `SurvivalWorld.create()` just wrote it, or
# an earlier writable open in this process already ran the check.
_schema_ready: set[Path] = set()
_schema_lock = threading.Lock()


def _ensure_world_schema(path: Path) -> None:
    """Run schema setup for a writable open, at most once per path per process."""
    resolved = path.resolve()
    if resolved in _schema_ready:
        return
    with _schema_lock:
        if resolved in _schema_ready:
            return
        with open_db(path) as db:
            db.execute("BEGIN IMMEDIATE")
            create_world_tables(db)
        _schema_ready.add(resolved)


def new_survival_state(*, name: str, seed: str, spawn: dict, born_at: float, traits: dict) -> dict:
    return {
        "name": name,
        "world_seed": seed,
        "born_at": born_at,
        "traits": traits,
        "position": {"x": float(spawn["x"]), "y": float(spawn["y"]), "z": float(spawn["z"])},
        "vitals": dict(START_VITALS),
        "status": "idle",
        "last_thought": "Everything is new. I wonder what is out there.",
        "inventory": {},
        "last_tick_at": born_at,
        "last_hello_at": None,
        "care": {"day": None, "snack": 0, "bandage": 0},
        "died_at": None,
        "cause": None,
    }


def create_world_tables(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS survival_state (id INTEGER PRIMARY KEY CHECK (id=1), data TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS mimo_events (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL)")
    create_block_tables(db)


def read_state(db: sqlite3.Connection) -> dict:
    return json.loads(db.execute("SELECT data FROM survival_state WHERE id=1").fetchone()["data"])


def write_state(db: sqlite3.Connection, state: dict) -> None:
    db.execute("UPDATE survival_state SET data=? WHERE id=1", (json.dumps(state),))


def log_event(db: sqlite3.Connection, at: float, kind: str, text: str) -> None:
    db.execute("INSERT INTO mimo_events(at,kind,text) VALUES(?,?,?)", (at, kind, text))


def placed_near(db: sqlite3.Connection, position: dict, reach: float,
                materials: tuple[str, ...]) -> list[tuple[int, int, int, str]]:
    """Placed blocks of the given materials in the square column around `position`."""
    marks = ",".join("?" * len(materials))
    rows = db.execute(
        f"SELECT x,y,z,material FROM mimo_blocks WHERE material IN ({marks}) "
        "AND x BETWEEN ? AND ? AND z BETWEEN ? AND ?",
        (*materials, math.floor(position["x"] - reach), math.ceil(position["x"] + reach),
         math.floor(position["z"] - reach), math.ceil(position["z"] + reach))).fetchall()
    return [(row["x"], row["y"], row["z"], row["material"]) for row in rows]


class SurvivalWorld:
    def __init__(self, path: str | Path, read_only: bool = False):
        self.path = Path(path)
        self.read_only = read_only
        if not self.path.exists():
            raise WorldMissing(f"World database {self.path} is missing")
        if not read_only:
            _ensure_world_schema(self.path)
        with self.connect() as db:
            self.seed = read_state(db)["world_seed"]

    @classmethod
    def create(cls, path: str | Path, state: dict) -> "SurvivalWorld":
        """Write a new world file. A leftover file from a failed hatch is replaced, not reused."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open_db(path) as db:
            db.execute("BEGIN IMMEDIATE")
            create_world_tables(db)
            db.execute("INSERT OR REPLACE INTO survival_state(id, data) VALUES (1, ?)", (json.dumps(state),))
            if db.execute("SELECT 1 FROM mimo_events LIMIT 1").fetchone() is None:
                log_event(db, state["born_at"], "birth", f"{state['name']} hatched into a brand-new world.")
        with _schema_lock:
            _schema_ready.add(path.resolve())
        return cls(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with open_db(self.path, self.read_only) as connection:
            yield connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """One write transaction: read the state, change it and write it back, all or nothing."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def state(self) -> dict:
        with self.connect() as db:
            return read_state(db)

    def events(self, limit: int = 12) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,at,kind,text FROM mimo_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def blocks_seq(self) -> int:
        with self.connect() as db:
            return blocks_seq(db)

    def blocks_since(self, since: int, limit: int = 5000) -> dict:
        with self.connect() as db:
            return read_blocks_since(db, since, limit)

    def material_at(self, x: int, y: int, z: int) -> str:
        with self.connect() as db:
            return material_in(db, x, y, z, self.seed)

    def put_block(self, x: int, y: int, z: int, material: str) -> None:
        if (material not in BLOCK_TYPES or not WORLD_MIN_Y <= y <= WORLD_MAX_Y
                or abs(x) > COORDINATE_LIMIT or abs(z) > COORDINATE_LIMIT):
            raise ValueError("Invalid block position or material")
        with self.connect() as db:
            write_block(db, x, y, z, material)

    def greet(self, timestamp: float) -> dict:
        with self.transaction() as db:
            state = read_state(db)
            if state["died_at"] is not None:
                raise LifeOver(f"{state['name']} has died")
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + 5)
            state["last_hello_at"] = timestamp
            write_state(db, state)
            log_event(db, timestamp, "hello", f"You said hello to {state['name']}.")
            return {"mood": state["vitals"]["mood"], "noticed_at": timestamp}

    def owner_action(self, action: str, item: str, timestamp: float) -> dict:
        """The owner helps craft, place a workstation or smelt, with the legacy station rules."""
        with self.transaction() as db:
            state = read_state(db)
            if state["died_at"] is not None:
                raise LifeOver(f"{state['name']} has died")
            position = state["position"]
            stations = {material for x, _, z, material in placed_near(db, position, STATION_REACH, MACHINES)
                        if math.hypot(x - position["x"], z - position["z"]) <= STATION_REACH}
            if action == "craft":
                state["inventory"] = craft(state["inventory"], item, stations)
                message = f"You crafted {item.replace('_', ' ')} for {state['name']}."
            elif action == "place_machine":
                if item not in MACHINES:
                    raise ValueError("Only a crafting table or furnace can be placed here")
                inventory = take_items(state["inventory"], {item: 1})
                cell = self._machine_cell(db, position)
                write_block(db, *cell, item)
                state["inventory"] = inventory
                message = f"You placed {item.replace('_', ' ')} beside {state['name']}."
            elif action == "smelt":
                state["inventory"] = smelt(state["inventory"], item, stations)
                message = f"You smelted {item.replace('_', ' ')} for {state['name']}."
            else:
                raise ValueError("Unknown owner action")
            write_state(db, state)
            log_event(db, timestamp, "owner", message)
            return {"message": message, "inventory": state["inventory"]}

    def _machine_cell(self, db: sqlite3.Connection, position: dict) -> tuple[int, int, int]:
        px, pz = round(position["x"]), round(position["z"])
        for dx, dz in MACHINE_OFFSETS:
            x, z = px + dx, pz + dz
            y = terrain_height(x, z, self.seed) + 1
            here = material_in(db, x, y, z, self.seed)
            if is_replaceable(here) and here != "water":
                return x, y, z
        raise ValueError("No open block beside the pet for that machine")
