"""One survival tick: bring the active life's world up to now.

The worker calls `tick_life` about once a second. A longer gap (a laptop that slept) is
caught up in steps of at most 60 game seconds, so a pet can starve while nobody watches. Each
step is its own transaction with its own path-search budget (`advance_world`), the way a fast
test run ticks, so a long catch-up is not one long write that locks the owner out, and a pet
catching up still walks, forages and gets home; between steps the worker lets its rules chooser
answer (`between`), so Mimo keeps choosing what to do, and a worker told to stop stops there
(`should_stop`) instead of running the rest of the gap first.
Each step first runs Mimo's timed actions up to the step's start (backend.survival.actions),
then advances vitals with the activity and surroundings at that moment. A `Mind` decides the
steps: its `plan` fills an empty queue (M1's `rest_plan` in the default `RESTING` mind), and its
optional hooks let a brain (backend.survival.brain) hear about finished steps (`observe`) and
notice each vitals step (`notice`). Minds never call a model here: the tick holds the world's
write transaction. After each chunk of actions the world regrows on its own
(backend.survival.renewal) and the creatures near Mimo take their turns
(backend.survival.creatures.simulate), whatever mind runs Mimo; the creatures skip the moment
the last tick ended on, since that tick already ran them up to it. A hostile creature's blow that
takes Mimo's last health kills it (L2): the creature's kind is the cause of death.

Fix round 2: while a hostile could reach Mimo, this step is one of many short FIGHT_SLICE steps in
the same transaction (see below), so only that call's creature turn is a hostile one
(`run_creatures(..., fight_step=True)`, backend.survival.creatures.simulate): herd spawning and
every animal's turn wait for the transaction's one final call, the ordinary L1 cadence, instead of
running (and costing) on every short step too.

L2 final fix wave: each of those short steps also gives Mimo's walks one small route search of
its own (ActionContext.small_searches_left, backend.survival.actions), so a flee walk does not wait
in the queue for the transaction's 2 whole searches while it is struck.

Making: last of all, once a transaction while Mimo lives, the machines Mimo built run up to its end
(backend.survival.signals.run_signals, bounded to MAX_CELLS cells a transaction).

W1: first of all, a living pet's difficulty is settled (backend.survival.wild.settle): a world from before
W1 becomes gentle, and a gentle pet is granted the survival lessons it knows from the start. Each vitals
step takes a wild pet's ailments into account (backend.survival.ailments: `ailing` before, `tend` after),
and its food ages (backend.survival.spoilage.age).

W2: a world from before W2 gets its year's offset on its first tick (backend.survival.sky.settle_sky), and before
each step the sky is tended (sky.advance: the season, then its effects), so a long catch-up plays the seasons in
time order; the season sets the warmth Mimo drifts toward (Surroundings.season), and falling snow takes some off
outdoors (Surroundings.snowing; backend.survival.weather's other effects register themselves).
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Callable

from backend.services.block_table import material_in
from backend.services.worldgen import biome_at
from backend.survival import ailments, sky, spoilage
from backend.survival import weather  # noqa: F401  (W2: rain and snow slow walks, fog brings the dark creatures)
from backend.survival.actions import (
    ActionContext, Interrupt, Observe, Planner, activity_of, advance_actions, ensure_actions,
)
from backend.survival.clock import DAY_SECONDS, action_scale as action_scale_setting, clock_at, is_night, time_scale
from backend.survival.creatures.hostiles import hostile_near
from backend.survival.creatures.simulate import simulate
from backend.survival.grid import world_grid
from backend.survival.once import log_once
from backend.survival.registry import LifeRegistry
from backend.survival.renewal import renew
from backend.survival.script import rest_plan
from backend.survival.signals import run_signals
from backend.survival.vitals import (
    FIRE_REACH, FREEZING_BELOW, WARM_BLOCKS, Surroundings, is_sheltered, near_warm_block, step_vitals,
)
from backend.survival.wild import settle
from backend.survival.world import SurvivalWorld, log_event, placed_near, read_state, write_state

logger = logging.getLogger(__name__)

MAX_STEP_SECONDS = 60.0
# L2: while a hostile creature could reach Mimo, a step lasts at most this many seconds of action
# time (divided by MIMO_ACTION_SCALE), so fights and flights see where the creatures are now.
FIGHT_SLICE = 1.0
# Fix round 1: at most this many of those short steps run in one transaction. Without a cap, a low
# MIMO_TIME_SCALE with a high MIMO_ACTION_SCALE shrinks FIGHT_SLICE / action_scale * scale toward
# nothing (a transaction could otherwise cost thousands of creature calls); once the cap is spent,
# catch-up falls back to the ordinary (longer) pace for the rest of the transaction. Fix round 2:
# those short steps are spread evenly across the transaction's span instead (max(FIGHT_SLICE /
# action_scale * scale, span / FIGHT_SLICES_MAX)), so the cap being spent does not also leave one
# long tail step at the end.
FIGHT_SLICES_MAX = 60
HUNGRY_BELOW = 30.0
CAUSE_TEXT = {"starvation": "starvation", "cold": "the cold", "drowning": "drowning", "fall": "a fall"}
CAUSE_WORDS = {"sickness": "fell sick and never got better"}  # W1

Event = tuple[float, str, str]
# After each vitals step: (state, context, vitals before the step, surroundings, step start, step end).
Notice = Callable[[dict, ActionContext, dict, Surroundings, float, float], None]


@dataclass(frozen=True)
class Mind:
    """What runs Mimo inside a tick. `plan` fills an empty queue; the hooks are optional."""

    plan: Planner = rest_plan
    interrupt: Interrupt | None = None
    observe: Observe | None = None
    notice: Notice | None = None


RESTING = Mind()


def surroundings_at(db: sqlite3.Connection, seed: str, position: dict, state: dict | None = None) -> Surroundings:
    """What the world round Mimo's cell says for a vitals step; W2: with `state`, the season too."""
    x, y, z = round(position["x"]), round(position["y"]), round(position["z"])

    def material_at(cx: int, cy: int, cz: int) -> str:
        return material_in(db, cx, cy, cz, seed)

    return Surroundings(
        biome=biome_at(x, z, seed),
        sheltered=is_sheltered(material_at, x, y, z),
        near_fire=near_warm_block(placed_near(db, position, FIRE_REACH, WARM_BLOCKS), x, y, z),
        head_in_water=material_at(x, y, z) == "water",
        season=sky.season_now(state) if state is not None else "spring",
        snowing=state is not None and sky.weather_now(state) == "snow",
    )


