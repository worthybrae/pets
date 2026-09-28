"""W2: the sky's reflexes (backend.survival.reflexes).

- flee_fire (25): a burning cell within FIRE_FLEE blocks of Mimo (backend.survival.storms): it runs away from
  the nearest, as flee runs from a hostile (creatures.defense.run_away), and chooses again where it stops.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.survival.creatures.defense import run_away
from backend.survival.reflexes import Reflex, register
from backend.survival.situation import Situation
from backend.survival.storms import fire_near

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

FIRE_FLEE = 2


def nearest_fire(s: Situation) -> tuple[int, int, int] | None:
    cells = [(entry["x"], entry["y"], entry["z"]) for entry in (s.state.get("sky") or {}).get("fires", ())]
    return min(cells, key=lambda cell: math.dist(cell, s.here)) if cells else None


def plan_flee_fire(s: Situation, context: ActionContext) -> list[dict]:
    fire = nearest_fire(s)
    return [] if fire is None else [run_away(s, fire)]


register(Reflex("flee_fire", 25, trigger=lambda s: fire_near(s.state, FIRE_FLEE), plan=plan_flee_fire,
                thought="Fire! I have to get away!", event="{name} ran from the fire.", cooldown=3.0,
                ends_purpose=True, paced=True))
