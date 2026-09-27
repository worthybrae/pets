"""Harder enemies farther out (L5, "Frontier"): a hostile born in a danger ring is tougher.

A hostile that comes out in ring n (backend.survival.rings, measured where it is born) has
HEALTH_PER_LEVEL (35 %) more health a level and hits 1 harder for every two levels. From the frontier
(3) a gloomling or a skitter may be an elder: one in four at 3, one in two in the deep frontier, with
half as much health again and one more damage; the viewer draws it glowing faintly. Its state keeps
what the viewer and the drops need: "ring", "most" (its full health, for the health bar), "fiercer"
(the damage its blow adds) and "elder". Home ground (0) is untouched, so life near home plays as
before.

Two more things grow with the ring Mimo stands in: the cap on hostiles near it (darkness.HOSTILE_CAP,
8) by one a level, and Mimo's caution: from the far wilds (2) on it runs 5 health points sooner a
level (defense.FLEE_BELOW, 35) and stands its ground only from 5 points more (defense.FIGHT_FROM,
50), since each blow out there costs more.
All three register into the hooks darkness and defense keep for them.
"""

from __future__ import annotations

from backend.survival.creatures.acts import Scene
from backend.survival.creatures.darkness import BIRTHS, MORE_ROOM
from backend.survival.creatures.defense import CAUTION
from backend.survival.creatures.kinds import Kind
from backend.survival.creatures.moves import roll
from backend.survival.grid import Cell
from backend.survival.rings import DEEPEST, ring_at, ring_here
from backend.survival.situation import Situation

HEALTH_PER_LEVEL = 0.35
DAMAGE_EVERY = 2  # levels for each point of damage a blow adds
ELDERS = ("gloomling", "skitter")
ELDER_FROM = 3
ELDER_CHANCE = {3: 0.25, 4: 0.5}
ELDER_HEALTH = 1.5
ELDER_DAMAGE = 1.0
CAUTION_FROM = 2
CAUTION_PER_LEVEL = 5.0
ELDER_ROLL = 114  # roll channel


def level_of(scene: Scene, cell: Cell) -> int:
    return min(DEEPEST, ring_at(scene.state, cell[0], cell[2]))


def elder_roll(scene: Scene, cell: Cell) -> float:
    return roll(scene.seed, cell[0] * 7919 + cell[1] * 131 + cell[2], int(scene.at * scene.scale), ELDER_ROLL)


def toughen(scene: Scene, kind: Kind, cell: Cell, state: dict, health: float) -> float:
    """A hostile born in ring n: more health, a harder blow, maybe an elder (see the module docstring)."""
    level = level_of(scene, cell)
    if level <= 0 or not kind.hostile:
        return health
    fiercer = float(level // DAMAGE_EVERY)
    health *= 1.0 + HEALTH_PER_LEVEL * level
    if kind.name in ELDERS and elder_roll(scene, cell) < ELDER_CHANCE.get(level, 0.0):
        state["elder"] = True
        health *= ELDER_HEALTH
        fiercer += ELDER_DAMAGE
    health = round(health, 1)
    state.update(ring=level, most=health)
    if fiercer:
        state["fiercer"] = fiercer
    return health


def more_room(scene: Scene) -> int:
    """One more hostile near Mimo for each level of the ring it stands in."""
    return min(DEEPEST, ring_here(scene.state))


def caution(s: Situation) -> float:
    """Health points Mimo adds to its flee and fight lines in the ring it stands in."""
    level = min(DEEPEST, ring_here(s.state))
    return CAUTION_PER_LEVEL * (level - CAUTION_FROM + 1) if level >= CAUTION_FROM else 0.0


BIRTHS.append(toughen)
MORE_ROOM.append(more_room)
CAUTION.append(caution)
