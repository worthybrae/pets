"""Creature seeds (spec L3): a rare seed that grows into an animal, the owner's "seeds that grow
creatures".

A creature seed drops, 1 in 60, from broken tall grass and decaying leaves (nature.CHANCE_DROPS).
Planted on grass (the plant step: nature.SEEDS and SOIL) it is a creature sprout, and a game day
later, through renewal's growth table (renewal.GROWERS), the sprout is gone and a passive land
animal stands in its cell: a kind that lives in the biome there (spawning's land_kinds, rolled from
the world seed and the cell; a rabbit where none does). It is tame: at home where it grew, it
counts toward no chunk's herds and Mimo never hunts it (backend.survival.creatures.hunting). While
24 land animals are already near, the sprout waits and tries again 10 game minutes later. A sprout
that was mined or built over grows nothing, and mining one gives its seed back (the block's drop).
"""

from __future__ import annotations

import sqlite3

from backend.services.worldgen import biome_at
from backend.survival import nature
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.kinds import KINDS, Kind, land_kinds
from backend.survival.creatures.spawning import LAND_CAP, SIM_REACH, passive
from backend.survival.creatures.table import dead
from backend.survival.grid import Cell, Grid
from backend.survival.renewal import Grower, later, register_grower, schedule

SEED = "creature_seed"
SPROUT = "creature_sprout"
MARKER = "animal"  # the growth table's entry for a sprout: an animal grows there
GROW_SECONDS = DAY_SECONDS
RETRY_SECONDS = 600.0  # game seconds a sprout waits while the land is full of animals
KIND_CHANNEL = 92
FIRST_TURN = 1.0  # server seconds before a new animal takes its first turn


def local_kind(seed: str, cell: Cell) -> Kind:
    """The passive land kind a sprout at `cell` grows into: one that lives in the biome there."""
    kinds = land_kinds(biome_at(cell[0], cell[2], seed)) or [KINDS["rabbit"]]
    return kinds[int(nature.roll(seed, cell, KIND_CHANNEL) * len(kinds))]


def hatch(db: sqlite3.Connection, grid: Grid, state: dict, cell: Cell, ready_at: float, scale: float,
          events: list) -> None:
    """The sprout at `cell` grows into a tame animal, or waits while the land is full."""
    herd = grid.herd
    if herd is None or grid.material(*cell) != SPROUT:
        return
    near = [creature for creature in herd.near(cell[0], cell[2], SIM_REACH)
            if not dead(creature) and passive(creature, False)]
    if len(near) >= LAND_CAP:
        schedule(db, cell, MARKER, later(ready_at, RETRY_SECONDS, scale))
        return
    kind = local_kind(state.get("world_seed", "0"), cell)
    grid.put(*cell, "air")
    herd.add(kind.name, cell, kind.health, ready_at, ready_at + FIRST_TURN,
             {"home": list(cell), "chunk": None, "pose": "idle", "turn": 0, "tame": True})
    events.append((ready_at, "grow", f"A creature seed grew into a {kind.name}."))


register_grower(SPROUT, Grower(MARKER, GROW_SECONDS, hatch))
