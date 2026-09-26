"""What Mimo knows about making (Making, T2): the lessons, an old manual, and tinkering.

Knowledge gates the making (the spec): wiring needs the lesson that copper carries a spark, and each
larger machine a lesson of its own (the clock, the latch, the adder). They are L4b journal lessons
(journal.LESSONS, kind "making"), so the owner can teach them (Part A's teaching makes every lesson in
the table teachable) and the journal shows them. Mimo gets them in two ways of its own:
- An old manual, until L5's ruins carry them: mining copper ore at DEEP_COPPER or deeper before it
  knows that copper carries a spark turns one up 1 time in MANUAL_ODDS (a roll on the world seed and
  the cell): a notable "found" event ("Pip found an old manual in the copper seam."), and the lesson.
- Tinkering, the `tinker` purpose, "tinker": a curious experiment. With copper to hand and the lesson
  not known, Mimo makes a lever, a copper wire and a lamp (making.craft_plan), lays them in a row on
  open ground beside it, throws the lever and fiddles with them for TINKER_SECONDS, then takes them
  back. Each later lesson it works out from the machine before: the clock by watching its night-light
  (an inverter), the latch by watching its clock, the adder (counting) by watching its memory cell; it
  walks up to that machine and watches it for TINKER_SECONDS. When the look ends it has worked it out
  with a chance of 0.25 plus curiosity / 200 (a roll on the seed, the cell and the time): the lesson
  is learned (on the bench, the lamp lights up and the wire glows as it does); otherwise it tries
  again after TINKER_REST. Day work in the work band, by home: 35 plus a quarter of curiosity.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.services.blocks import is_replaceable
from backend.survival import nature
from backend.survival.clock import DAY_SECONDS
from backend.survival.curiosity import value_of
from backend.survival.foraging import reach_steps
from backend.survival.grid import Cell
from backend.survival.journal import LESSONS, Lesson, journal_ready, learn_lesson, taught, teach
from backend.survival.machines import built, machines_built
from backend.survival.making import craft_plan, place_steps
from backend.survival.once import log_once
from backend.survival.pens import near_home
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import as_cell, seed_of
from backend.survival.structures import blueprint_of, reserved
from backend.survival.triggers import ensure_brain

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

SPARK = "copper_spark"
DEEP_COPPER = 0  # copper ore at this height or lower may hold an old manual...
MANUAL_ODDS = 6  # ...one time in this many
MANUAL_CHANNEL = 96
TINKER_CHANNEL = 97
TINKER_SECONDS = 20.0  # game seconds a session of tinkering takes
TINKER_REST = DAY_SECONDS / 2  # game seconds after a session that found nothing before the next
BENCH = ("lever", "copper_wire", "lamp")  # what Mimo lays out to see what copper does
# Each later lesson, and the machine Mimo works it out from.
WORKED_OUT = (("clock", "night_light"), ("latch", "clock"), ("adder", "memory_cell"))

teach(
    Lesson(SPARK, "making", "copper wire", "Copper carries a spark: a lever, copper wire and a lamp make light.",
           "wires up machines", ("I flipped the lever and the lamp lit up! Copper carries a spark.",
                                 "A spark runs down the copper wire. I can build with this!")),
    Lesson("clock", "making", "a clock",
           "An inverter whose spark comes back round to it through repeaters flickers on and off: a clock.",
           "builds a clock", ("A spark chasing its own tail: tick, tock!", "Round and round the repeaters: a clock.")),
    Lesson("latch", "making", "a memory cell",
           "Two inverters that feed each other hold the spark on one side: a memory cell remembers one bit.",
           "builds a memory cell", ("Two inverters holding hands remember!",
                                    "Press set and it stays lit. It remembers.")),
    Lesson("adder", "making", "counting in twos",
           "Counting in twos: each lamp flips when the lamp before it goes dark.",
           "builds a counter and a computer", ("One, ten, eleven, a hundred... I can count in twos!",
                                                "Each lamp flips when the one before it goes out.")),
)


def tinker_state(state: dict) -> dict:
    """The brain's tinkering: the lesson a session is after, and when one last found nothing."""
    found = ensure_brain(state).setdefault("tinker", {})
    found.setdefault("idea", None)
    found.setdefault("tried", None)
    return found


# The old manual ----------------------------------------------------------------------------------

def observe_tinker(state: dict, step: dict, context, at: float) -> None:
    """After a finished step (brain.observe_step): an old manual in deep copper, and the end of a
    session of tinkering. A crash is logged once and the tick goes on."""
    if not journal_ready(state, context.db):
        return
    try:
        if step["kind"] == "mine" and step.get("block") == "copper_ore":
            cell = as_cell(step["target"])
            if (cell[1] <= DEEP_COPPER and not taught(context.db, SPARK)
                    and nature.roll(seed_of(state), cell, MANUAL_CHANNEL) < 1 / MANUAL_ODDS):
                context.events.append((at, "found", f"{state['name']} found an old manual in the copper seam."))
                learn_lesson(state, context, at, SPARK)
        elif step["kind"] == "wait" and step.get("purpose") == "tinker":
            finish_session(state, context, at)
    except Exception as error:
        log_once(logger, "tinker", error)


