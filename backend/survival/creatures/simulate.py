"""The creature hook: what advance_world runs after each chunk of Mimo's actions (spec L1,
"Creature tick").

`simulate(state, context, at)` works only near Mimo. It reads the creatures within 48 blocks of
Mimo, spawns the herds of chunks Mimo came near and brings herds back to emptied ones
(backend.survival.creatures.spawning) and, in the dark, hostile ones (L2,
backend.survival.creatures.darkness), clears away creatures that died more than DEAD_KEEP
seconds ago (the viewer has shown their puff by then), and lets each living one whose `next_at`
has come take one turn (backend.survival.creatures.acts), earliest first, at most MAX_ACTS in one
call. L2: a hostile takes each turn that comes due up to the call's time instead, at its own
`next_at` (at most LATE seconds behind the call), up to TURNS_EACH in one call, from a budget of
HOSTILE_ACTS of its own, so the animals never crowd it out. Near Mimo the tick runs in one-second
steps (backend.survival.tick), so there a gloomling strikes every 1.2 s; the cap keeps one that
was out of Mimo's sight when a long step began from walking up and striking within that step.
Creatures farther away stay put. Moves are written to the creature rows; nothing searches
for a path and no block changes, so a call costs a few queries and a few hundred cell lookups.
"""

from __future__ import annotations

import heapq
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.survival.creatures.acts import Scene, act
from backend.survival.creatures.darkness import spawn_hostiles
from backend.survival.creatures.kinds import kind_of
from backend.survival.creatures.spawning import SIM_REACH, populate
from backend.survival.creatures.table import dead

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

MAX_ACTS = 24  # animal turns in one call, one each at most
HOSTILE_ACTS = 32  # hostile turns in one call (L2)
TURNS_EACH = 3  # turns one hostile takes in one call at most (L2)
LATE = 2.0  # server seconds (at the normal pace) a hostile's turn may lag the call's time at most
DEAD_KEEP = 10.0  # server seconds a dead creature stays listed, for the viewer's puff
UNKNOWN_WAIT = 60.0  # server seconds a creature of a kind no longer registered waits between turns


def simulate(state: dict, context: ActionContext, at: float) -> None:
    """Spawn, clear away and move the creatures near Mimo up to `at`. Needs the tick's database."""
    grid = context.grid
    if context.db is None or grid.herd is None:
        return
    clock = context.clock_at(at)
    scene = Scene(grid, grid.herd, state.get("world_seed", "0"), state, at, context.action_scale,
                  events=context.events, clock=clock)
    scale = clock["time_scale"]
    x, _, z = scene.pet
    loaded = grid.herd.near(x, z, SIM_REACH)
    loaded += populate(scene, loaded, scale)
    loaded += spawn_hostiles(scene)
    for creature in loaded:
        if dead(creature) and at - creature["state"].get("dead_at", at) > DEAD_KEEP:
            grid.herd.remove(creature["id"])
    take_turns(scene, loaded)


def take_turns(scene: Scene, loaded: list[dict]) -> None:
    """The creatures in `loaded` whose turn has come take it, in order of how overdue each truly is
    (its raw `next_at`, not the clamp below): an animal once, at the scene's time; a hostile each
    turn that comes due up to then, at its own time, clamped to at most LATE seconds behind the
    call so one long-neglected hostile cannot walk up and strike within a single step (see the
    module docstring for the limits). Fix round 1: ordering on the clamped time alone let ties
    (every long-overdue creature clamps to the same floor) resolve by id forever, so the animals
    past MAX_ACTS never got a turn; the raw `next_at` breaks those ties by staleness instead, so
    every animal's turn comes eventually across calls. Each creature that acted is saved once, in a
    `finally` around the whole call (fix round 1: saving after every single turn, not just every
    creature, would cost a multi-turn hostile up to TURNS_EACH writes instead of one), so a crash
    partway through a call still keeps every earlier creature's turn and never leaves an
    already-struck hostile unsaved and free to strike again next call."""
    at, earliest = scene.at, scene.at - LATE / scene.pace
    left = {True: HOSTILE_ACTS, False: MAX_ACTS}
    queue = []
    for creature in loaded:
        if not dead(creature) and creature["next_at"] <= at:
            kind = kind_of(creature["kind"])
            hostile = kind is not None and kind.hostile
            queue.append((max(creature["next_at"], earliest), creature["next_at"], creature["id"], hostile,
                          creature))
    heapq.heapify(queue)
    turns: dict[int, int] = {}
    acted: dict[int, dict] = {}
    try:
        while queue:
            when, _, number, hostile, creature = heapq.heappop(queue)
            if left[hostile] <= 0:
                continue
            left[hostile] -= 1
            turns[number] = turns.get(number, 0) + 1
            acted[number] = creature
            if act(creature, replace(scene, at=when) if hostile else scene) is None:
                creature["next_at"] = at + UNKNOWN_WAIT
            if (hostile and turns[number] < TURNS_EACH and not dead(creature)
                    and when < creature["next_at"] <= at):
                heapq.heappush(queue, (creature["next_at"], creature["next_at"], number, hostile, creature))
    finally:
        for creature in acted.values():
            scene.herd.save(creature)
