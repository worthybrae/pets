"""Mimo's timed actions: the step it is doing, the steps queued after it and the last finished ones.

`advance_actions` brings the actions up to a moment in time. Every step that ends by then
finishes in order, so several short steps can finish in one tick, and each next step starts the
moment the one before it ended. When the queue is empty the planner is asked for more steps.
Before a new step starts, two hazards come first: Mimo falls when nothing holds it up
((blocks - 3) x 10 damage, none when it lands on water), and it swims straight up when its cell
is water (the physical half of the brain's surface reflex). Either hazard drops the running
step or the queue it interrupts (recorded once with result "interrupted" and reason "fall" or
"swim") so the brain can tell its plan was abandoned, not failed. A step that fails is recorded
with a failure code (steps.FAILURE_CODES) and kept as `state["last_failure"]` with its cell and
the purpose that planned it; queued steps carry that purpose as `purpose`. A failure drops the
rest of the plan except its cleanup steps (`keep`, see kept_steps).

A crashing planner, or one returning something other than a list of dicts, is logged once per
distinct error and replaced with rest_plan for that call; a step that fails to start or finish in some unexpected
way (not the StepFailed/ValueError/KeyError start_step and finish_step already raise for bad
game state) is recorded failed with reason "bad step" instead of raising. Neither ever stops the
tick: a malformed step or a broken planner must not freeze a life (M3 will plug new planners in
here, so this must be airtight).

A walk step starts with a path search (route(), inside start_step); on real terrain a search
that exhausts its budget costs around 250ms. Catching up after a long gap can call advance_actions
many times inside one advance_world (one per catch-up step, plus a final call), all sharing one
ActionContext, so the search budget lives on the context (`searches_left`, from
MAX_SEARCHES_PER_TICK) instead of resetting every call: once it reaches zero, a walk at the front
of the queue (or just re-queued by an unfinished segment) is left there and waits for the next
advance_actions call instead of searching (Task 3 review ruling; Task 6 fix round 1 made the
budget span the whole tick instead of one call). Because that walk is left unpopped and unstarted,
no step with an empty path is ever built.

A mind can take over through `context.interrupt` (the brain's reflexes). It is asked before every
step starts and at every advance while a walk, sleep or wait is still running; a cut walk has
already moved to the last cell it reached. The cut step is recorded as "interrupted" with the
hook's reason. At most MAX_TAKEOVERS takeovers happen per advance_actions call, so a hook that
always says yes cannot spin the tick.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass
from typing import Callable

from backend.services.worldgen import WORLD_MIN_Y
from backend.survival.clock import is_night
from backend.survival.grid import Cell, Grid
from backend.survival.once import log_once
from backend.survival.pathing import SWIM_SECONDS
from backend.survival.steps import as_cell, as_point, failure_code, finish_step, position_of, start_step

logger = logging.getLogger(__name__)

RECENT_LIMIT = 20
# Finished walks, swims and falls keep their timed path so the viewer can replay a short step it
# never saw running. Only entries that ended within PATH_WINDOW real seconds of the newest one keep
# it (the viewer replays about 1.5 s behind), and never more than the newest PATH_KEEP, so the
# saved state and the /api/mimo payload stay small.
PATH_KEEP = 4
PATH_WINDOW = 10.0
MAX_STEPS_PER_ADVANCE = 1000
MAX_SEARCHES_PER_TICK = 2  # route()/start_step(walk) calls allowed across one whole advance_world call
GRAVITY = 32.0  # blocks per second squared: a fall of b blocks takes sqrt(2 b / GRAVITY) seconds
SAFE_FALL = 3
FALL_DAMAGE = 10.0
WAKE_ENERGY = 95.0
WORKING = frozenset({"walk", "swim", "mine", "place"})
STATUS = {"walk": "walking", "swim": "swimming", "fall": "falling", "mine": "mining", "place": "building",
          "eat": "eating", "craft": "crafting", "smelt": "smelting", "sleep": "sleeping", "wait": "idle"}
# Waits tell the viewer nothing and would push real steps out of the recent list.
UNRECORDED = frozenset({"wait"})
# Running steps a takeover may cut short. The others last a few seconds at most and finish first.
INTERRUPTIBLE = frozenset({"walk", "sleep", "wait"})
MAX_TAKEOVERS = 4
RECORDED_FIELDS = ("kind", "started_at", "target", "block", "item", "recipe", "purpose", "path")

Event = tuple[float, str, str]
# A planner gets the state, the tick's ActionContext and the time, and returns the next steps.
Planner = Callable[[dict, "ActionContext", float], list[dict]]
# An observer hears about each step that finished well: (state, finished step, context, time).
Observe = Callable[[dict, dict, "ActionContext", float], None]
# An interrupt hook may take over: it fills the queue with its own steps and returns a reason.
Interrupt = Callable[[dict, "ActionContext", float], "str | None"]


@dataclass
class ActionContext:
    """What advance_actions needs besides the state: the world, the game clock, a planner, an event list.

    `searches_left` is one path-search budget shared by every advance_actions call made from the
    same advance_world call (it is created once per tick and mutated down as walks start), so a
    long catch-up cannot run more than MAX_SEARCHES_PER_TICK searches in one write transaction.
    Planners that search themselves spend it through `take_search`. `observe` hears about every
    step that finished well. `db` is the world's connection inside the tick's transaction, for
    minds that keep memory; tests without a database leave it None.
    """

    grid: Grid
    clock_at: Callable[[float], dict]
    planner: Planner
    events: list[Event]
    searches_left: int = MAX_SEARCHES_PER_TICK
    observe: Observe | None = None
    db: sqlite3.Connection | None = None
    action_scale: float = 1.0
    interrupt: Interrupt | None = None


def take_search(context: ActionContext) -> bool:
    """Spend one path search from the tick's budget. False when none is left this tick."""
    if context.searches_left <= 0:
        return False
    context.searches_left -= 1
    return True


