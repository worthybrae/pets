"""The creature hook: what advance_world runs after each chunk of Mimo's actions (spec L1,
"Creature tick").

`simulate(state, context, at)` works only near Mimo. It reads the creatures within 48 blocks of
Mimo, spawns the herds of chunks Mimo came near and brings herds back to emptied ones
(backend.survival.creatures.spawning), clears away creatures that died more than DEAD_KEEP
seconds ago (the viewer has shown their puff by then), and lets each living one whose `next_at`
has come take one turn (backend.survival.creatures.acts), earliest first, at most MAX_ACTS in one
call. Creatures farther away stay put. Moves are written to the creature rows; nothing searches
for a path and no block changes, so a call costs a few queries and a few hundred cell lookups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival.creatures.acts import Scene, act
from backend.survival.creatures.spawning import SIM_REACH, populate
from backend.survival.creatures.table import dead

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

MAX_ACTS = 24  # creature turns in one call
DEAD_KEEP = 10.0  # server seconds a dead creature stays listed, for the viewer's puff
UNKNOWN_WAIT = 60.0  # server seconds a creature of a kind no longer registered waits between turns


def simulate(state: dict, context: ActionContext, at: float) -> None:
    """Spawn, clear away and move the creatures near Mimo up to `at`. Needs the tick's database."""
    grid = context.grid
    if context.db is None or grid.herd is None:
        return
    scene = Scene(grid, grid.herd, state.get("world_seed", "0"), state, at, context.action_scale, context.events)
    scale = context.clock_at(at)["time_scale"]
    x, _, z = scene.pet
    loaded = grid.herd.near(x, z, SIM_REACH)
    loaded += populate(scene, loaded, scale)
    for creature in loaded:
        if dead(creature) and at - creature["state"].get("dead_at", at) > DEAD_KEEP:
            grid.herd.remove(creature["id"])
    due = sorted((creature for creature in loaded if not dead(creature) and creature["next_at"] <= at),
                 key=lambda creature: (creature["next_at"], creature["id"]))
    for creature in due[:MAX_ACTS]:
        if act(creature, scene) is None:
            creature["next_at"] = at + UNKNOWN_WAIT
        grid.herd.save(creature)
