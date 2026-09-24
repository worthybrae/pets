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

Fix round 2: those short steps call this many times a slice, and herd spawning plus every animal's
turn scale with how often it is called, not with the game time it covers -- so at that pace they
cost far more than the L1 budget expects. `fight_step=True` (passed from backend.survival.tick,
which knows whether a call is one of those short steps or the slice's one final call) skips
`populate` and loads only hostile rows (`Herd.near(..., kinds=...)`, fewer rows read and decoded),
so only hostiles act on a fight step; herd spawning and every animal's turn still run once a slice,
at the final call, the ordinary L1 cadence.

Followup fix: that final call still spent about 5.7 ms of the slice's budget on `populate` even
while a hostile chased Mimo through new chunks, animals it had no time to look at. `simulate` now
skips `populate` there too whenever a hostile is near (hostiles.hostile_near, the same reach
tick.py slices short steps for); the chunk spawns as soon as nothing hostile is close by.

The budget (spec L2: creatures and light checks at most 20 ms a slice on average) is per slice, one
60-game-second transaction, the catch-up cadence (backend.survival.tick.MAX_STEP_SECONDS). At the
worker's live 1x cadence, a transaction a real second, the same creatures cost about 1.3 ms a real
second.
"""

from __future__ import annotations

import heapq
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.survival.creatures.acts import Scene, act
from backend.survival.creatures.darkness import spawn_hostiles
from backend.survival.creatures.hostiles import hostile_near
from backend.survival.creatures.kinds import hostile_kinds, kind_of
from backend.survival.creatures.spawning import SIM_REACH, populate
from backend.survival.creatures.table import dead
from backend.survival.once import log_once

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

MAX_ACTS = 24  # animal turns in one call, one each at most
HOSTILE_ACTS = 32  # hostile turns in one call (L2)
TURNS_EACH = 3  # turns one hostile takes in one call at most (L2)
LATE = 2.0  # server seconds (at the normal pace) a hostile's turn may lag the call's time at most
DEAD_KEEP = 10.0  # server seconds a dead creature stays listed, for the viewer's puff
UNKNOWN_WAIT = 60.0  # server seconds a creature of a kind no longer registered waits between turns


def simulate(state: dict, context: ActionContext, at: float, fight_step: bool = False) -> None:
    """Spawn, clear away and move the creatures near Mimo up to `at`. Needs the tick's database.

    `fight_step` (fix round 2): a short 1-second step (backend.survival.tick, FIGHT_SLICE) taken
    only to see where a hostile near Mimo is now, not the slice's one ordinary call -- so herd
    spawning and every animal's turn are skipped, and only hostile rows are even loaded. Followup
    fix: even the slice's one ordinary call skips herd spawning (not the rest) while a hostile is
    near (hostile_near)."""
    grid = context.grid
    if context.db is None or grid.herd is None:
        return
    clock = context.clock_at(at)
    scene = Scene(grid, grid.herd, state.get("world_seed", "0"), state, at, context.action_scale,
                  events=context.events, clock=clock)
    scale = clock["time_scale"]
    x, _, z = scene.pet
    if fight_step:
        loaded = grid.herd.near(x, z, SIM_REACH, kinds=hostile_kinds())
    else:
        loaded = grid.herd.near(x, z, SIM_REACH)
        # Followup fix: while a hostile is near enough to reach Mimo (hostile_near, the same reach
        # tick.py slices short steps for), skip herd spawning too -- new chunks a flight runs into
        # cost about 5.7 ms of populate() a slice for herds that are beside the point while Mimo is
        # busy running or fighting. The chunk still spawns once nothing hostile is close by.
        if not hostile_near(grid, context.db, state):
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
    already-struck hostile unsaved and free to strike again next call. Fix round 2: a crashing
    `act` (a bad kind, a bad state) is caught around that one creature, logged once and backed off
    (`next_at = at + UNKNOWN_WAIT`), so it does not also cost every other queued creature its turn
    this call."""
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
            try:
                if act(creature, replace(scene, at=when) if hostile else scene) is None:
                    creature["next_at"] = at + UNKNOWN_WAIT
            except Exception as error:
                log_once(logger, "creature_act", error)
                creature["next_at"] = at + UNKNOWN_WAIT
                continue
            if (hostile and turns[number] < TURNS_EACH and not dead(creature)
                    and when < creature["next_at"] <= at):
                heapq.heappush(queue, (creature["next_at"], creature["next_at"], number, hostile, creature))
    finally:
        for creature in acted.values():
            scene.herd.save(creature)
