"""The bow: the shoot step (spec L2, "Bow").

A bow takes 3 sticks and 3 string (skitters drop string) at a crafting table; 1 flint, 1 stick
and 1 feather make 4 arrows there (backend.services.crafting). Flint comes from gravel: one mined
gravel in 8 drops one (backend.survival.nature).

shoot(creature): Mimo draws and looses an arrow at a creature up to 16 blocks away. It takes 1.0 s
and spends one arrow, hit or miss. Whether it hits is rolled when the step starts (from the world
seed, the creature and the time), so the viewer can show the arrow fly true or wide
(`hit` in the running step): a sure hit within 4 blocks, falling to one in two at 16. A hit
does 5 damage through the same blow a sword deals (creatures.combat.strike): a hit animal runs, a
hit hostile turns on Mimo, and a kill's drops go into Mimo's arms with a "hunt" or "fight" event
(creatures.combat.spoils). A creature that is gone or dead when the arrow lands, or that ran more
than a block past the bow's range, is missed, which is no failure. The step does not start
without a bow or an arrow ("missing_item") or with the creature out of range ("out_of_reach").
Like the attack step, it takes the tick's events (`takes_events`) for its Scene; the kill's own
event is its return value.
"""

from __future__ import annotations

import math

from backend.services.crafting import take_items
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.combat import LUNGE, spoils, strike, target_of
from backend.survival.creatures.moves import roll, where
from backend.survival.grid import Grid
from backend.survival.steps import StepFailed, StepKind, as_cell, as_point, register_step, seed_of

SHOOT_RANGE = 16.0
SHOOT_SECONDS = 1.0
ARROW_DAMAGE = 5.0
SURE_WITHIN = 4.0  # blocks within which an arrow always hits
WORST_CHANCE = 0.5  # the chance of a hit at the bow's full range
AIM = 95  # roll channel


def hit_chance(distance: float) -> float:
    """1 within SURE_WITHIN blocks, falling in a straight line to WORST_CHANCE at SHOOT_RANGE."""
    if distance <= SURE_WITHIN:
        return 1.0
    share = (distance - SURE_WITHIN) / (SHOOT_RANGE - SURE_WITHIN)
    return max(WORST_CHANCE, 1.0 - (1.0 - WORST_CHANCE) * share)


def start_shoot(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    _, creature = target_of(spec, grid)
    if state["inventory"].get("bow", 0) < 1:
        raise StepFailed("no bow to shoot with", "missing_item")
    if state["inventory"].get("arrow", 0) < 1:
        raise StepFailed("no arrows", "missing_item")
    there = where(creature, at)
    distance = math.dist(as_cell(state["position"]), there)
    if distance > SHOOT_RANGE:
        raise StepFailed("out of range", "out_of_reach")
    hit = roll(seed_of(state), creature["id"], int(at * 10), AIM) < hit_chance(distance)
    return {"kind": "shoot", "started_at": at, "ends_at": round(at + SHOOT_SECONDS / scale, 3),
            "target": as_point(there), "creature": creature["id"], "hit": hit, "pace": scale}


def finish_shoot(step: dict, state: dict, grid: Grid, at: float, events: list) -> tuple[str, str] | None:
    state["inventory"] = take_items(state["inventory"], {"arrow": 1})
    if not step.get("hit"):
        return None
    try:
        herd, creature = target_of(step, grid)
    except StepFailed:
        return None  # it died or went while the arrow flew
    if math.dist(as_cell(state["position"]), where(creature, at)) > SHOOT_RANGE + LUNGE:
        return None
    scene = Scene(grid, herd, seed_of(state), state, at, step.get("pace", 1.0), events=events)
    found = strike(scene, creature, ARROW_DAMAGE, as_cell(state["position"]))
    return None if found is None else spoils(state, creature, found, at)


register_step(StepKind("shoot", start_shoot, finish_shoot, "shooting", working=True, cell_field="target",
                       takes_events=True))
