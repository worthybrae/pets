"""What Mimo knows at one moment: its state, the world around it, the clock and its memory.

Purposes and reflexes read a Situation instead of the raw state. The tick builds one inside its
transaction (`in_tick`); the worker builds one from a read-only connection when it offers
choices (`from_db`). Memory is read at most once per Situation, and only when asked for.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable

from backend.survival import memory
from backend.survival.clock import DAY_SECONDS, clock_at, is_night
from backend.survival.grid import Cell, Grid, world_grid
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

DUSK = 2220.0
NIGHTFALL = 2400.0
PLACE_SIGHT = 256  # remembered places this far away (on each axis) are read; farther ones are not


@dataclass
class Situation:
    state: dict
    grid: Grid
    clock: dict
    at: float
    db: sqlite3.Connection | None = None
    # L2 followup fix: how many times shorter Mimo's steps are (MIMO_ACTION_SCALE), the same pacing
    # a reflex's cooldown uses (reflexes.reflex_hook), so a trigger that measures its own hysteresis
    # in action time (defense.fleeing) agrees with the cooldown instead of drifting from it when
    # time_scale and action_scale differ. from_db has no ActionContext to read it from, so it keeps
    # the default of 1 (nothing there is paced).
    action_scale: float = 1.0
    # What Mimo sensed, kept for this Situation: a purpose's check, facts, score and plan look once.
    memo: dict = field(default_factory=dict)

    def sensed(self, key: str, look: Callable[[], Any]) -> Any:
        """`look()` the first time `key` is asked for, then the same answer."""
        if key not in self.memo:
            self.memo[key] = look()
        return self.memo[key]

    @cached_property
    def places(self) -> list[dict]:
        return memory.places(self.db, around=self.here, reach=PLACE_SIGHT) if self.db is not None else []

    @cached_property
    def poisons(self) -> tuple[str, ...]:
        """Food Mimo learned is poisonous (it got sick eating it)."""
        return tuple(memory.known(self.db, "poisonous")) if self.db is not None else ()

    @cached_property
    def lessons(self) -> tuple[str, ...]:
        """L4b: the lessons Mimo learned (backend.survival.journal); what it knows unlocks work. W1: not the
        ones a gentle pet knew from the start (backend.survival.wild), which unlock nothing and never count."""
        if self.db is None:
            return ()
        start = set(memory.known(self.db, "born_knowing"))
        return tuple(lesson for lesson in memory.known(self.db, "lesson") if lesson not in start)

    @cached_property
    def recipes(self) -> list[str]:
        return memory.known_recipes(self.db) if self.db is not None else []

    @property
    def here(self) -> Cell:
        return as_cell(self.state["position"])

    @property
    def vitals(self) -> dict:
        return self.state["vitals"]

    @property
    def inventory(self) -> dict:
        return self.state["inventory"]

    @property
    def brain(self) -> dict:
        return ensure_brain(self.state)

    @property
    def seed(self) -> str:
        return self.state["world_seed"]

    @property
    def phase(self) -> str:
        return self.clock["phase"]

    @property
    def night(self) -> bool:
        return is_night(self.phase)

    @property
    def scale(self) -> float:
        return self.clock["time_scale"]

    def trait(self, name: str) -> float:
        """A trait from 0 to 100; 50 when the life has none (tests, older states)."""
        return float(self.state.get("traits", {}).get(name, 50))

    def count(self, *items: str) -> int:
        return sum(self.inventory.get(item, 0) for item in items)

    def distance(self, cell: Cell) -> float:
        return math.dist(self.here, cell)

    def seconds_to(self, seconds_into_day: float) -> float:
        """Game seconds until that time of day comes round (0 when it is now)."""
        return (seconds_into_day - self.clock["seconds_into_day"]) % DAY_SECONDS


def in_tick(state: dict, context: ActionContext, at: float) -> Situation:
    return Situation(state, context.grid, context.clock_at(at), at, context.db, context.action_scale)


def from_db(db: sqlite3.Connection, state: dict, at: float, scale: float) -> Situation:
    return Situation(state, world_grid(db, state["world_seed"]), clock_at(state["born_at"], at, scale), at, db)
