"""The hostile creatures and what they do (spec L2, "Hostile kinds" and "Hostile AI").

- gloomling: 20 health, slow (0.9 s a block), a blow of 3 every 1.2 s from 1.5 blocks. It walks
  dark ground at night and caves at any hour, and burns and fades under the open sky by day. It
  drops 0 to 2 gloom_dust (for lanterns or potions in L3).
- skitter: 12 health, fast (0.4 s a block), a blow of 2 every second. It lives in caves and other
  covered dark places, and fades when it is caught under the open sky by day. It drops 0 to 2
  string (a bow takes 3).
Neither runs from a blow (a hit one turns on Mimo instead) and neither is hunted. Both are kinds
in the registry and act through the creature-action registry, ahead of the animals' actions:
- sunlit (2): under the open sky by day (backend.survival.light.sky_open) a gloomling catches
  fire ("burning") and dies BURN_SECONDS later without drops; a skitter fades at once.
- strike (4): within its reach of a living Mimo, with nothing solid between them (`can_hit`: a
  blow does not go through a wall or round a roof's edge), once its cooldown has passed, it hits
  Mimo (backend.survival.creatures.harm) and waits out the cooldown; never while Mimo is inside
  its shelter (harm.sheltered).
- chase (6): within 16 blocks of Mimo (and no more than 4 above or below it, so what lives in a
  cave under Mimo's feet leaves it be), or 24 once it is after Mimo or was just hurt by it, it
  moves up to 2 blocks toward Mimo, each step to the neighbour nearest Mimo, never through a
  door, into anything Mimo built or, for a gloomling (2 cells tall), under a ceiling lower than
  that (creatures.moves.steps), so a hostile outside a finished shelter waits at the wall; but a
  claimed cell it cannot enter (a door, say) is not always one a blow cannot reach from outside
  it, so the alarm and `hostile_near` (backend.survival.tick's short slicing) use `harm.sheltered`
  (a room or passage cell) like `strike` does, not every claimed cell. The first to come after
  Mimo outside its shelter raises the alarm: an urgent "threat" choice and event, at most one
  every 5 game minutes, so a model picker (Jev) can react at once.
- prowl (25): otherwise it gives up the chase and wanders near where it spawned, or stands. One
  that has not come after Mimo for LOITER game seconds fades away, so the few hostiles about are
  the ones Mimo has to deal with, and new ones can come out where it is.
Spawning in the dark, the cap of 8 and despawning far away are backend.survival.creatures.darkness.
"""

from __future__ import annotations

import math
import sqlite3

from backend.survival.creatures.acts import (
    IDLE_SECONDS, PAUSE, WANDER, WANDER_CHANCE, CreatureAction, Scene, flat_distance, pause, register_action, wander,
)
from backend.survival.creatures.harm import hurt_pet, pet_alive, sheltered
from backend.survival.creatures.kinds import Kind, hostile_kinds, kind_of, register_kind
from backend.survival.creatures.moves import heading, move, steps, where
from backend.survival.creatures.table import dead
from backend.survival.grid import Cell, Grid
from backend.survival.light import sky_open
from backend.survival.triggers import ensure_brain, mark_trigger

CHASE_SIGHT = 16.0
GIVE_UP = 24.0
CHASE_STEPS = 2
ROUSED = 10.0  # server seconds after Mimo hurts a hostile that it chases Mimo from as far as GIVE_UP
BURN_SECONDS = 3.0
ALARM_GAP = 300.0  # game seconds between two "threat" choices
WAIT = (0.5, 1.5)  # seconds a chaser that cannot get closer waits before it looks again
CHASE_RISE = 4  # blocks above or below Mimo a hostile may be to come after it
LOITER = 120.0  # game seconds a hostile stays about without coming after Mimo

register_kind(Kind("gloomling", health=20.0, speed=0.9, size=1.7, hostile=True, damage=3.0, reach=1.5,
                   drops={"gloom_dust": (0, 2)}, flee_when_hurt=False, cooldown=1.2, burns=True, height=2))
register_kind(Kind("skitter", health=12.0, speed=0.4, size=0.6, hostile=True, damage=2.0, reach=1.5,
                   drops={"string": (0, 2)}, flee_when_hurt=False, cooldown=1.0))


# sunlit ----------------------------------------------------------------------------------------

def sunlit(creature: dict, kind: Kind, scene: Scene) -> bool:
    return kind.hostile and not scene.night and sky_open(scene.grid, scene.seed, where(creature, scene.at))


def vanish(creature: dict, scene: Scene) -> None:
    """Gone without a trace: dead now, with no drops (the viewer shows its puff)."""
    creature["x"], creature["y"], creature["z"] = map(float, where(creature, scene.at))
    creature["health"] = 0.0
    creature["state"].update(pose="dead", dead_at=scene.at, drops=[], path=None, chasing=False)


def fade(creature: dict, kind: Kind, scene: Scene) -> None:
    """A gloomling catches fire first and dies when its next turn comes; anything else fades now."""
    state = creature["state"]
    if kind.burns and state.get("burning_at") is None:
        state.update(pose="burning", burning_at=scene.at, chasing=False, path=None)
        creature["next_at"] = scene.at + BURN_SECONDS / scene.pace
        return
    vanish(creature, scene)


register_action(CreatureAction("sunlit", 2, sunlit, fade))


# strike ----------------------------------------------------------------------------------------