def note_crossings(state: dict, before: dict, at: float, events: list[Event]) -> None:
    after, name = state["vitals"], state["name"]
    if before["hunger"] >= HUNGRY_BELOW > after["hunger"]:
        state["last_thought"] = "My tummy is rumbling. I need food."
        events.append((at, "hungry", f"{name} is getting hungry."))
    if before["hunger"] > 0 >= after["hunger"]:
        state["last_thought"] = "I'm starving..."
        events.append((at, "starving", f"{name} is starving."))
    if before["warmth"] >= FREEZING_BELOW > after["warmth"]:
        state["last_thought"] = "I'm so cold."
        events.append((at, "freezing", f"{name} is freezing."))


def death_words(cause: str) -> str:
    """How a death reads: "died of the cold", or, for a creature's kind (L2), "was caught by a gloomling"."""
    if cause in CAUSE_WORDS:
        return CAUSE_WORDS[cause]
    if cause in CAUSE_TEXT:
        return f"died of {CAUSE_TEXT[cause]}"
    return f"was caught by a {cause.replace('_', ' ')}"


def record_death(state: dict, cause: str, at: float, scale: float, events: list[Event]) -> None:
    """Mark Mimo dead at `at` and log it. The current step and the plan end with the life.

    A fatal fall can be discovered a catch-up step after the vitals (and any crossing, like
    "hungry") that already ran up to that step's cursor, so `at` can land before events already
    queued for it. Drop those: nothing should read as happening after Mimo died. Health already
    reads 0 by the time any cause is known (step_vitals or finish_fall got it there), so it is
    left alone.
    """
    events[:] = [event for event in events if event[0] <= at]
    day = clock_at(state["born_at"], at, scale)["day_number"]
    state.update(status="dead", died_at=at, cause=cause, action=None, queue=[])
    events.append((at, "death", f"{state['name']} {death_words(cause)} on day {day}."))


