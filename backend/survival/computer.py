"""The thinking machine (Making, T3): a clock, a memory cell, a counter and Mimo's computer.

The owner, 2026-09-25: "it would be so cool for the pet to develop a computer or something like other
people have done in minecraft". The life goal "A thinking machine" (after the first circuits) is four
machines, each after the lesson it takes (backend.survival.tinker: the owner can teach it, or Mimo works
it out by watching the machine before):
- a clock (the lesson "clock"): an inverter whose spark comes round to it through three repeaters of
  delay 2: on for 7 steps, off for 7 (a lamp by it blinks every 7 game seconds);
- a memory cell ("latch"): two inverters that feed each other, a set button and a reset button, and a
  lamp that shows the bit it holds; Mimo presses set to try it and the lamp stays lit;
- a counter ("adder"): a slower clock (repeaters of delay 4: a tick every 13 game seconds, longer than a
  count takes to ripple through) driving four stages in a row, each a pair of repeaters locked from the
  side (signals: a locked repeater keeps what it gives out) with an inverter: the first repeater follows
  the stage's own output turned over while the stage's clock is low, the second copies it when the clock
  rises, so the stage flips once for each rise of its clock, and its turned-over output is the next
  stage's clock. Four lamps show the count in binary, 0 to 15 and round again, the lowest bit east;
- Mimo's computer ("adder"): the same four stages driven by a daylight sensor, so each dawn counts one
  more, a bell by the sensor that rings at dawn, and the lamps shown only while its lever is thrown (a
  joiner that ands each stage's bit with the lever's line). When it is first run it is set to the days
  Mimo has lived (STARTS: today's dawn counted, by day or by night), so it shows the game day in
  binary, the highest bit west, as long as it stands: "day 13 = 1101". 4 bits count to 15.
  It is named for Mimo (the final fix wave's M1): "Pip built Pip's computer."
A machine's parts are laid out as the rows below read (signals.parse). When Mimo throws the computer's
lever the first time: a notable "computer" event ("Pip built a machine that remembers how long it has
been alive!"). The readout (signals.READOUTS: the count, its bits and whether the lamps are shown) goes
to the viewer for its caption.

The goal: work out the clock, build it, work out the latch, build the memory cell, work out counting,
build the counter, build the computer. Rules score 45 plus a tenth of curiosity and of creativity and a
twentieth of diligence; reward 30 mood.
"""

from __future__ import annotations

import logging

from backend.survival.clock import NIGHT_PHASES, clock_at
from backend.survival.goals import Goal, Milestone, register_goal
from backend.survival.machines import MACHINE_GOALS, Machine, knows, machine_share, register_machine
from backend.survival.memory import structures
from backend.survival.once import log_once
from backend.survival.signals import FULL, READOUTS, STARTS, Circuit
from backend.survival.steps import as_cell
from backend.survival.structures import structure_at
from backend.survival.triggers import ensure_brain

logger = logging.getLogger(__name__)

GOAL = "thinking_machine"
BITS = 4
DAY_COLUMNS = (16, 11, 6, 1)  # each stage's column in the counter and the computer, the lowest bit first
REMEMBERS = "I built a machine that remembers how long I've been alive!"

CLOCK = ("w n>2>w . ",
         "w . . w * ",
         "w 2<2<w . ")

MEMORY = (". . * . ",
          "w w w B ",
          "n^Nv. . ",
          "w w w B ")

COUNTER = (". . . . . . . . . . . . . . . . . . . . w w w ",
           ". . . . . . . . . . . . . . . . . . . . 4^. nv",
           ". . . . . . . . . . . . . . . . . . . . 4^. 4v",
           ". . . . . . . . . . . . . . . . . . . . w w w ",
           ". . . . . . . . . . . . . . . . . . . . . w . ",
           ". . . . . . . . . . . . . . . . . . . . . w . ",
           ". . . . . . . . . . . . . . . . . . w w w w . ",
           "w w . w w w w . w w w w . w w w w . w . . w . ",
           "w 2v1<w . w 2v1<w . w 2v1<w . w 2v1<w . . w . ",
           "n^2v1<1<w n^2v1<1<w n^2v1<1<w n^2v1<1<w n<w . ",
           "w w . . w w w . . w w w . . w w w . . . . . . ",
           ". * . . . . * . . . . * . . . . * . . . . . . ")

COMPUTER = (". . . . . . . . . . . . . . . . . . b . . . ",
            "w w . w w w w . w w w w . w w w w . S w w w ",
            "w 2v1<w . w 2v1<w . w 2v1<w . w 2v1<w . . w ",
            "n^2v1<1<w n^2v1<1<w n^2v1<1<w n^2v1<1<w n<w ",
            "w w . . w w w . . w w w . . w w w . . . . . ",
            "w . . . . w . . . . w . . . . w . . . . . . ",
            "w av1<w . w av1<w . w av1<w . w av1<w . . . ",
            ". * . w . . * . w . . * . w . . * . w . . . ",
            ". . . w . . . . w . . . . w . . . . w . . . ",
            "w w w w w w w w w 1<w w w w w w w w w L . . ")
