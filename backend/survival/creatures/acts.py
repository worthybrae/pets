"""What a creature does when its turn comes: the creature-action registry.

A CreatureAction is data, like a reflex: a name, a priority (lower is checked first), a `when`
check and an `act` that starts the creature's next move or pose and sets when it acts again
(`next_at`). `act(creature, scene)` runs the first action whose check holds. L1 registers:

- flee (10): a passive land animal within 6 blocks of Mimo while Mimo is hunting runs about 8
  blocks away from it at double speed, then stays calm for 8 seconds (it does not flee from a
  hunting Mimo again until then). A creature that is hit flees at once (backend.survival.creatures
  .combat calls `run_away`), whatever its calm.
- swim (20): a fish moves 1 or 2 cells through the water, then drifts 2 to 6 seconds.
- graze (30): three times in ten, a land animal lowers its head and grazes for 3 to 6 seconds.
- wander (40): otherwise, two times in three, it walks 1 to 3 blocks to random standable
  neighbours, staying within 12 blocks of its home (the cell it spawned in) or heading back to it,
  then pauses 1 to 4 seconds.
- idle (90): else it stands still for 2 to 5 seconds.

L2's hostile kinds register their chase and attack here the same way. Every duration is in
server seconds and is divided by the action scale (`Scene.pace`, MIMO_ACTION_SCALE), like Mimo's
own steps. Nothing here searches for a path or edits a block. L5: BARRIERS keep a creature from
some steps (hostiles from a warding lantern's reach).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from backend.survival.clock import is_night
from backend.survival.creatures.kinds import Kind, huntable, kind_of
from backend.survival.creatures.moves import move, roll, steps, where
from backend.survival.creatures.table import Herd, dead
from backend.survival.grid import Cell, Grid

FLEE_BLOCKS = 8
SCARE_REACH = 6.0
CALM_SECONDS = 8.0
FLEE_PAUSE = 0.5
LEASH = 12.0
GRAZE_CHANCE = 0.3
WANDER_CHANCE = 2 / 3
WANDER_MOST = 3
WANDER_PAUSE = (1.0, 4.0)
GRAZE_SECONDS = (3.0, 6.0)
IDLE_SECONDS = (2.0, 5.0)
SWIM_PAUSE = (2.0, 6.0)
# Roll channels: each choice rolls on its own channel.
GRAZE, WANDER, LENGTH, PAUSE, STEP = 40, 41, 42, 43, 50


@dataclass
class Scene:
    """What creatures act in at one moment: the world, Mimo, and the time."""

    grid: Grid
    herd: Herd
    seed: str
    state: dict  # Mimo's state: where it is and what it is doing (L2's attacks hurt it through here)
    at: float
    pace: float = 1.0  # MIMO_ACTION_SCALE: moves and pauses are this many times shorter
    # The tick's event list, always passed (never a throwaway), so what happens here is logged.
    events: list = field(kw_only=True)
    clock: dict = field(default_factory=dict, kw_only=True)  # L2: the game clock at `at`; {} reads as day at 1x

    @property
    def night(self) -> bool:
        return is_night(self.clock.get("phase", "day"))

    @property
    def scale(self) -> float:
        """Game seconds per server second (MIMO_TIME_SCALE)."""
        return float(self.clock.get("time_scale", 1.0))

    @property
    def pet(self) -> Cell:
        position = self.state["position"]
        return round(position["x"]), round(position["y"]), round(position["z"])

    @property
    def hunting(self) -> bool:
        return (self.state.get("brain") or {}).get("purpose") == "hunt"

    def roll(self, creature: dict, channel: int) -> float:
        return roll(self.seed, creature["id"], creature["state"].get("turn", 0), channel)

    def between(self, creature: dict, span: tuple[float, float], channel: int) -> float:
        """A duration from `span` (server seconds at the normal pace), divided by the pace."""
        low, high = span
        return (low + (high - low) * self.roll(creature, channel)) / self.pace


@dataclass(frozen=True)
class CreatureAction:
    name: str
    priority: int
    when: Callable[[dict, Kind, Scene], bool]
    act: Callable[[dict, Kind, Scene], None]


CREATURE_ACTIONS: list[CreatureAction] = []
# L5: functions (scene, kind, cell, step) that bar a creature of `kind` from stepping from `cell` to
# `step` (backend.survival.frontier_gear: hostiles keep away from a warding lantern). Wandering and
# chasing (backend.survival.creatures.hostiles) ask `barred`.
BARRIERS: list = []


def barred(scene: Scene, creature: dict, cell: Cell, step: Cell) -> bool:
    kind = kind_of(creature["kind"])
    return kind is not None and any(barrier(scene, kind, cell, step) for barrier in BARRIERS)


def register_action(action: CreatureAction) -> CreatureAction:
    """Add an action (or replace the one with the same name), keeping the list in priority order."""
    CREATURE_ACTIONS[:] = sorted([known for known in CREATURE_ACTIONS if known.name != action.name] + [action],
                                 key=lambda known: known.priority)
    return action


def act(creature: dict, scene: Scene) -> str | None:
    """Run the first registered action whose check holds, count the turn and return its name.
    A dead creature, or one of a kind no longer registered, does nothing."""
    kind = kind_of(creature["kind"])
    if kind is None or dead(creature):
        return None
    for action in CREATURE_ACTIONS:
        if action.when(creature, kind, scene):
            action.act(creature, kind, scene)
            creature["state"]["turn"] = creature["state"].get("turn", 0) + 1
            return action.name
    return None


def flat_distance(a: Cell, b: Cell) -> float:
    return math.hypot(a[0] - b[0], a[2] - b[2])


def pause(creature: dict, scene: Scene, pose: str, span: tuple[float, float], channel: int) -> None:
    """Stand still in `pose` for a while (the last move stays in the state, finished)."""
    creature["state"]["pose"] = pose
    creature["next_at"] = scene.at + scene.between(creature, span, channel)


# flee ------------------------------------------------------------------------------------------

def run_away(creature: dict, kind: Kind, scene: Scene, danger: Cell) -> None:
    """Run up to FLEE_BLOCKS blocks away from `danger` at double speed, each step to the neighbour
    farthest from it, stopping when none gets farther; then stay calm for CALM_SECONDS."""
    cell, cells = where(creature, scene.at), []
    for _ in range(FLEE_BLOCKS):
        options = [step for step in steps(scene.grid, cell, kind.water) if step not in cells]
        if not options:
            break
        best = max(options, key=lambda step: flat_distance(step, danger))
        if flat_distance(best, danger) <= flat_distance(cell, danger):
            break
        cells.append(best)
        cell = best
    ends = move(creature, cells, scene.at, kind.speed / 2 / scene.pace, "fleeing")
    creature["next_at"] = ends + FLEE_PAUSE / scene.pace
    creature["state"]["calm_until"] = ends + CALM_SECONDS / scene.pace


def scared(creature: dict, kind: Kind, scene: Scene) -> bool:
    return (huntable(kind) and scene.hunting and scene.at >= creature["state"].get("calm_until", -math.inf)
            and flat_distance(where(creature, scene.at), scene.pet) <= SCARE_REACH)


register_action(CreatureAction("flee", 10, scared, lambda creature, kind, scene: run_away(creature, kind, scene,
                                                                                           scene.pet)))


# swim ------------------------------------------------------------------------------------------

def swim(creature: dict, kind: Kind, scene: Scene) -> None:
    cell, cells = where(creature, scene.at), []
    for number in range(1 + int(scene.roll(creature, LENGTH) * 2)):
        options = [step for step in steps(scene.grid, cell, True) if step not in cells]
        if not options:
            break
        cell = options[int(scene.roll(creature, STEP + number) * len(options))]
        cells.append(cell)
    ends = move(creature, cells, scene.at, kind.speed / scene.pace, "swimming")
    creature["next_at"] = ends + scene.between(creature, SWIM_PAUSE, PAUSE)


register_action(CreatureAction("swim", 20, lambda creature, kind, scene: kind.water, swim))


# graze -----------------------------------------------------------------------------------------

register_action(CreatureAction(
    "graze", 30, lambda creature, kind, scene: not kind.water and scene.roll(creature, GRAZE) < GRAZE_CHANCE,
    lambda creature, kind, scene: pause(creature, scene, "grazing", GRAZE_SECONDS, PAUSE)))


# wander ----------------------------------------------------------------------------------------

def height_of(creature: dict) -> int:
    """L2: the cells of room a creature of this kind needs to pass."""
    kind = kind_of(creature["kind"])
    return 1 if kind is None else kind.height


def wander_cells(creature: dict, scene: Scene) -> list[Cell]:
    """1 to 3 random steps, each to a standable neighbour within LEASH blocks of home, or the one
    nearest home when it has strayed beyond (a flee can take it past the leash)."""
    home = tuple(creature["state"].get("home") or where(creature, scene.at))
    cell, cells = where(creature, scene.at), []
    for number in range(1 + int(scene.roll(creature, LENGTH) * WANDER_MOST)):
        options = [step for step in steps(scene.grid, cell, False, height_of(creature))
                   if step not in cells and not barred(scene, creature, cell, step)]
        near = [step for step in options if flat_distance(step, home) <= LEASH]
        if not near and options:
            near = [min(options, key=lambda step: (flat_distance(step, home), step))]
        if not near:
            break
        cell = near[int(scene.roll(creature, STEP + number) * len(near))]
        cells.append(cell)
    return cells


def wander(creature: dict, kind: Kind, scene: Scene) -> None:
    cells = wander_cells(creature, scene)
    if not cells:
        pause(creature, scene, "idle", IDLE_SECONDS, PAUSE)
        return
    ends = move(creature, cells, scene.at, kind.speed / scene.pace, "walking")
    creature["next_at"] = ends + scene.between(creature, WANDER_PAUSE, PAUSE)


register_action(CreatureAction(
    "wander", 40, lambda creature, kind, scene: not kind.water and scene.roll(creature, WANDER) < WANDER_CHANCE,
    wander))


# idle ------------------------------------------------------------------------------------------

register_action(CreatureAction("idle", 90, lambda creature, kind, scene: True,
                               lambda creature, kind, scene: pause(creature, scene, "idle", IDLE_SECONDS, PAUSE)))