def run_notice(mind: Mind, state: dict, context: ActionContext, before: dict, surroundings: Surroundings,
               since: float, at: float) -> None:
    """Call the mind's notice hook. A crashing hook is logged once and the tick goes on."""
    if mind.notice is None:
        return
    try:
        mind.notice(state, context, before, surroundings, since, at)
    except Exception as error:
        log_once(logger, "notice", error)


def run_renewal(state: dict, context: ActionContext, at: float) -> None:
    """Let the world regrow up to `at` (backend.survival.renewal). A crash is logged once and the
    tick goes on."""
    try:
        renew(state, context, at)
    except Exception as error:
        log_once(logger, "renewal", error)


def run_creatures(state: dict, context: ActionContext, at: float, fight_step: bool = False) -> None:
    """Let the creatures near Mimo take their turns up to `at` (backend.survival.creatures.simulate).
    `fight_step` (fix round 2) says whether this call is one of the short FIGHT_SLICE steps, so
    only hostiles load and act, or the slice's one final call, the ordinary L1 cadence. A crash is
    logged once and the tick goes on."""
    try:
        simulate(state, context, at, fight_step=fight_step)
    except Exception as error:
        log_once(logger, "creatures", error)


def caught(state: dict) -> bool:
    """A hostile creature's blow (L2, backend.survival.creatures.harm) took Mimo's last health."""
    return state["vitals"]["health"] <= 0 and bool(state.get("hurt_by"))


def creature_nearby(context: ActionContext, state: dict) -> bool:
    """Whether a hostile could reach Mimo now (backend.survival.creatures.hostiles.hostile_near),
    so the step ahead should be short. A crash is logged once and treated as "no" (fix round 1),
    so a bad query falls back to the ordinary (longer) pace instead of stopping the tick."""
    try:
        return hostile_near(context.grid, context.db, state)
    except Exception as error:
        log_once(logger, "hostile_near", error)
        return False


