"""The brain inside the tick: purposes into steps, failures and reports, triggers and discoveries.

The tick never calls a model (it holds the world's write transaction). It asks `brain_plan` for
steps whenever Mimo's queue runs dry:

1. A batch that failed (a `state["last_failure"]` the brain has not dealt with yet) is planned
   again once. A second failure reports back: the purpose is dropped, scores 30 lower for 600
   game seconds, and a `plan_failed` trigger asks for a new choice.
   On any failure after two walks of the purpose found no path, the brain first checks whether
   Mimo is trapped and digs a staircase out (backend.survival.escape).
2. Otherwise the last batch finished well and counts toward the purpose's `batches`.
3. The chosen purpose plans its next batch, each step tagged with the purpose's name. A purpose
   that is no longer valid, or has nothing left to do, is finished: `plan_done` asks for a new
   choice. A planner that crashes (or returns something other than a list of steps) is logged
   once and reported like a failure.
4. With no purpose (a choice is pending), Mimo follows M1's rest rule while it waits: it sleeps
   at night (or when exhausted) and otherwise waits a second at a time.

Reflexes (backend.survival.reflexes) take over through the interrupt hook. When a reflex's steps
run out, brain_plan ends it and resumes the purpose's steps it set aside (only their cleanup
steps when no purpose is left). head_home ends the purpose instead, so the choice after it is
made at home.

`observe_step` hears about finished steps: ores around a mined block, recipes learned, water swum
in, places visited, the ground walked (backend.survival.exploring), M4's lessons
(backend.survival.learning: poisonous food, food patches, fires and farms) and M5's
(building.note_building: finished structures, planted trees, full arms, torches). `notice_step`
runs after each vitals step: vital crossings (urgent), dawn and dusk, a game hour since the last
choice, and shelter (the first sheltered spot becomes home).
First sightings (home, each ore material, water) are discoveries and ask for a new choice.
"""

from __future__ import annotations

import logging

from backend.survival import cooking, farming, foraging, toolmaking, work  # noqa: F401  (they register their purposes)
from backend.survival import farmstead, lighting, storage  # noqa: F401  (M5's building purposes)
from backend.survival.building import note_building
from backend.survival.actions import ActionContext, kept_steps
from backend.survival.escape import plan_escape
from backend.survival.exploring import note_ground
from backend.survival.learning import learn_from_step
from backend.survival.memory import SHELTER_KINDS, forget, learn, remember, visit
from backend.survival.once import log_once
from backend.survival.purposes import PURPOSES, Purpose, is_valid
from backend.survival.reflexes import by_name, end_reflex, reflex_hook
from backend.survival.script import rest_plan
from backend.survival.senses import ORES, ores_around
from backend.survival.situation import Situation, in_tick
from backend.survival.steps import as_cell, label
from backend.survival.tick import Mind
from backend.survival.triggers import crossings, ensure_brain, hour_passed, mark_trigger, phase_trigger
from backend.survival.vitals import Surroundings

logger = logging.getLogger(__name__)

PENDING_WAIT = 1.0
PENALTY_GAME_SECONDS = 600.0


def waiting(state: dict, context: ActionContext, at: float) -> list[dict]:
    """Wait for a choice, asking for one if nothing is pending: asleep at night (rest_plan's
    rule), else a second at a time so a choice starts promptly."""
    if ensure_brain(state)["pending"] is None:
        mark_trigger(state, "idle", at)
    plan = rest_plan(state, context, at)
    return plan if plan and plan[0]["kind"] == "sleep" else [{"kind": "wait", "seconds": PENDING_WAIT}]


def finish_purpose(state: dict, at: float, reason: str) -> None:
    """Drop the current purpose and ask for a new choice."""
    ensure_brain(state).update(purpose=None, batches=0, replans=0, planned_at=None)
    mark_trigger(state, reason, at)


def report(state: dict, context: ActionContext, purpose_name: str, at: float, why: str) -> None:
    """Give up on a purpose: it scores lower for 10 game minutes and a new choice is asked for."""
    brain = ensure_brain(state)
    brain["penalties"][purpose_name] = at + PENALTY_GAME_SECONDS / context.clock_at(at)["time_scale"]
    purpose = PURPOSES.get(purpose_name)
    phrase = purpose.phrase if purpose else purpose_name.replace("_", " ")
    context.events.append((at, "plan", f"{state['name']} gave up trying to {phrase} ({why})."))
    finish_purpose(state, at, "plan_failed")


def forget_unreachable(context: ActionContext, purpose_name: str, failure: dict) -> None:
    """A place a purpose failed twice to find a way to is forgotten: a shelter go_home was after
    (so the next sheltered spot Mimo finds can become home), or an ore mine_ore was after (so it
    is not chosen again and again only to fail)."""
    cell = failure.get("cell")
    if failure.get("code") != "no_path" or context.db is None or not isinstance(cell, dict):
        return
    kinds = {"go_home": SHELTER_KINDS, "mine_ore": ("ore",)}.get(purpose_name, ())
    for kind in kinds:
        forget(context.db, kind, (cell["x"], cell["y"], cell["z"]))


