"""Reflexes: rules that take over at once, ahead of the purpose layer.

A Reflex is data: a name, a priority (lower is more urgent), a trigger, a planner, a thought, an
event line and a cooldown. The brain's interrupt hook (`reflex_hook`) checks them in priority
order before every step starts and while a walk, sleep or wait runs. The first whose trigger
holds and whose planner returns steps takes over:

- The first takeover sets the purpose's queue aside (a cut walk is queued again toward its
  target) and puts the reflex's steps in the queue, tagged with the reflex's name. A more urgent
  reflex can take over from a running one; a less urgent one waits. Preempting a different running
  reflex ends it there and then (its cooldown and quiet start from that moment), so it does not
  fire again the instant the one that cut it off lets go.
- When the reflex's steps run out, `end_reflex` brings the set-aside steps back, starts the
  reflex's cooldown and asks for a new choice (`reflex_ended`). The set-aside steps include the
  plan's cleanup steps (`keep`), which come back even when the purpose changed meanwhile. A
  reflex with `ends_purpose` (head_home) finishes the purpose instead of resuming it, keeping
  only the cleanup steps, so Mimo chooses again at home rather than walking back out.
- A veto reflex (avoid_drop) does not set anything aside: it fails or replaces only the step that
  would fall too far, even when it has no steps of its own.

M3 registers surface (10), avoid_drop (20), eat_now (40), warm_up (50), head_home (60) and
collapse (70). L2's flee (30) and fight (40) register themselves from
backend.survival.creatures.defense; a fight goes round after round, so a reflex may stay `quiet`
for a while after it ends and log its event once per encounter. M5: collapse lies down in a bed
within 8 blocks when there is one (and where it stands when the walk there fails), and head_home
leaves Mimo be while it builds its shelter or lights torches at home.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Callable

from backend.services.blocks import hardness, is_solid
from backend.services.crafting import can_harvest
from backend.services.worldgen import WORLD_MIN_Y
from backend.survival.actions import SAFE_FALL, ActionContext, as_started, fail, take_search
from backend.survival.beds import to_bed
from backend.survival.foraging import whole_walk
from backend.survival.grid import Cell, Grid
from backend.survival.memory import SHELTER_KINDS, cell_of, nearest, remember
from backend.survival.once import log_once
from backend.survival.pathing import find_path
from backend.survival.purposes import AT_HOME, HOME_RANGE, HOMEWARD, foods, home_of, meal, walk_to
from backend.survival.senses import near_failure
from backend.survival.situation import NIGHTFALL, Situation, in_tick
from backend.survival.steps import as_cell
from backend.survival.toolmaking import place_station, station_spots
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.vitals import EXHAUSTED_BELOW, WARM_BLOCKS, is_sheltered

logger = logging.getLogger(__name__)

SURFACE_BELOW = 40.0
EAT_NOW_BELOW = 15.0
EAT_NOW_FULL = 40.0
WARM_UP_BELOW = 25.0
SHORE_SEARCH = 2000
FIRE_STAND = 2.0
# Purposes that keep Mimo at its home at dusk (M5): head_home leaves them be.
AT_HOME_WORK = ("build_shelter", "light_up")


@dataclass(frozen=True)
class Reflex:
    name: str
    priority: int
    trigger: Callable[[Situation], bool]
    plan: Callable[[Situation, ActionContext], list[dict]]
    thought: str
    event: str  # "{name} ..." for the event log
    cooldown: float = 10.0  # real seconds before it may fire again after it ended
    veto: bool = False
    # When it ends, drop the purpose and its set-aside steps (but their cleanup), so the next
    # choice starts from where the reflex left Mimo instead of undoing it.
    ends_purpose: bool = False
    # L2: real seconds after it last ended during which a new takeover logs no event.
    quiet: float = 0.0


REFLEXES: list[Reflex] = []


def register(reflex: Reflex) -> Reflex:
    """Add a reflex (or replace the one with the same name), keeping the list in priority order."""
    REFLEXES[:] = sorted([known for known in REFLEXES if known.name != reflex.name] + [reflex],
                         key=lambda known: known.priority)
    return reflex


def by_name(name: str | None) -> Reflex | None:
    return next((reflex for reflex in REFLEXES if reflex.name == name), None)


# The hook --------------------------------------------------------------------------------------

def set_aside(state: dict) -> list[dict]:
    """The purpose's steps to resume later: a running walk again toward its target, then the queue."""
    kept = []
    action = state["action"]
    if action is not None and action["kind"] == "walk":
        target = action["target"]
        spec = {"kind": "walk", "target": [target["x"], target["y"], target["z"]], "reach": action["reach"]}
        if "purpose" in action:
            spec["purpose"] = action["purpose"]
        if action.get("whole"):
            spec["whole"] = True
        kept.append(spec)
    return kept + [dict(spec) for spec in state["queue"]]


