"""Hitting a creature: the attack step and what a blow does (spec L1, "Hunting").

attack(creature): Mimo swings at a creature within 2.5 blocks of it: 0.6 s with a bare hand for 1
damage, 0.5 s with a sword for 4 (wooden), 5 (stone) or 6 (iron); the best sword Mimo carries is
used. It works on any creature of any kind, so L2's fights use the same step. The step fails when
the creature is gone or dead ("gone") or out of reach when the swing starts ("out_of_reach").
It lands when the swing ends if the creature still lives and is within a block of that reach
(the lunge); one that ran off in the meantime is missed, which is no failure.

A blow (`strike`) takes health, marks the creature hurt (the viewer flashes it, knocks it back
and shows its health bar) and, for a kind that flees when hurt, sends it running from Mimo at
once. At 0 health it dies where it is: its move is cut at that moment, keeping the cells it
reached, so the viewer replays it running up to the spot where it fell. It stays listed a few
seconds as "dead" with what it dropped (the viewer's puff), its home chunk counts one animal
fewer, and its drops go straight into Mimo's arms, as far as the carry limit lets them (the
engine settles the inventory after the step, backend.survival.carrying). A kill sets
`state["hunted_at"]` and is a routine "hunt" event. Drops are rolled from the world seed and
the creature, so they never depend on how often the tick ran.
"""

from __future__ import annotations

import math

from backend.services.crafting import add_item
from backend.survival.creatures.acts import Scene, run_away
from backend.survival.creatures.kinds import Kind, kind_of
from backend.survival.creatures.moves import roll, where
from backend.survival.creatures.table import Herd, dead
from backend.survival.grid import Cell, Grid
from backend.survival.steps import StepFailed, StepKind, as_cell, as_point, label, register_step, seed_of

ATTACK_REACH = 2.5
LUNGE = 1.0  # a swing still lands on a creature this much farther away when it ends
HAND = (1.0, 0.6)  # damage and seconds of a blow without a sword
SWORDS = {"wooden_sword": 4.0, "stone_sword": 5.0, "iron_sword": 6.0}  # damage, weakest first
SWORD_SECONDS = 0.5
DROP_CHANNEL = 70


def weapon(inventory: dict) -> str | None:
    """The best sword Mimo carries, or None for a bare hand."""
    return max((sword for sword in SWORDS if inventory.get(sword, 0) > 0), key=SWORDS.get, default=None)


def blow(sword: str | None) -> tuple[float, float]:
    """The damage and seconds of a blow with `sword` (None: a bare hand)."""
    return (SWORDS[sword], SWORD_SECONDS) if sword in SWORDS else HAND


def drops_of(seed: str, creature: dict, kind: Kind) -> dict[str, int]:
    """What a dead creature drops: each (least, most) range or chance rolled on its own channel."""
    found = {}
    for index, (item, drop) in enumerate(sorted(kind.drops.items())):
        chance = roll(seed, creature["id"], 0, DROP_CHANNEL + index)
        if isinstance(drop, tuple):
            low, high = drop
            count = low + int(chance * (high - low + 1))
        else:
            count = 1 if chance < drop else 0
        if count > 0:
            found[item] = count
    return found


def reached(path: list[dict] | None, at: float) -> list[dict] | None:
    """The part of a move that is done by `at`: its start and each cell reached by then."""
    if not path:
        return None
    return [entry for entry in path if entry["at"] <= at] or path[:1]


def strike(scene: Scene, creature: dict, damage: float, source: Cell) -> dict[str, int] | None:
    """Hit a creature from `source`: take `damage` from its health and mark it hurt, then either
    kill it (returns its drops) or, for a kind that flees when hurt, send it running (returns
    None). The creature is saved."""
    kind = kind_of(creature["kind"])
    state = creature["state"]
    creature["health"] = max(0.0, creature["health"] - damage)
    state["hurt_at"] = scene.at
    if creature["health"] <= 0:
        found = drops_of(scene.seed, creature, kind) if kind is not None else {}
        cell = where(creature, scene.at)
        creature["x"], creature["y"], creature["z"] = map(float, cell)
        state.update(pose="dead", dead_at=scene.at, drops=sorted(found), path=reached(state.get("path"), scene.at))
        scene.herd.save(creature)
        if kind is not None and not kind.water and not kind.hostile:
            scene.herd.lost(state.get("chunk"), scene.at)
        return found
    if kind is not None and kind.flee_when_hurt:
        run_away(creature, kind, scene, source)
    elif kind is not None and kind.hostile:
        state["chasing"] = True  # L2: a hostile that is hit turns on Mimo
    scene.herd.save(creature)
    return None


def target_of(spec: dict, grid: Grid) -> tuple[Herd, dict]:
    number = spec.get("creature")
    if isinstance(number, bool) or not isinstance(number, int):
        raise StepFailed("bad step: creature")
    herd = grid.herd
    creature = herd.get(number) if herd is not None else None
    if creature is None or dead(creature):
        raise StepFailed("it got away", "gone")
    return herd, creature


def start_attack(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    _, creature = target_of(spec, grid)
    there = where(creature, at)
    if math.dist(as_cell(state["position"]), there) > ATTACK_REACH:
        raise StepFailed("out of reach", "out_of_reach")
    sword = weapon(state["inventory"])
    _, seconds = blow(sword)
    step = {"kind": "attack", "started_at": at, "ends_at": round(at + seconds / scale, 3), "target": as_point(there),
            "creature": creature["id"], "pace": scale}
    if sword is not None:
        step["weapon"] = sword
    return step


def finish_attack(step: dict, state: dict, grid: Grid, at: float, events: list) -> tuple[str, str] | None:
    herd, creature = target_of(step, grid)
    if math.dist(as_cell(state["position"]), where(creature, at)) > ATTACK_REACH + LUNGE:
        return None  # it ran off before the blow landed
    damage, _ = blow(step.get("weapon"))
    scene = Scene(grid, herd, seed_of(state), state, at, step.get("pace", 1.0), events=events)
    found = strike(scene, creature, damage, as_cell(state["position"]))
    if found is None:
        return None
    return spoils(state, creature, found, at)


def spoils(state: dict, creature: dict, found: dict[str, int], at: float) -> tuple[str, str]:
    """A kill's drops go into Mimo's arms (the engine settles them after the step) and its event
    comes back. A hostile creature (L2) is fought off: a "fight" event that is no hunt. Any other
    kill is a hunt and sets `state["hunted_at"]`. The event is the step's return value, which the
    engine logs."""
    for item, count in found.items():
        add_item(state["inventory"], item, count)
    kind = kind_of(creature["kind"])
    if kind is not None and kind.hostile:
        state["last_thought"] = f"That {label(creature['kind'])} won't bother me again."
        return "fight", f"{state['name']} fought off a {label(creature['kind'])}."
    state["last_thought"] = f"Got the {label(creature['kind'])}!"
    state["hunted_at"] = at
    return "hunt", f"{state['name']} hunted a {label(creature['kind'])}."


register_step(StepKind("attack", start_attack, finish_attack, "attacking", working=True, cell_field="target",
                       takes_events=True))