def ensure_actions(state: dict) -> None:
    """Give a state saved before actions existed (an M1 world) its action fields."""
    state.setdefault("action", None)
    state.setdefault("queue", [])
    state.setdefault("recent_actions", [])
    state.setdefault("actions_at", state["last_tick_at"])
    state.setdefault("last_failure", None)


def activity_of(state: dict) -> str:
    """The vitals activity of the current step: sleeping, working (walk, swim, mine, place) or idle."""
    action = state.get("action")
    if action is None:
        return "idle"
    if action["kind"] == "sleep":
        return "sleeping"
    return "working" if action["kind"] in WORKING else "idle"


def record(state: dict, step: dict, ended_at: float, result: str, reason: str | None = None,
           code: str | None = None) -> None:
    if step["kind"] in UNRECORDED:
        return
    entry = {key: step[key] for key in RECORDED_FIELDS if key in step}
    entry.update(ended_at=ended_at, result=result)
    if reason:
        entry["reason"] = reason
    if code:
        entry["code"] = code
    recent = [*state["recent_actions"], entry][-RECENT_LIMIT:]
    for index, older in enumerate(recent[:-1]):
        if index < len(recent) - PATH_KEEP or older["ended_at"] < ended_at - PATH_WINDOW:
            older.pop("path", None)
    state["recent_actions"] = recent


def kept_steps(queue: list[dict]) -> list[dict]:
    """The cleanup steps of a plan that is being dropped: queued steps marked `keep` (a portable
    station's mine-back), except one whose station is not down yet (its place step is still
    queued), since there is nothing to pick up."""
    unplaced = {tuple(spec["target"]) for spec in queue
                if spec.get("kind") == "place" and isinstance(spec.get("target"), list)}
    return [spec for spec in queue if spec.get("keep") and not (
        isinstance(spec.get("target"), list) and tuple(spec["target"]) in unplaced)]


def fail(state: dict, step: dict, at: float, reason: str, code: str = "bad_step") -> None:
    """Record a failed step, keep it as the last failure and drop the rest of the plan but its
    cleanup steps, so the planner plans again. `seq` counts failures, so two alike failures at the
    same moment differ. A cleanup step (`keep`, a portable station's mine-back) is recorded like
    any other failure but never becomes `last_failure`: it is not the current purpose's doing, and
    charging it would spend the purpose's one re-plan on someone else's mistake."""
    record(state, step, at, "failed", reason, code)
    if not step.get("keep"):
        seq = (state.get("last_failure") or {}).get("seq", 0) + 1
        state["last_failure"] = {"code": code, "reason": reason, "kind": step["kind"], "cell": step.get("target"),
                                 "purpose": step.get("purpose"), "at": at, "seq": seq}
    state["action"] = None
    state["queue"] = kept_steps(state["queue"])


def as_started(spec: dict, at: float) -> dict:
    """A queued step in the shape of a started one, to record a step that could not start.

    Copies the spec's own fields as they are, without re-parsing them: a spec malformed enough to
    fail start_step must still be recordable. `target` is normalised only best-effort, since that
    is exactly the field most likely to be the malformed one; a value as_point cannot make sense
    of is kept as-is rather than raising a second time from inside a failure handler.
    """
    step = {key: spec[key] for key in ("block", "item", "recipe", "purpose", "keep") if key in spec}
    step.update(kind=spec.get("kind", "unknown"), started_at=at)
    if "target" in spec:
        try:
            step["target"] = as_point(spec["target"])
        except ValueError:
            step["target"] = spec["target"]
    return step