# Where each stage's pair of repeaters is, as rows of the layouts: (first, second).
COUNTER_ROWS = (8, 9)
COMPUTER_ROWS = (2, 3)

register_machine(Machine("clock", "a clock", "clock", CLOCK))
register_machine(Machine("memory_cell", "a memory cell", "latch", MEMORY))
register_machine(Machine("counter", "a counter", "adder", COUNTER, try_out=False, reach=24))
register_machine(Machine("computer", "{name}'s computer", "adder", COMPUTER, reach=24))  # M1: Pip's computer
MACHINE_GOALS[GOAL] = ("clock", "memory_cell", "counter", "computer")


def pairs(circuit: Circuit, rows: tuple[int, int], corner) -> list[tuple[int | None, int | None]]:
    """(first repeater, second repeater) of each stage, the lowest bit first (None where one is missing),
    from the layout's top left corner."""
    at = {part[0]: index for index, part in enumerate(circuit.parts)}
    ox, y, oz = corner
    return [(at.get((ox + column, y, oz + rows[0])), at.get((ox + column, y, oz + rows[1])))
            for column in DAY_COLUMNS]


def computer_start(life: dict, at: float, scale: float, circuit: Circuit, corner) -> tuple[dict, dict]:
    """signals.STARTS: the count set to the days Mimo has lived, today's dawn included (day_number % 16),
    by day or by night. Nothing is forced: the sensor is read as it stands. Each stage's second repeater
    holds its bit; its first one holds the same bit while its stage's clock is high: for the lowest stage
    that is the sensor (high by day), for the rest the bit below it being 0."""
    clock = clock_at(life.get("born_at", 0.0), at, scale)
    by_day = clock["phase"] not in NIGHT_PHASES
    value = clock["day_number"] % (1 << BITS)
    held = {}
    for bit, (first, second) in enumerate(pairs(circuit, COMPUTER_ROWS, corner)):
        on = FULL if (value >> bit) & 1 else 0
        if second is not None:
            held[second] = on
        high = by_day if bit == 0 else not (value >> (bit - 1)) & 1
        if first is not None and high:
            held[first] = on
    return held, {}


def readout(rows: tuple[int, int], always_shown: bool = False):
    def read(circuit: Circuit, state: dict, corner) -> dict:
        """The count the stages hold, its bits (highest first) and whether its lamps are shown: for the
        computer (fix round 1), its lever must be there and thrown, not merely absent (`all` of no levers
        is true, which used to show the caption while a lever-less or lever-gone circuit was dark); the
        counter (`always_shown`) is always shown, having no lever to gate it."""
        value = sum(1 << bit for bit, (_, second) in enumerate(pairs(circuit, rows, corner))
                    if second is not None and state["out"].get(second, 0) > 0)
        if always_shown:
            shown = True
        else:
            levers = [index for index, part in enumerate(circuit.parts) if part[1] == "lever"]
            shown = bool(levers) and all(state["out"].get(index, 0) > 0 for index in levers)
        return {"value": value, "bits": format(value, f"0{BITS}b"), "shown": shown}
    return read


STARTS["computer"] = computer_start
READOUTS["computer"] = readout(COMPUTER_ROWS)
READOUTS["counter"] = readout(COUNTER_ROWS, always_shown=True)


def observe_computer(state: dict, step: dict, context, at: float) -> None:
    """After a finished step (brain.observe_step): the first time Mimo throws its computer's lever, a notable
    "computer" event and the thought. A crash is logged once and the tick goes on."""
    if step["kind"] != "flip" or context.db is None:
        return
    try:
        brain = ensure_brain(state)
        number = structure_at(context.db, as_cell(step["target"]))
        found = next((row for row in structures(context.db, ("machine",)) if row["id"] == number), None)
        if brain.get("computer_told") or found is None or found["data"].get("style", {}).get("machine") != "computer":
            return
        brain["computer_told"] = True
        state["last_thought"] = REMEMBERS
        context.events.append((at, "computer", f"{state['name']} built a machine that remembers how long it has "
                                               "been alive!"))
    except Exception as error:
        log_once(logger, "computer", error)


register_goal(Goal(
    GOAL, "A thinking machine",
    "People build computers out of redstone: Mimo can build one of copper that counts the days it has lived.",
    (Milestone("Work out how a clock ticks", knows("clock"), ("tinker",)),
     Milestone("Build a clock", machine_share("clock"), ("build_machine", "mine_ore"), ("repeater",)),
     Milestone("Work out how to remember", knows("latch"), ("tinker",)),
     Milestone("Build a memory cell", machine_share("memory_cell"), ("build_machine", "mine_ore"), ("button",)),
     Milestone("Work out how to count", knows("adder"), ("tinker",)),
     Milestone("Build a counter", machine_share("counter"), ("build_machine", "mine_ore"), ("repeater",)),
     Milestone("Build a computer that counts its days", machine_share("computer"),
               ("build_machine", "mine_ore", "gather_materials"), ("daylight_sensor", "bell"))),
    score=lambda s: 45.0 + s.trait("curiosity") / 10 + s.trait("creativity") / 10 + s.trait("diligence") / 20,
    thought="People build computers out of sparks. I want to build one that counts my days.",
    after=("first_circuits",), reward=30.0))
