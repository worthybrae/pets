"""Hatch the pending egg into a new life: new seed, spawn point, traits, name and world.

W1: a life hatches "wild" or "gentle" (backend.survival.wild). This function hatches gentle unless told
otherwise, so every test that hatches a pet measures what it always measured; the API hatches wild
(backend.api.lives)."""

from __future__ import annotations

import random
import time

from backend.survival.eggs import pick_name, roll_traits
from backend.survival.registry import LifeConflict, LifeRegistry
from backend.survival.spawn import find_spawn
from backend.survival.wild import DIFFICULTIES, GENTLE


def hatch(registry: LifeRegistry, rng: random.Random | None = None, timestamp: float | None = None,
          difficulty: str = GENTLE) -> dict:
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"A life is wild or gentle, not {difficulty!r}")
    rng = rng or random.Random()
    timestamp = time.time() if timestamp is None else timestamp
    if registry.active_life() is not None:
        raise LifeConflict("A pet is already alive")
    egg = registry.pending_egg(rng, timestamp)
    seed = str(rng.getrandbits(64))
    spawn = find_spawn(seed, rng)
    return registry.create_life(name=pick_name(rng, registry.names()), seed=seed, spawn=spawn,
                                born_at=timestamp, egg=egg, traits=roll_traits(egg, rng), difficulty=difficulty)