def take_over(state: dict, reflex: Reflex, steps: list[dict], context: ActionContext, at: float) -> None:
    brain = ensure_brain(state)
    if reflex.veto:
        state["queue"] = steps
    else:
        if brain["reflex"] is None:
            brain["set_aside"] = set_aside(state)
        elif brain["reflex"] != reflex.name:
            # A different reflex was running: it ends here, so its cooldown and quiet start now
            # instead of never, which would let it fire again the moment this one lets go.
            brain["reflex_ends"][brain["reflex"]] = at
        state["queue"] = [{**step, "purpose": reflex.name} for step in steps]
        brain["reflex"] = reflex.name
    state["last_thought"] = reflex.thought
    if at - brain["reflex_ends"].get(reflex.name, -math.inf) >= reflex.quiet:
        context.events.append((at, "reflex", reflex.event.format(name=state["name"])))


def reflex_hook(state: dict, context: ActionContext, at: float) -> str | None:
    """The interrupt hook: the first reflex that fires takes over. Returns its name, or None."""
    brain = ensure_brain(state)
    running = by_name(brain["reflex"])
    s = in_tick(state, context, at)
    for reflex in REFLEXES:
        if running is not None and reflex.priority >= running.priority:
            break
        if at - brain["reflex_ends"].get(reflex.name, -math.inf) < reflex.cooldown:
            continue
        try:
            if not reflex.trigger(s):
                continue
            steps = reflex.plan(s, context)
        except Exception as error:
            log_once(logger, f"{reflex.name} reflex", error)
            continue
        if not steps and not reflex.veto:
            continue
        take_over(state, reflex, list(steps), context, at)
        return reflex.name
    return None


def end_reflex(state: dict, at: float) -> list[dict]:
    """The running reflex's steps ran out: start its cooldown, ask for a new choice and hand back
    the steps it set aside."""
    brain = ensure_brain(state)
    brain["reflex_ends"][brain["reflex"]] = at
    brain["reflex"] = None
    brain["handled_failure"] = state.get("last_failure")
    mark_trigger(state, "reflex_ended", at)
    resumed, brain["set_aside"] = brain["set_aside"], []
    return resumed


# surface ---------------------------------------------------------------------------------------

def plan_surface(s: Situation, context: ActionContext) -> list[dict]:
    """Mine a ceiling that holds Mimo under water, or swim to the nearest shore once afloat."""
    x, y, z = s.here
    if s.grid.water(s.here):
        ceiling = (x, y + 1, z)
        material = s.grid.material(*ceiling)
        if is_solid(material) and hardness(material) is not None and can_harvest(material, s.inventory):
            return [{"kind": "mine", "target": list(ceiling)}]
        return []  # open water above: the swim-up hazard already takes Mimo up
    if s.grid.swimming(s.here) and take_search(context):
        cells, found = find_path(s.grid, s.here, lambda cell: s.grid.standable(cell) and not s.grid.swimming(cell),
                                 s.here, max_nodes=SHORE_SEARCH)
        if found:
            return [walk_to(cells[-1])]
    return []


register(Reflex("surface", 10, trigger=lambda s: s.vitals["air"] < SURFACE_BELOW, plan=plan_surface,
                thought="I need air!", event="{name} swam for air.", cooldown=3.0))


# avoid_drop ------------------------------------------------------------------------------------

def fall_depth(grid: Grid, cell: Cell, removed: Cell | None = None) -> tuple[int, bool]:
    """How far Mimo would fall from `cell` (with `removed` gone), and whether it passes lava."""

    def holds(below: Cell) -> bool:
        if below == removed:
            return False
        material = grid.material(*below)
        return material == "water" or is_solid(material)

    x, y, z = cell
    lava = False
    while not holds((x, y - 1, z)) and y > WORLD_MIN_Y:
        y -= 1
        lava = lava or ((x, y, z) != removed and grid.material(x, y, z) == "lava")
    return cell[1] - y, lava


def too_far(grid: Grid, cell: Cell, removed: Cell | None = None) -> str | None:
    """"lava" or "drop" when falling from `cell` would hurt too much, else None."""
    blocks, lava = fall_depth(grid, cell, removed)
    if lava:
        return "lava"
    return "drop" if blocks > SAFE_FALL else None


def drop_ahead(s: Situation) -> tuple[str, Cell, str] | None:
    """("walk", cell, why) for the next cell of the running walk, or ("mine", cell, why) for a
    queued mine of the block under Mimo, when either would drop Mimo too far."""
    action = s.state["action"]
    if action is not None:
        if action["kind"] != "walk":
            return None
        upcoming = [entry for entry in action["path"] if entry["at"] > s.at]
        if not upcoming:
            return None
        cell = as_cell(upcoming[0])
        why = None if s.grid.supported(cell) else too_far(s.grid, cell)
        return ("walk", cell, why) if why else None
    if not s.state["queue"] or s.state["queue"][0].get("kind") != "mine":
        return None
    try:
        target = as_cell(s.state["queue"][0].get("target"))
    except ValueError:
        return None
    x, y, z = s.here
    if target != (x, y - 1, z):
        return None
    why = too_far(s.grid, s.here, removed=target)
    return ("mine", target, why) if why else None


