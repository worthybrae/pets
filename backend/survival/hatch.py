"""Hatch the pending egg into a new life: new seed, spawn point, traits, name and world."""

from __future__ import annotations

import random
import time

from backend.survival.eggs import pick_name, roll_traits
from backend.survival.registry import LifeConflict, LifeRegistry
from backend.survival.spawn import find_spawn


def hatch(registry: LifeRegistry, rng: random.Random | None = None, timestamp: float | None = None) -> dict:
    rng = rng or random.Random()
    timestamp = time.time() if timestamp is None else timestamp
    if registry.active_life() is not None:
        raise LifeConflict("A pet is already alive")
    egg = registry.pending_egg(rng, timestamp)
    seed = str(rng.getrandbits(64))
    spawn = find_spawn(seed, rng)
    return registry.create_life(name=pick_name(rng, registry.names()), seed=seed, spawn=spawn,
                                born_at=timestamp, egg=egg, traits=roll_traits(egg, rng))