def advance_world(world: SurvivalWorld, timestamp: float, scale: float, mind: Mind = RESTING,
                  action_scale: float = 1.0) -> dict:
    """Catch the world up to `timestamp` in one transaction and return the saved state."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None or timestamp <= state["last_tick_at"]:
            return state
        ensure_actions(state)
        settle(state, db, state["last_tick_at"])  # W1: gentle for an old world, and a gentle pet's lessons
        sky.settle_sky(state, state["last_tick_at"], scale)  # W2: an old world's year starts in spring now
        events: list[Event] = []
        context = ActionContext(grid=world_grid(db, world.seed), planner=mind.plan, events=events,
                                clock_at=lambda at: clock_at(state["born_at"], at, scale),
                                observe=mind.observe, db=db, action_scale=action_scale,
                                interrupt=mind.interrupt)
        cursor = state["last_tick_at"]
        remaining = (timestamp - cursor) * scale
        span = remaining  # fix round 2: the whole span, to spread the short steps evenly across it
        fight_slices = 0  # fix round 1: bounds how many short (FIGHT_SLICE) steps this transaction takes
        fight_step = False  # fix round 2: whether the step that reached the current cursor was one of those
        while remaining > 1e-9:
            fell_at = advance_actions(state, context, cursor)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
                break
            sky.advance(state, context, cursor)  # W2: the season and the weather at this step's start
            run_renewal(state, context, cursor)
            if cursor != state["last_tick_at"]:  # the last tick already ran the creatures up to here
                run_creatures(state, context, cursor, fight_step=fight_step)
                if caught(state):
                    record_death(state, state["hurt_by"], cursor, scale, events)
                    break
            step = min(MAX_STEP_SECONDS, remaining)
            fight_step = False
            if fight_slices < FIGHT_SLICES_MAX and creature_nearby(context, state):
                # Fix round 2: spread the FIGHT_SLICES_MAX steps evenly across the whole span,
                # instead of many tiny ones followed by one long tail step once the cap is spent.
                step = min(step, max(FIGHT_SLICE / action_scale * scale, span / FIGHT_SLICES_MAX))
                fight_slices += 1
                fight_step = True
            # Final fix wave: each fight step brings one small search of its own for a walk
            # (backend.survival.actions.walk_search), so a flee or a step up never waits on the
            # transaction's 2 whole searches while a hostile strikes; unused, it does not add up.
            context.small_searches_left = 1 if fight_step else 0
            night = is_night(clock_at(state["born_at"], cursor, scale)["phase"])
            last_hello = state["last_hello_at"] or state["born_at"]
            before = state["vitals"]
            surroundings = surroundings_at(db, world.seed, state["position"], state)
            activity = activity_of(state)
            ill = ailments.ailing_now(state)  # W1: read once a step, guarded (the final fix wave)
            state["vitals"], cause = step_vitals(
                before, step, night=night, activity=activity, surroundings=surroundings,
                lonely=(cursor - last_hello) * scale > DAY_SECONDS, ailing=ill)
            since = cursor
            cursor += step / scale
            remaining -= step
            note_crossings(state, before, cursor, events)
            ailments.tend(state, context, step, activity, cursor, ill)  # W1: a sickness runs its time, a wound too
            phases = (clock_at(state["born_at"], since, scale)["phase"], clock_at(state["born_at"], cursor, scale)["phase"])
            ailments.tend_night(state, context, step, phases, activity, surroundings.sheltered, cursor)  # W1: cold nights
            spoilage.age(state, context, step, cursor)  # W1: a wild pet's food ages
            if cause:
                record_death(state, cause, cursor, scale, events)
                break
            run_notice(mind, state, context, before, surroundings, since, cursor)
        if state["died_at"] is None:
            fell_at = advance_actions(state, context, timestamp)
            if fell_at is not None:
                record_death(state, "fall", fell_at, scale, events)
            else:
                run_renewal(state, context, timestamp)
                run_creatures(state, context, timestamp)  # the slice's one final call: full (fix round 2)
                if caught(state):
                    record_death(state, state["hurt_by"], timestamp, scale, events)
                else:
                    run_signals(state, context, timestamp)  # Making: the machines, once a transaction
        state["last_tick_at"] = state["died_at"] if state["died_at"] is not None else timestamp
        write_state(db, state)
        for at, kind, text in sorted(events, key=lambda event: event[0]):
            log_event(db, at, kind, text)
        return state


def tick_life(registry: LifeRegistry, timestamp: float | None = None, scale: float | None = None,
              mind: Mind = RESTING, action_scale: float | None = None,
              between: Callable[[float], None] | None = None,
              should_stop: Callable[[], bool] | None = None) -> dict | None:
    """Advance the active life and archive it if it died. Returns its state, or None if no pet is alive.

    A gap longer than one catch-up step (60 game seconds) is advanced one step per transaction,
    calling `between(at)` after a step only when a whole further step still remains (fix round 1:
    an ordinary tick's small leftover, such as the worker's ~1 s sleep running a hair past one
    step, must not itself wake the rules chooser) while Mimo lives. `should_stop()` is asked after
    each committed step that leaves more to catch up: when it says yes (the worker was told to
    stop), the catch-up ends there, and the next tick goes on from the last committed step."""
    life = registry.active_life()
    if life is None:
        return None
    timestamp = time.time() if timestamp is None else timestamp
    scale = time_scale() if scale is None else scale
    action_scale = action_scale_setting() if action_scale is None else action_scale
    world = SurvivalWorld(registry.world_path(life))
    at = world.state()["last_tick_at"]
    while True:
        at = min(timestamp, at + MAX_STEP_SECONDS / scale)
        state = advance_world(world, at, scale, mind, action_scale)
        if at >= timestamp or state["died_at"] is not None:
            break
        if should_stop is not None and should_stop():
            break
        if between is not None and timestamp - at >= MAX_STEP_SECONDS / scale:
            between(at)
    if state["died_at"] is not None:
        registry.mark_dead(life["id"], state["died_at"], state["cause"])
    return state