def landing(grid: Grid, cell: Cell) -> Cell:
    """The first cell at or below `cell` where something holds Mimo up."""
    x, y, z = cell
    while not grid.supported((x, y, z)) and y > WORLD_MIN_Y:
        y -= 1
    return x, y, z


def interrupt_plan(state: dict, at: float, hazard: str) -> None:
    """Record the plan a fall or swim hazard is about to drop, once per hazard: the running step
    if there is one, else the first queued one. A wait, like any UNRECORDED kind, stays silent."""
    dropped = state["action"] or (state["queue"][0] if state["queue"] else None)
    if dropped is None:
        return
    step = dropped if dropped is state["action"] else as_started(dropped, at)
    record(state, step, at, "interrupted", hazard)


def start_hazard(state: dict, grid: Grid, at: float) -> bool:
    """Start a swim up or a fall when Mimo's cell calls for one. Returns True when one started."""
    here = as_cell(state["position"])
    if grid.water(here):
        x, y, z = here
        path = [{**as_point(here), "at": at}]
        while grid.water((x, y, z)) and not grid.solid((x, y + 1, z)):
            y += 1
            path.append({**as_point((x, y, z)), "at": round(path[-1]["at"] + SWIM_SECONDS, 3), "swim": True})
        if len(path) == 1:
            return False  # a ceiling holds Mimo under; air keeps draining
        interrupt_plan(state, at, "swim")
        state["action"] = {"kind": "swim", "started_at": at, "ends_at": path[-1]["at"], "path": path}
    elif grid.supported(here):
        return False
    else:
        land = landing(grid, here)
        blocks = here[1] - land[1]
        ends_at = round(at + math.sqrt(2 * blocks / GRAVITY), 3)
        interrupt_plan(state, at, "fall")
        state["action"] = {"kind": "fall", "started_at": at, "ends_at": ends_at, "blocks": blocks,
                           "path": [{**as_point(here), "at": at}, {**as_point(land), "at": ends_at}]}
    state["queue"] = []
    return True


def finish_fall(state: dict, step: dict, grid: Grid, at: float, events: list[Event]) -> bool:
    """Land. Returns True when the landing killed Mimo."""
    spot = step["path"][-1]
    state["position"] = position_of(spot)
    if grid.water((spot["x"], spot["y"] - 1, spot["z"])):
        return False
    damage = max(0, step["blocks"] - SAFE_FALL) * FALL_DAMAGE
    if damage == 0:
        return False
    state["vitals"]["health"] = max(0.0, state["vitals"]["health"] - damage)
    state["last_thought"] = "Ouch! That was a long way down."
    events.append((at, "fall", f"{state['name']} fell {step['blocks']} blocks and got hurt."))
    return state["vitals"]["health"] <= 0


def follow_path(state: dict, step: dict, grid: Grid, until: float) -> bool:
    """Move Mimo to the last path cell reached by `until`. False when a cell ahead turned solid."""
    for entry in step["path"][1:]:
        if entry["at"] > until:
            break
        if grid.solid(as_cell(entry)):
            return False
        state["position"] = position_of(entry)
    return True


def step_end(step: dict, state: dict, context: ActionContext, until: float) -> float | None:
    """When the running step ends, or None while it still runs at `until`."""
    if step["kind"] == "sleep":
        rested = state["vitals"]["energy"] >= WAKE_ENERGY
        return until if rested and not is_night(context.clock_at(until)["phase"]) else None
    return step["ends_at"] if step["ends_at"] <= until else None


def begin(state: dict, spec: dict, at: float, events: list[Event]) -> None:
    if spec.get("thought"):
        state["last_thought"] = spec["thought"]
    if spec["kind"] == "sleep":
        events.append((at, "sleep", f"{state['name']} fell asleep."))


def notify(context: ActionContext, state: dict, step: dict, at: float) -> None:
    """Tell the observer about a step that finished well. A crashing observer is logged once."""
    if context.observe is None:
        return
    try:
        context.observe(state, step, context, at)
    except Exception as error:
        log_once(logger, "observe", error)


