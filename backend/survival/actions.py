"""Mimo's timed actions: the step it is doing, the steps queued after it and the last finished ones.

`advance_actions` brings the actions up to a moment in time. Every step that ends by then
finishes in order, so several short steps can finish in one tick, and each next step starts the
moment the one before it ended. When the queue is empty the planner is asked for more steps.
Before a new step starts, two hazards come first: Mimo falls when nothing holds it up
((blocks - 3) x 10 damage, none when it lands on water), and it swims straight up when its cell
is water (a fallback until the brain's surface reflex in M3).

A crashing planner, or one returning something other than a list of dicts, is logged once and
replaced with rest_plan for that call; a step that fails to start or finish in some unexpected
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
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Callable

from backend.services.worldgen import WORLD_MIN_Y
from backend.survival.clock import is_night
from backend.survival.grid import Cell, Grid
from backend.survival.pathing import SWIM_SECONDS
from backend.survival.steps import as_cell, as_point, finish_step, position_of, start_step

logger = logging.getLogger(__name__)

RECENT_LIMIT = 20
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
RECORDED_FIELDS = ("kind", "started_at", "target", "block", "item", "recipe")

Event = tuple[float, str, str]
Planner = Callable[[dict, Grid, float, dict], list[dict]]


@dataclass
class ActionContext:
    """What advance_actions needs besides the state: the world, the game clock, a planner, an event list.

    `searches_left` is one path-search budget shared by every advance_actions call made from the
    same advance_world call (it is created once per tick and mutated down as walks start), so a
    long catch-up cannot run more than MAX_SEARCHES_PER_TICK searches in one write transaction.
    """

    grid: Grid
    clock_at: Callable[[float], dict]
    planner: Planner
    events: list[Event]
    searches_left: int = MAX_SEARCHES_PER_TICK


def ensure_actions(state: dict) -> None:
    """Give a state saved before actions existed (an M1 world) its action fields."""
    state.setdefault("action", None)
    state.setdefault("queue", [])
    state.setdefault("recent_actions", [])
    state.setdefault("actions_at", state["last_tick_at"])


def activity_of(state: dict) -> str:
    """The vitals activity of the current step: sleeping, working (walk, swim, mine, place) or idle."""
    action = state.get("action")
    if action is None:
        return "idle"
    if action["kind"] == "sleep":
        return "sleeping"
    return "working" if action["kind"] in WORKING else "idle"


def record(state: dict, step: dict, ended_at: float, result: str, reason: str | None = None) -> None:
    if step["kind"] in UNRECORDED:
        return
    entry = {key: step[key] for key in RECORDED_FIELDS if key in step}
    entry.update(ended_at=ended_at, result=result)
    if reason:
        entry["reason"] = reason
    state["recent_actions"] = [*state["recent_actions"], entry][-RECENT_LIMIT:]


def fail(state: dict, step: dict, at: float, reason: str) -> None:
    """Record a failed step and drop the rest of the plan, so the planner plans again."""
    record(state, step, at, "failed", reason)
    state["action"] = None
    state["queue"] = []


def as_started(spec: dict, at: float) -> dict:
    """A queued step in the shape of a started one, to record a step that could not start.

    Copies the spec's own fields as they are, without re-parsing them: a spec malformed enough to
    fail start_step must still be recordable. `target` is normalised only best-effort, since that
    is exactly the field most likely to be the malformed one; a value as_point cannot make sense
    of is kept as-is rather than raising a second time from inside a failure handler.
    """
    step = {key: spec[key] for key in ("block", "item", "recipe") if key in spec}
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
        state["action"] = {"kind": "swim", "started_at": at, "ends_at": path[-1]["at"], "path": path}
    elif grid.supported(here):
        return False
    else:
        land = landing(grid, here)
        blocks = here[1] - land[1]
        ends_at = round(at + math.sqrt(2 * blocks / GRAVITY), 3)
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


def finish(state: dict, step: dict, context: ActionContext, at: float) -> bool:
    """Apply a step that ended at `at`. Returns True when it killed Mimo."""
    grid, events = context.grid, context.events
    if step["kind"] == "fall":
        record(state, step, at, "done")
        return finish_fall(state, step, grid, at, events)
    if step["kind"] == "swim":
        state["position"] = position_of(step["path"][-1])
        record(state, step, at, "done")
        return False
    try:
        event = finish_step(step, state, grid, at)
    except (ValueError, KeyError) as error:
        fail(state, step, at, str(error))
        return False
    except Exception:
        logger.exception("finish_step crashed on %r", step)
        fail(state, step, at, "bad step")
        return False
    record(state, step, at, "done")
    if event:
        events.append((at, *event))
    if step["kind"] == "sleep":
        state["last_thought"] = "Good morning. I feel rested."
        events.append((at, "wake", f"{state['name']} woke up."))
    if step["kind"] == "walk" and not step["reached"]:
        target = step["target"]
        state["queue"].insert(0, {"kind": "walk", "target": [target["x"], target["y"], target["z"]],
                                  "reach": step["reach"], "segments": step["segments"] + 1})
    return False


def safe_plan(context: ActionContext, state: dict, grid: Grid, at: float) -> list[dict]:
    """Ask the planner for the next steps. A crash, or a result that is not a list of dicts, is
    logged once and replaced with rest_plan: M3 plugs new planners in here, so this must be
    airtight against whatever one of them does wrong."""
    clock = context.clock_at(at)
    try:
        plan = context.planner(state, grid, at, clock)
    except Exception:
        logger.exception("planner crashed")
        plan = None
    else:
        if not (isinstance(plan, list) and all(isinstance(spec, dict) for spec in plan)):
            logger.error("planner returned %r, not a list of steps", plan)
            plan = None
    if plan is None:
        from backend.survival.script import rest_plan  # imported here to sidestep any future cycle
        plan = rest_plan(state, grid, at, clock)
    return list(plan)


def advance_actions(state: dict, context: ActionContext, until: float) -> float | None:
    """Run Mimo's actions up to `until`. Returns the time a fall killed Mimo, or None."""
    ensure_actions(state)
    grid = context.grid
    at = min(state["actions_at"], until)
    for _ in range(MAX_STEPS_PER_ADVANCE):
        step = state["action"]
        if step is None:
            if start_hazard(state, grid, at):
                continue
            if not state["queue"]:
                state["queue"] = safe_plan(context, state, grid, at)
                if not state["queue"]:
                    break
            spec = state["queue"][0]
            if spec.get("kind") == "walk" and context.searches_left <= 0:
                break  # search budget spent this tick; try this walk again next advance_actions
            state["queue"].pop(0)
            if spec.get("kind") == "walk":
                context.searches_left -= 1
            try:
                state["action"] = start_step(spec, state, grid, at)
            except (ValueError, KeyError) as error:
                fail(state, as_started(spec, at), at, str(error))
                break  # plan again at the next advance, not in a tight loop
            except Exception:
                logger.exception("start_step crashed on %r", spec)
                fail(state, as_started(spec, at), at, "bad step")
                break
            begin(state, spec, at, context.events)
            continue
        if step["kind"] in ("walk", "swim") and not follow_path(state, step, grid, until):
            fail(state, step, until, "path blocked")
            at = until
            continue
        end = step_end(step, state, context, until)
        if end is None:
            break
        state["action"] = None
        at = end
        if finish(state, step, context, end):
            return end
    state["actions_at"] = until
    action = state["action"]
    state["status"] = STATUS.get(action["kind"], "idle") if action else "idle"
    return None