def plan_avoid_drop(s: Situation, context: ActionContext) -> list[dict]:
    """Fail a mine that would drop Mimo too far, or walk again around a cell that lost its floor."""
    found = drop_ahead(s)
    if found is None:
        return []
    what, cell, why = found
    if context.db is not None:
        remember(context.db, "danger", cell, s.at, why)
    if what == "mine":
        spec = s.state["queue"].pop(0)  # popped first: a vetoed step must never be kept
        fail(s.state, as_started(spec, s.at), s.at, "that would be a long fall", "blocked")
        return list(s.state["queue"])  # the plan's cleanup steps, which fail() kept
    action = s.state["action"]
    target = action["target"]
    again = {"kind": "walk", "target": [target["x"], target["y"], target["z"]], "reach": action["reach"]}
    if "purpose" in action:
        again["purpose"] = action["purpose"]
    if action.get("whole"):
        again["whole"] = True
    return [again, *s.state["queue"]]


register(Reflex("avoid_drop", 20, trigger=lambda s: drop_ahead(s) is not None, plan=plan_avoid_drop,
                thought="Whoa, that's a long way down.", event="{name} stopped at the edge of a long drop.",
                cooldown=0.0, veto=True))


# eat_now ---------------------------------------------------------------------------------------

register(Reflex("eat_now", 40,
                trigger=lambda s: s.vitals["hunger"] < EAT_NOW_BELOW and bool(foods(s.inventory, s.poisons)),
                plan=lambda s, context: meal(s.inventory, s.vitals["hunger"], EAT_NOW_FULL, s.poisons),
                thought="I'm starving. I have to eat now.", event="{name} ate in a hurry.", cooldown=5.0))


# warm_up ---------------------------------------------------------------------------------------

def plan_warm_up(s: Situation, context: ActionContext) -> list[dict]:
    """Light a carried campfire beside Mimo (or place a carried furnace, which warms the same), else
    walk to the nearest known warm spot: a shelter, or a campfire or furnace within 64 blocks.
    Below the surface the fire goes in a niche Mimo digs, never in its way out. A walk to a fire
    goes all the way or not at all (foraging.whole_walk), and a fire where a step just failed is
    left alone for a while (senses.near_failure)."""
    fire = next((block for block in WARM_BLOCKS if s.inventory.get(block, 0) > 0), None)
    if fire is not None:
        steps: list[dict] = []
        if place_station(station_spots(s), fire, steps) is not None:
            return steps
    x, _, z = s.here
    spots = []
    home = nearest(s.places, s.here, SHELTER_KINDS, HOME_RANGE)
    if home is not None:
        spots.append((s.distance(cell_of(home)), walk_to(cell_of(home))))
    for cell, _ in s.grid.placed_cells(x, z, HOME_RANGE, WARM_BLOCKS):
        if not near_failure(s.state, cell):
            spots.append((s.distance(cell), whole_walk(cell, FIRE_STAND)))
    spots = [spot for spot in spots if spot[0] > FIRE_STAND]
    return [min(spots, key=lambda spot: spot[0])[1]] if spots else []


register(Reflex("warm_up", 50, trigger=lambda s: s.vitals["warmth"] < WARM_UP_BELOW, plan=plan_warm_up,
                thought="Brr. I need to get warm.", event="{name} went to get warm.", cooldown=30.0))


# head_home -------------------------------------------------------------------------------------

def head_home_due(s: Situation) -> bool:
    if not HOMEWARD <= s.clock["seconds_into_day"] < NIGHTFALL:
        return False
    if s.brain["purpose"] in ("go_home", "sleep", *AT_HOME_WORK):
        return False
    home = home_of(s)
    if home is None or s.distance(cell_of(home)) <= AT_HOME:
        return False
    x, y, z = s.here
    return not is_sheltered(s.grid.material, x, y, z)


register(Reflex("head_home", 60, trigger=head_home_due,
                plan=lambda s, context: [walk_to(cell_of(home_of(s)))],
                thought="It's getting dark. Home, quickly.", event="{name} hurried home before dark.",
                cooldown=60.0, ends_purpose=True))


# collapse --------------------------------------------------------------------------------------

def plan_collapse(s: Situation, context: ActionContext) -> list[dict]:
    """Lie down in a bed within 8 blocks, else where Mimo stands. After a walk to the bed the sleep
    is kept (`keep`): when the walk fails, Mimo still sleeps where the walk left it."""
    walk = to_bed(s)
    return [*walk, {"kind": "sleep", "keep": True} if walk else {"kind": "sleep"}]


register(Reflex("collapse", 70,
                trigger=lambda s: s.vitals["energy"] < EXHAUSTED_BELOW and (s.state["action"] or {}).get("kind") != "sleep",
                plan=plan_collapse,
                thought="I can't keep my eyes open...", event="{name} collapsed from exhaustion.", cooldown=30.0))