def finish(state: dict, step: dict, context: ActionContext, at: float) -> bool:
    """Apply a step that ended at `at`. Returns True when it killed Mimo."""
    grid, events = context.grid, context.events
    if step["kind"] == "fall":
        record(state, step, at, "done")
        return finish_fall(state, step, grid, at, events)
    if step["kind"] == "swim":
        state["position"] = position_of(step["path"][-1])
        record(state, step, at, "done")
        notify(context, state, step, at)
        return False
    try:
        event = finish_step(step, state, grid, at)
    except (ValueError, KeyError) as error:
        fail(state, step, at, str(error), failure_code(error))
        return False
    except Exception as error:
        log_once(logger, "finish_step", error)
        fail(state, step, at, "bad step", "bad_step")
        return False
    record(state, step, at, "done")
    if event:
        events.append((at, *event))
    if step["kind"] == "sleep":
        state["last_thought"] = "Good morning. I feel rested."
        events.append((at, "wake", f"{state['name']} woke up."))
    if step["kind"] == "walk" and not step["reached"]:
        target = step["target"]
        segment = {"kind": "walk", "target": [target["x"], target["y"], target["z"]], "reach": step["reach"],
                   "segments": step["segments"] + 1}
        if "purpose" in step:
            segment["purpose"] = step["purpose"]
        state["queue"].insert(0, segment)
    notify(context, state, step, at)
    return False


def safe_plan(context: ActionContext, state: dict, at: float) -> list[dict]:
    """Ask the planner for the next steps. A crash, or a result that is not a list of dicts, is
    logged once per distinct error and replaced with rest_plan: minds plug their planners in
    here, so this must be airtight against whatever one of them does wrong."""
    try:
        plan = context.planner(state, context, at)
    except Exception as error:
        log_once(logger, "planner", error)
        plan = None
    else:
        if not (isinstance(plan, list) and all(isinstance(spec, dict) for spec in plan)):
            log_once(logger, "planner", TypeError(f"planner returned {type(plan).__name__}, not a list of steps"))
            plan = None
    if plan is None:
        from backend.survival.script import rest_plan  # imported here to sidestep an import cycle
        plan = rest_plan(state, context, at)
    return list(plan)


def interrupted(state: dict, context: ActionContext, at: float) -> bool:
    """Ask the interrupt hook whether something takes over at `at`.

    The hook sees the running step (if any) and, to take over, fills the queue with its own steps
    and returns a reason. The running step is then recorded as interrupted and cleared. A
    crashing hook is logged once and counts as no takeover.
    """
    if context.interrupt is None:
        return False
    try:
        reason = context.interrupt(state, context, at)
    except Exception as error:
        log_once(logger, "interrupt", error)
        return False
    if not reason:
        return False
    step = state["action"]
    if step is not None:
        record(state, step, at, "interrupted", reason)
        state["action"] = None
    return True


def advance_actions(state: dict, context: ActionContext, until: float) -> float | None:
    """Run Mimo's actions up to `until`. Returns the time a fall killed Mimo, or None."""
    ensure_actions(state)
    grid = context.grid
    at = min(state["actions_at"], until)
    takeovers = 0
    for _ in range(MAX_STEPS_PER_ADVANCE):
        step = state["action"]
        if step is None:
            if start_hazard(state, grid, at):
                continue
            if takeovers < MAX_TAKEOVERS and interrupted(state, context, at):
                takeovers += 1
                continue
            if not state["queue"]:
                state["queue"] = safe_plan(context, state, at)
                if not state["queue"]:
                    break
                if context.interrupt is not None:
                    continue  # a fresh plan gets the same takeover check before its first step
            spec = state["queue"][0]
            if spec.get("kind") == "walk" and not take_search(context):
                break  # search budget spent this tick; try this walk again next advance_actions
            state["queue"].pop(0)
            try:
                state["action"] = start_step(spec, state, grid, at, context.action_scale)
            except (ValueError, KeyError) as error:
                fail(state, as_started(spec, at), at, str(error), failure_code(error))
                break  # plan again at the next advance, not in a tight loop
            except Exception as error:
                log_once(logger, "start_step", error)
                fail(state, as_started(spec, at), at, "bad step", "bad_step")
                break
            if "purpose" in spec:
                state["action"]["purpose"] = spec["purpose"]
            begin(state, spec, at, context.events)
            continue
        if step["kind"] in ("walk", "swim") and not follow_path(state, step, grid, until):
            fail(state, step, until, "path blocked", "blocked")
            at = until
            continue
        end = step_end(step, state, context, until)
        if end is None:
            if step["kind"] in INTERRUPTIBLE and takeovers < MAX_TAKEOVERS and interrupted(state, context, until):
                takeovers += 1
                at = until
                continue
            break
        state["action"] = None
        at = end
        if finish(state, step, context, end):
            return end
    state["actions_at"] = until
    action = state["action"]
    state["status"] = STATUS.get(action["kind"], "idle") if action else "idle"
    return None