def can_hit(grid: Grid, cell: Cell, target: Cell, reach: float) -> bool:
    """`target` is within `reach` of `cell` and open to it: when the two cells differ along two
    axes (a diagonal), at least one of the corner cells between them is not solid."""
    if math.dist(cell, target) > reach:
        return False
    differ = [axis for axis in range(3) if cell[axis] != target[axis]]
    if len(differ) < 2:
        return True
    corners = [tuple(target[index] if index == axis else cell[index] for index in range(3)) for axis in differ]
    return any(not grid.solid(corner) for corner in corners)


def in_reach(creature: dict, kind: Kind, scene: Scene) -> bool:
    return can_hit(scene.grid, where(creature, scene.at), scene.pet, kind.reach)


def cooled(creature: dict, kind: Kind, scene: Scene) -> bool:
    return scene.at >= creature["state"].get("struck_at", -math.inf) + kind.cooldown / scene.pace


def strikes(creature: dict, kind: Kind, scene: Scene) -> bool:
    return (kind.hostile and kind.damage > 0 and pet_alive(scene.state) and in_reach(creature, kind, scene)
            and cooled(creature, kind, scene) and not sheltered(scene.herd.db, scene.pet))


def strike_pet(creature: dict, kind: Kind, scene: Scene) -> None:
    creature["heading"] = heading(where(creature, scene.at), scene.pet, creature["heading"])
    creature["state"].update(pose="attacking", struck_at=scene.at, chasing=True)
    hurt_pet(scene, kind.damage, kind.name)
    creature["next_at"] = scene.at + kind.cooldown / scene.pace


register_action(CreatureAction("strike", 4, strikes, strike_pet))


# chase -----------------------------------------------------------------------------------------

def chases(creature: dict, kind: Kind, scene: Scene) -> bool:
    if not kind.hostile or not pet_alive(scene.state):
        return False
    here = where(creature, scene.at)
    distance = flat_distance(here, scene.pet)
    if abs(here[1] - scene.pet[1]) > CHASE_RISE:
        return False
    state = creature["state"]
    roused = state.get("chasing") or scene.at - state.get("hurt_at", -math.inf) <= ROUSED / scene.pace
    return distance <= CHASE_SIGHT or (bool(roused) and distance <= GIVE_UP)


def hostile_near(grid: Grid, db: sqlite3.Connection | None, state: dict) -> bool:
    """A living hostile could come after Mimo now: one within CHASE_SIGHT across and CHASE_RISE up
    or down, while Mimo is not sheltered (a room or passage cell of a shelter it built) -- the
    same cell a blow cannot reach (harm.sheltered), so this agrees with `strikes` about what is
    safe. The tick then runs in short steps (backend.survival.tick)."""
    position = state["position"]
    x, y, z = round(position["x"]), round(position["y"]), round(position["z"])
    if grid.herd is None or (db is not None and sheltered(db, (x, y, z))):
        return False
    for creature in grid.herd.near(x, z, CHASE_SIGHT, kinds=hostile_kinds()):  # final fix wave: hostile rows only
        kind = kind_of(creature["kind"])
        if kind is not None and kind.hostile and not dead(creature) and abs(creature["y"] - y) <= CHASE_RISE:
            return True
    return False


def alarm(scene: Scene, kind: Kind) -> None:
    """The first hostile to come after Mimo outside its shelter (harm.sheltered, the same room or
    passage a blow cannot reach) asks for a new choice at once."""
    brain = ensure_brain(scene.state)
    last = brain.get("threat_at")
    if sheltered(scene.herd.db, scene.pet) or (last is not None and (scene.at - last) * scene.scale < ALARM_GAP):
        return
    brain["threat_at"] = scene.at
    mark_trigger(scene.state, "threat", scene.at, urgent=True)
    scene.events.append((scene.at, "threat", f"{scene.state['name']} saw a {kind.name.replace('_', ' ')} coming."))


def chase(creature: dict, kind: Kind, scene: Scene) -> None:
    """Up to CHASE_STEPS steps, each to the neighbour nearest Mimo, stopping in reach of it or when
    no step gets closer; with none, it waits (and keeps its stance when it is in reach)."""
    state = creature["state"]
    state["active_at"] = scene.at
    if not state.get("chasing"):
        state["chasing"] = True
        alarm(scene, kind)
    target = scene.pet
    cell, cells = where(creature, scene.at), []
    for _ in range(CHASE_STEPS):
        if can_hit(scene.grid, cell, target, kind.reach):
            break
        options = [step for step in steps(scene.grid, cell, kind.water, kind.height) if step not in cells]
        best = min(options, key=lambda step: (math.dist(step, target), step), default=None)
        if best is None or math.dist(best, target) >= math.dist(cell, target):
            break
        cells.append(best)
        cell = best
    if cells:
        creature["next_at"] = move(creature, cells, scene.at, kind.speed / scene.pace, "chasing")
        return
    creature["heading"] = heading(cell, target, creature["heading"])
    if can_hit(scene.grid, cell, target, kind.reach):
        state["pose"] = "attacking"
        creature["next_at"] = max(scene.at, state.get("struck_at", scene.at) + kind.cooldown / scene.pace)
        return
    pause(creature, scene, "idle", WAIT, PAUSE)


register_action(CreatureAction("chase", 6, chases, chase))


# prowl -----------------------------------------------------------------------------------------

def prowl(creature: dict, kind: Kind, scene: Scene) -> None:
    creature["state"]["chasing"] = False
    if (scene.at - creature["state"].get("active_at", creature["spawned_at"])) * scene.scale > LOITER:
        vanish(creature, scene)
    elif scene.roll(creature, WANDER) < WANDER_CHANCE:
        wander(creature, kind, scene)
    else:
        pause(creature, scene, "idle", IDLE_SECONDS, PAUSE)


register_action(CreatureAction("prowl", 25, lambda creature, kind, scene: kind.hostile, prowl))