# Tinkering ---------------------------------------------------------------------------------------

def has_copper(s: Situation) -> bool:
    return s.count("copper_ingot", "copper_ore", "copper_wire") > 0


def next_idea(s: Situation) -> str | None:
    """The lesson Mimo could work out by tinkering now, or None."""
    known = set(s.lessons)
    if SPARK not in known:
        return SPARK if has_copper(s) else None
    for lesson, machine in WORKED_OUT:
        if lesson not in known:
            return lesson if built(s, machine) else None
    return None


def tried_lately(s: Situation) -> bool:
    tried = (s.brain.get("tinker") or {}).get("tried")
    return tried is not None and (s.at - tried) * s.scale < TINKER_REST


def bench_cells(s: Situation) -> list[Cell] | None:
    """Three open cells in a row on firm ground beside Mimo, clear of anything it built or tends."""
    x, y, z = s.here
    for dx, dz in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        cells = [(x + dx * step, y, z + dz * step) for step in (1, 2, 3)]
        if all(is_replaceable(s.grid.material(*cell)) and s.grid.material(*cell) != "water"
               and s.grid.solid((cell[0], cell[1] - 1, cell[2])) and not reserved(s.grid, cell) for cell in cells):
            return cells
    return None


def bench_plan(s: Situation) -> list[dict] | None:
    """Make the bench's lever, wire and lamp, lay them out, throw the lever, fiddle, take them back."""
    cells = bench_cells(s)
    crafting = craft_plan(s, {item: 1 for item in BENCH}) if cells is not None else None
    if crafting is None:
        return None
    places = [{"kind": "place", "target": list(cell), "block": item} for cell, item in zip(cells, BENCH)]
    fiddle = [{"kind": "flip", "target": list(cells[0])},
              {"kind": "wait", "seconds": max(1.0, TINKER_SECONDS / s.scale)}]
    back = [{"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(cells)]
    return crafting + places + fiddle + back


def watch_plan(s: Situation, machine: str) -> list[dict] | None:
    """Walk up to the machine and watch it for TINKER_SECONDS."""
    found = machines_built(s).get(machine)
    if found is None:
        return None
    blueprint = blueprint_of(found)
    look = {"kind": "wait", "seconds": max(1.0, TINKER_SECONDS / s.scale)}
    jobs = [(blueprint.anchor, [look])]
    return place_steps(s, blueprint.stands, jobs) or reach_steps(s, jobs)


def session(s: Situation) -> list[dict] | None:
    """The steps of a session for the idea Mimo is after now (read once per Situation)."""
    def look() -> list[dict] | None:
        idea = next_idea(s)
        if idea is None:
            return None
        if idea == SPARK:
            return bench_plan(s)
        return watch_plan(s, dict(WORKED_OUT)[idea])
    return s.sensed("tinker session", look)


def tinker_valid(s: Situation) -> bool:
    return not s.night and near_home(s) and not tried_lately(s) and session(s) is not None


def chance(state: dict) -> float:
    return 0.25 + value_of(state.get("brain")) / 200


def lucky(state: dict, at: float) -> bool:
    """Whether a session worked it out (a roll on the seed, where Mimo stands and the time)."""
    return nature.roll(seed_of(state), as_cell(state["position"]), TINKER_CHANNEL, int(at)) < chance(state)


def finish_session(state: dict, context, at: float) -> None:
    """The session's look is over: the idea worked out (the lesson learned, the bench's lamp and wire lit)
    or not (tried again after TINKER_REST)."""
    tinkering = tinker_state(state)
    idea, tinkering["idea"] = tinkering["idea"], None
    if idea is None:
        return
    if not lucky(state, at):
        tinkering["tried"] = at
        return
    learn_lesson(state, context, at, idea)
    if idea == SPARK:
        x, y, z = as_cell(state["position"])
        for dx, dz in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            cells = [(x + dx * step, y, z + dz * step) for step in (1, 2, 3)]
            if [context.grid.material(*cell) for cell in cells] == ["lever_on", "copper_wire", "lamp"]:
                context.grid.put(*cells[1], "copper_wire_lit")
                context.grid.put(*cells[2], "lamp_lit")
                break


def plan_tinker(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0 or not tinker_valid(s):
        return []
    tinker_state(s.state)["idea"] = next_idea(s)
    return list(session(s))


def tinker_facts(s: Situation) -> str:
    idea = next_idea(s)
    if idea == SPARK:
        return f"wants to work out what copper does with a lever and a lamp; {len(s.lessons)} lessons learned"
    return f"wants to work out {LESSONS[idea].words} from its {dict(WORKED_OUT)[idea].replace('_', ' ')}"


register(Purpose(
    "tinker", "tinker",
    "Try things out with copper, levers and lamps, or watch a machine it built, to work out something new.",
    valid=tinker_valid, facts=tinker_facts, score=lambda s: 35.0 + value_of(s.brain) / 4, plan=plan_tinker,
    thoughts=("What happens if I connect this to that?", "Let me fiddle with this a little.")))