def new_failure(state: dict, brain: dict) -> dict | None:
    """The last failure, unless the brain already dealt with it."""
    failure = state.get("last_failure")
    return failure if failure is not None and failure != brain["handled_failure"] else None


def plan_batch(purpose: Purpose, s: Situation, context: ActionContext) -> list[dict] | None:
    """The purpose's next batch: [] when it is finished, None when its planner broke."""
    if not is_valid(purpose, s):
        return []
    try:
        steps = purpose.plan(s, context)
        if not (isinstance(steps, list) and all(isinstance(step, dict) for step in steps)):
            raise TypeError(f"{purpose.name} planned {type(steps).__name__}, not a list of steps")
    except Exception as error:
        log_once(logger, f"{purpose.name} planner", error)
        return None
    return steps


def brain_plan(state: dict, context: ActionContext, at: float) -> list[dict]:
    """The next steps for Mimo's purpose. See the module docstring for the rules."""
    brain = ensure_brain(state)
    if brain["reflex"] is not None:
        reflex = by_name(brain["reflex"])
        resumed = end_reflex(state, at)
        if reflex is not None and reflex.ends_purpose and brain["purpose"] is not None:
            finish_purpose(state, at, "reflex_ended")
        if brain["purpose"] is None:
            resumed = kept_steps(resumed)
        if resumed:
            return resumed
    purpose = PURPOSES.get(brain["purpose"]) if brain["purpose"] else None
    if purpose is None:
        return waiting(state, context, at)
    failure = new_failure(state, brain)
    if failure is not None:
        escape = plan_escape(state, context, at)
        if escape is None:
            return [{"kind": "wait", "seconds": PENDING_WAIT}]  # no search left this tick; look again next tick
        brain["handled_failure"] = failure
        if escape:
            return escape
        if brain["replans"] >= 1:
            forget_unreachable(context, purpose.name, failure)
            report(state, context, purpose.name, at, failure["reason"])
            return waiting(state, context, at)
        brain["replans"] += 1
    elif brain["planned_at"] is not None:
        brain["batches"] += 1
        brain["replans"] = 0
    steps = plan_batch(purpose, in_tick(state, context, at), context)
    if steps is None:
        report(state, context, purpose.name, at, "its plan broke")
        return waiting(state, context, at)
    if not steps:
        finish_purpose(state, at, "plan_done")
        return waiting(state, context, at)
    brain["planned_at"] = at
    return [{**step, "purpose": purpose.name} for step in steps]


def discover(state: dict, context: ActionContext, at: float, what: str, kind: str, text: str) -> None:
    """Log and announce the first discovery of `what`; later ones stay quiet."""
    brain = ensure_brain(state)
    if what in brain["found"]:
        return
    brain["found"].append(what)
    context.events.append((at, kind, text))
    mark_trigger(state, "discovery", at)


def observe_step(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """Remember what a finished step showed: ores, recipes, water and visited places."""
    db = context.db
    if db is None:
        return
    kind, name = step["kind"], state["name"]
    if kind == "mine":
        cell = as_cell(step["target"])
        if step.get("block") in ORES:
            forget(db, "ore", cell)
        for near, material in ores_around(context.grid, cell):
            if remember(db, "ore", near, at, material):
                discover(state, context, at, material, "found", f"{name} spotted {label(material)}.")
    elif kind == "craft":
        learn(db, step["recipe"], at)
    elif kind == "smelt":
        learn(db, f"smelt_{step['item']}", at)
    elif kind in ("walk", "swim"):
        water = next((entry for entry in step["path"] if entry.get("swim")), None)
        if water is not None and remember(db, "water", as_cell(water), at):
            discover(state, context, at, "water", "discovered", f"{name} found water.")
        visit(db, as_cell(state["position"]), at)
    note_ground(state, step, context, at)
    learn_from_step(state, step, context, at)
    note_building(state, step, context, at)


def notice_step(state: dict, context: ActionContext, before: dict, surroundings: Surroundings,
                since: float, at: float) -> None:
    """After a vitals step: ask for a choice on crossings, dawn, dusk or a quiet game hour, and
    remember sheltered spots."""
    brain = ensure_brain(state)
    for reason in crossings(before, state["vitals"]):
        mark_trigger(state, reason, at, urgent=True)
    clock = context.clock_at(at)
    phase = phase_trigger(context.clock_at(since)["phase"], clock["phase"])
    if phase:
        mark_trigger(state, phase, at)
    asleep = (state.get("action") or {}).get("kind") == "sleep"
    if brain["pending"] is None and not asleep and hour_passed(brain, at, clock["time_scale"]):
        mark_trigger(state, "hour", at)
    if surroundings.sheltered and context.db is not None:
        cell = as_cell(state["position"])
        if remember(context.db, "home", cell, at):
            discover(state, context, at, "home", "discovered", f"{state['name']} found a sheltered spot and made it home.")
        else:
            remember(context.db, "shelter", cell, at)


BRAIN = Mind(plan=brain_plan, interrupt=reflex_hook, observe=observe_step, notice=notice_step)
