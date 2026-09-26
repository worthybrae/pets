"""The signal engine (Making, T2): copper wire carries a spark, and the machines Mimo builds work.

A circuit is a list of parts, [x, y, z, kind, facing, setting] (`parse` reads one from a layout), each
drawn by a block that shows whether it is on (MATERIALS):
- sources: a lever (on while thrown: lever_on), a button (button_on for BUTTON_STEPS steps once pressed,
  a one-second pulse), a pressure plate (on while Mimo stands on it, or stood there in the last
  PLATE_SECONDS) and a daylight sensor (on by day, off at night);
- wire (copper_wire, copper_wire_lit while powered): power 15 where a source or a gate feeds it, one less
  each block along it, so it carries a spark up to 15 blocks;
- gates, each facing the way it gives out (its front) and taking in from behind (a joiner from its two
  sides): a repeater, on `delay` steps (1 to 4) after its input (T3: while a repeater or joiner facing into
  one of its sides is on, it is locked and keeps what it gives out, as in Minecraft, so a pair of repeaters
  holds a bit); an inverter, on one step after its input goes off and off one step after it comes on
  (setting 1: it starts on); a joiner, one step later on when both sides are ("and") or either side is
  ("or");
- outputs: a lamp (lamp_lit while powered), a door (open while powered: the viewer swings it) and a bell
  (it rings, a routine "bell" event, as it becomes powered).
A source powers the wire, gates and outputs beside it (north, east, south or west, on its level); a
gate only what is in front of it; an output is powered by a powered wire or a source beside it, or a
gate facing it. Wires join the wires beside them. A part whose block is gone is left out.

Each step is synchronous and deterministic: the sources are read at the step's own time (a plate from
where Mimo's walks had taken it by then: a cell a walk under way reaches later does not count), the
wires fed by what changed are worked out again (breadth first from what feeds them), and the gates and
outputs that read something that changed (and repeaters with a signal still under way) are worked out;
a gate's new output shows from the next step. Only what changed is worked out again, and a circuit
where nothing is under way and no source changed is quiet: it costs nothing but reading its sources
(unless Mimo stepped onto or off one of its plates in the meantime).

The machines (kind "machine" structures, backend.survival.machines) carry their circuit in their design
(style "circuit"). Once one is done, `run_signals` (last in the tick's transaction, after renewal and the
creatures) brings its circuit up to the tick's time, STEP game seconds a step, and draws what changed. The
work is bounded: at most MAX_CELLS cells worked out per world per tick (a wire's power, a gate, an
output): before each step the engine bounds what it can touch (`step_bound`: the wires of every net fed by
what changed, and every gate and output that reads them or something that changed, and the repeaters with
a signal under way) and takes it only while that fits in what is left; a circuit that runs out waits for
the next tick, and one more than MAX_BEHIND steps behind skips ahead. (A step bigger than the whole budget
is taken alone, first in a tick, so no machine stalls; none of Mimo's machines has one.) A machine is
started when it is first run, and again whenever which of its parts are there changes: its gates settle
(repeaters filled with what they read, an inverter set to start on held on) with its starting outputs
held (STARTS, by machine name: the computer's count), then every gate is worked out once from that. A
start is worked out outside the budget. A machine that crashes is logged once and left for that tick;
the others still run.

The state of each machine is kept in the machine_signals table, one row a machine written only when
it changed: the time it is at, which of its parts it runs without, its gates' outputs, its repeaters'
registers, the power in its wires, what it draws lit, its pressed buttons. A world only ever read (an
archive) may lack the table: it reads as no signals (`machine_state`; the viewer's
backend.survival.machines.workshop_view). GETs never write.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from backend.survival.clock import NIGHT_PHASES, clock_at
from backend.survival.grid import Cell, Grid
from backend.survival.once import log_once

logger = logging.getLogger(__name__)

STEP = 0.5  # game seconds a signal step lasts
FULL = 15  # a source's or gate's power; a wire's falls by one a block
MAX_CELLS = 256  # cells worked out per world per tick, at most
MAX_BEHIND = 240  # steps a circuit may fall behind the clock before it skips ahead
BUTTON_STEPS = 2  # a button's pulse: one game second
PLATE_SECONDS = 1.0  # a pressure plate stays down this long after Mimo steps off it
SETTLE_PASSES = 24  # how many times a starting circuit's gates are worked out, to settle
KIND = "machine"

MATERIALS = {
    "wire": ("copper_wire", "copper_wire_lit"),
    "lever": ("lever", "lever_on"),
    "button": ("button", "button_on"),
    "plate": ("pressure_plate", "pressure_plate"),
    "sensor": ("daylight_sensor", "daylight_sensor"),
    "repeater": ("repeater", "repeater_lit"),
    "inverter": ("inverter", "inverter_lit"),
    "joiner": ("joiner", "joiner_lit"),
    "lamp": ("lamp", "lamp_lit"),
    "door": ("door", "door"),
    "bell": ("bell", "bell"),
}
SOURCES = ("lever", "button", "plate", "sensor")
GATES = ("repeater", "inverter", "joiner")
LOCKERS = ("repeater", "joiner")  # T3: what locks a repeater, facing into its side
OUTPUTS = ("lamp", "door", "bell")
DRAWN = ("wire", "repeater", "inverter", "joiner", "lamp")  # the engine draws these lit or not
DIRECTIONS = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
LEFT = {"north": "west", "east": "north", "south": "east", "west": "south"}
RIGHT = {"north": "east", "east": "south", "south": "west", "west": "north"}
AROUND = tuple(DIRECTIONS.values())

# A layout: rows north to south, two characters a cell west to east. "w " wire, "L " lever, "B " button,
# "P " plate, "S " daylight sensor, "* " lamp, "b " bell, "D " a door; a gate is its key and the way it
# faces (">" east, "<" west, "^" north, "v" south): "1>" to "4>" a repeater of that delay, "n>" an
# inverter ("N>" one that starts on), "a>" a joiner that ands, "o>" one that ors; ". " nothing.
KEYS = {"w": "wire", "L": "lever", "B": "button", "P": "plate", "S": "sensor", "*": "lamp", "b": "bell", "D": "door"}
GATE_KEYS = {"1": ("repeater", 1), "2": ("repeater", 2), "3": ("repeater", 3), "4": ("repeater", 4),
             "n": ("inverter", 0), "N": ("inverter", 1), "a": ("joiner", "and"), "o": ("joiner", "or")}
ARROWS = {">": "east", "<": "west", "^": "north", "v": "south"}

# Machine name -> start(life, at, scale, circuit, corner) giving ({part index: output held while it
# settles}, {source index: reading while it settles}): what a machine starts from. `corner` is the least
# x and z of all its parts, present or not, and their height: where its layout's top left is.
STARTS: dict[str, Callable] = {}
# T3: machine name -> readout(circuit, state, corner) giving what the viewer shows of it (the computer's
# count, backend.survival.computer).
READOUTS: dict[str, Callable] = {}


def parse(rows, origin: Cell = (0, 0, 0)) -> list[list]:
    """The parts of a layout (see KEYS), its top left cell at `origin`."""
    ox, oy, oz = origin
    parts: list[list] = []
    for row, line in enumerate(rows):
        for column in range(0, len(line), 2):
            key, arrow = line[column], line[column + 1:column + 2] or " "
            cell = [ox + column // 2, oy, oz + row]
            if key in KEYS:
                parts.append([*cell, KEYS[key], "", 0])
            elif key in GATE_KEYS:
                kind, setting = GATE_KEYS[key]
                parts.append([*cell, kind, ARROWS[arrow], setting])
            elif key != ".":
                raise ValueError(f"unknown part {key!r} in a layout")
    return parts


def ahead(cell: Cell, facing: str) -> Cell:
    dx, dz = DIRECTIONS[facing]
    return cell[0] + dx, cell[1], cell[2] + dz


def behind(cell: Cell, facing: str) -> Cell:
    dx, dz = DIRECTIONS[facing]
    return cell[0] - dx, cell[1], cell[2] - dz


# Compiling a circuit -----------------------------------------------------------------------------

Ref = tuple[str, int]  # ("w", wire index): the power in that wire; ("e", part index): that part's output


@dataclass(frozen=True)
class Circuit:
    parts: tuple[tuple, ...]  # (cell, kind, facing, setting)
    nets: tuple[tuple[int, ...], ...]  # the wires of each net (part indices)
    net_of: dict  # wire -> its net
    feeders: dict  # net -> ((emitter, wire it feeds at FULL), ...)
    inputs: dict  # gate or output -> (ref, ...): a gate's input(s) in order, an output's all around
    net_readers: dict  # net -> (gate or output, ...)
    emitter_readers: dict  # emitter -> (gate or output, ...)
    emitter_nets: dict  # emitter -> (net, ...)

    def kind(self, index: int) -> str:
        return self.parts[index][1]


def powers(parts, index: int, cells: dict) -> list[Cell]:
    """The cells a source or a gate gives its power to: all four around a source, a gate's front."""
    cell, kind, facing, _ = parts[index]
    if kind in SOURCES:
        return [(cell[0] + dx, cell[1], cell[2] + dz) for dx, dz in AROUND]
    return [ahead(cell, facing)] if kind in GATES else []


def reads_from(parts, index: int) -> list[Cell]:
    """The cells a gate takes in from: behind it, or a joiner's left and right sides."""
    cell, kind, facing, _ = parts[index]
    if kind == "joiner":
        return [ahead(cell, LEFT[facing]), ahead(cell, RIGHT[facing])]
    return [behind(cell, facing)]


@lru_cache(maxsize=64)
def compile_circuit(parts: tuple[tuple, ...]) -> Circuit:
    """The nets and who reads and feeds what, for parts (cell, kind, facing, setting)."""
    cells = {part[0]: index for index, part in enumerate(parts)}
    wires = [index for index, part in enumerate(parts) if part[1] == "wire"]
    net_of: dict[int, int] = {}
    nets: list[tuple[int, ...]] = []
    for wire in wires:
        if wire in net_of:
            continue
        net, frontier = [wire], [wire]
        net_of[wire] = len(nets)
        while frontier:
            x, y, z = parts[frontier.pop()][0]
            for dx, dz in AROUND:
                near = cells.get((x + dx, y, z + dz))
                if near is not None and parts[near][1] == "wire" and near not in net_of:
                    net_of[near] = len(nets)
                    net.append(near)
                    frontier.append(near)
        nets.append(tuple(sorted(net)))
    emitters = [index for index, part in enumerate(parts) if part[1] in SOURCES or part[1] in GATES]
    feeders: dict[int, list] = {}
    emitter_nets: dict[int, list] = {}
    emitter_readers: dict[int, list] = {}
    for emitter in emitters:
        for cell in powers(parts, emitter, cells):
            target = cells.get(cell)
            if target is None:
                continue
            if parts[target][1] == "wire":
                net = net_of[target]
                feeders.setdefault(net, []).append((emitter, target))
                if net not in emitter_nets.setdefault(emitter, []):
                    emitter_nets[emitter].append(net)
    inputs: dict[int, list] = {}
    for index, (cell, kind, facing, _) in enumerate(parts):
        if kind in GATES:
            sides = reads_from(parts, index)
        elif kind in OUTPUTS:
            sides = [(cell[0] + dx, cell[1], cell[2] + dz) for dx, dz in AROUND]
        else:
            continue
        refs = []
        for side in sides:
            other = cells.get(side)
            ref = None
            if other is not None:
                other_kind = parts[other][1]
                if other_kind == "wire":
                    ref = ("w", other)
                elif other_kind in SOURCES or (other_kind in GATES and ahead(side, parts[other][2]) == cell):
                    ref = ("e", other)
            if ref is not None or kind in GATES:
                refs.append(ref)
        if kind == "repeater":  # T3: a repeater or joiner facing into a repeater's side locks it
            for side in (ahead(cell, LEFT[facing]), ahead(cell, RIGHT[facing])):
                other = cells.get(side)
                if other is not None and parts[other][1] in LOCKERS and ahead(side, parts[other][2]) == cell:
                    refs.append(("e", other))
        inputs[index] = refs
    net_readers: dict[int, list] = {}
    for reader, refs in inputs.items():
        for ref in refs:
            if ref is None:
                continue
            if ref[0] == "w":
                net = net_of[ref[1]]
                if reader not in net_readers.setdefault(net, []):
                    net_readers[net].append(reader)
            elif reader not in emitter_readers.setdefault(ref[1], []):
                emitter_readers[ref[1]].append(reader)
    freeze = lambda table: {key: tuple(value) for key, value in table.items()}  # noqa: E731
    return Circuit(tuple(parts), tuple(nets), net_of, freeze(feeders), freeze(inputs), freeze(net_readers),
                   freeze(emitter_readers), freeze(emitter_nets))


# Running a circuit -------------------------------------------------------------------------------

def fresh_state(circuit: Circuit) -> dict:
    """Everything off, the repeaters' registers empty."""
    parts = circuit.parts
    return {"at": None, "out": {index: 0 for index, part in enumerate(parts) if part[1] in SOURCES + GATES},
            "reg": {index: [0] * max(0, int(part[3]) - 1) for index, part in enumerate(parts) if part[1] == "repeater"},
            "power": {index: 0 for index, part in enumerate(parts) if part[1] == "wire"},
            "lit": {index: 0 for index, part in enumerate(parts) if part[1] in OUTPUTS},
            "press": {}, "fresh": [], "pending": [], "quiet": False}


def value(state: dict, ref: Ref | None) -> int:
    if ref is None:
        return 0
    return state["power"][ref[1]] if ref[0] == "w" else state["out"][ref[1]]


def gate_output(circuit: Circuit, state: dict, gate: int, instant: bool = False) -> int:
    """What a gate gives out next from what it reads now. A repeater pushes its input into its register
    (the delay - 1 inputs before) and gives out the oldest (`instant`, when settling: its register fills
    with what it reads), so what it reads shows at its front `delay` steps later."""
    _, kind, _, setting = circuit.parts[gate]
    refs = circuit.inputs[gate]
    if kind == "repeater":
        register = state["reg"][gate]
        if any(value(state, ref) > 0 for ref in refs[1:]):  # locked: it keeps what it gives out
            register[:] = [1 if state["out"][gate] else 0] * len(register)
            return state["out"][gate]
        on = 1 if value(state, refs[0]) > 0 else 0
        if instant:
            register[:] = [on] * len(register)
            return FULL if on else 0
        register.append(on)
        return FULL if register.pop(0) else 0
    if kind == "inverter":
        return 0 if value(state, refs[0]) > 0 else FULL
    left, right = (value(state, ref) > 0 for ref in refs)
    return FULL if (left and right if setting == "and" else left or right) else 0


def net_power(circuit: Circuit, state: dict, net: int) -> dict[int, int]:
    """The power in each wire of a net: FULL where a powered emitter feeds it, one less each wire on."""
    parts = circuit.parts
    found = {wire: 0 for wire in circuit.nets[net]}
    frontier = sorted({wire for emitter, wire in circuit.feeders.get(net, ()) if state["out"][emitter] > 0})
    for wire in frontier:
        found[wire] = FULL
    cells = {parts[wire][0]: wire for wire in circuit.nets[net]}
    while frontier:
        ahead_frontier = []
        for wire in frontier:
            x, y, z = parts[wire][0]
            for dx, dz in AROUND:
                near = cells.get((x + dx, y, z + dz))
                if near is not None and found[near] < found[wire] - 1:
                    found[near] = found[wire] - 1
                    ahead_frontier.append(near)
        frontier = ahead_frontier
    return found


def changed_now(circuit: Circuit, state: dict, readings: dict[int, int]) -> set[int]:
    """The emitters whose output a step with these readings starts from changed: the gates that changed
    last step, and the sources that read differently now."""
    return set(state["fresh"]) | {source for source, reading in readings.items() if state["out"][source] != reading}


def step_bound(circuit: Circuit, state: dict, readings: dict[int, int]) -> int:
    """At most how many cells the next step works out (see the module docstring)."""
    changed = changed_now(circuit, state, readings)
    nets = {net for emitter in changed for net in circuit.emitter_nets.get(emitter, ())}
    readers = {reader for emitter in changed for reader in circuit.emitter_readers.get(emitter, ())}
    readers.update(reader for net in nets for reader in circuit.net_readers.get(net, ()))
    return sum(len(circuit.nets[net]) for net in nets) + len(readers | set(state["pending"]))


def step(circuit: Circuit, state: dict, readings: dict[int, int]) -> tuple[int, list[int]]:
    """One signal step: the sources read, what changed worked out again. Returns the cells worked out
    and the bells that rang."""
    cost = 0
    changed = set(state["fresh"])
    for source, reading in readings.items():
        if state["out"][source] != reading:
            state["out"][source] = reading
            changed.add(source)
    dirty_nets = {net for emitter in changed for net in circuit.emitter_nets.get(emitter, ())}
    readers = {reader for emitter in changed for reader in circuit.emitter_readers.get(emitter, ())}
    for net in sorted(dirty_nets):
        cost += len(circuit.nets[net])
        found = net_power(circuit, state, net)
        if any(state["power"][wire] != power for wire, power in found.items()):
            state["power"].update(found)
            readers.update(circuit.net_readers.get(net, ()))
    readers.update(state["pending"])
    outputs, pending, rang = {}, [], []
    for reader in sorted(readers):
        cost += 1
        kind = circuit.kind(reader)
        if kind in GATES:
            output = gate_output(circuit, state, reader)
            if output != state["out"][reader]:
                outputs[reader] = output
            register = state["reg"].get(reader)
            if register is not None and any(bit != (1 if output else 0) for bit in register):
                pending.append(reader)  # a signal still on its way through the repeater
        else:
            powered = 1 if any(value(state, ref) > 0 for ref in circuit.inputs[reader]) else 0
            if powered and not state["lit"][reader] and kind == "bell":
                rang.append(reader)
            state["lit"][reader] = powered
    state["out"].update(outputs)
    state["fresh"] = sorted(outputs)
    state["pending"] = sorted(pending)
    state["quiet"] = not state["fresh"] and not state["pending"] and not state["press"]
    return cost, rang


def settle(circuit: Circuit, state: dict, readings: dict[int, int], held: dict[int, int]) -> None:
    """Start a circuit: its sources as read, the `held` outputs kept, every other gate worked out again
    SETTLE_PASSES times with its repeaters' registers filled, then everything worked out once more."""
    held = {**{index: FULL for index, part in enumerate(circuit.parts) if part[1] == "inverter" and part[3] == 1},
            **held}
    state["out"].update(readings)
    state["out"].update(held)
    for gate, output in held.items():  # a held repeater has been giving that out all along
        if gate in state["reg"]:
            state["reg"][gate][:] = [1 if output else 0] * len(state["reg"][gate])
    gates = [index for index, part in enumerate(circuit.parts) if part[1] in GATES and index not in held]
    for _ in range(SETTLE_PASSES):
        for net in range(len(circuit.nets)):
            state["power"].update(net_power(circuit, state, net))
        outputs = {gate: gate_output(circuit, state, gate, instant=True) for gate in gates}
        state["out"].update(outputs)
    for net in range(len(circuit.nets)):
        state["power"].update(net_power(circuit, state, net))
    for index, part in enumerate(circuit.parts):
        if part[1] in OUTPUTS:
            state["lit"][index] = 1 if any(value(state, ref) > 0 for ref in circuit.inputs[index]) else 0
    state["fresh"] = [index for index, part in enumerate(circuit.parts) if part[1] in SOURCES + GATES]
    state["pending"] = gates
    state["quiet"] = False
    step(circuit, state, readings)  # every gate worked out once from what it reads, outside any budget


def drawn_on(circuit: Circuit, state: dict, index: int) -> bool:
    kind = circuit.kind(index)
    if kind == "wire":
        return state["power"][index] > 0
    if kind in GATES:
        return state["out"][index] > 0
    return bool(state["lit"].get(index))


# Machines in the world ---------------------------------------------------------------------------

def create_signal_table(db: sqlite3.Connection) -> None:
    """The machines' states (run inside the caller's BEGIN IMMEDIATE; running it again changes nothing)."""
    db.execute("CREATE TABLE IF NOT EXISTS machine_signals (structure INTEGER PRIMARY KEY, at REAL NOT NULL, "
               "data TEXT NOT NULL)")


def missing_table(error: sqlite3.OperationalError) -> bool:
    return "no such table" in str(error)


INDEXED = ("out", "reg", "power", "lit", "press")  # the state's tables keyed by part index


def encode(state: dict) -> str:
    return json.dumps({key: ({str(index): value for index, value in item.items()} if key in INDEXED else item)
                       for key, item in state.items()}, separators=(",", ":"))


def decode(data: str) -> dict:
    raw = json.loads(data)
    return {key: ({int(index): value for index, value in item.items()} if key in INDEXED else item)
            for key, item in raw.items()}


def machine_state(db: sqlite3.Connection, number: int) -> dict | None:
    """A machine's signal state, or None before it first ran (or in a world without the table)."""
    try:
        row = db.execute("SELECT data FROM machine_signals WHERE structure=?", (number,)).fetchone()
    except sqlite3.OperationalError as error:
        if missing_table(error):
            return None
        raise
    return None if row is None else decode(row[0])


def save_state(db: sqlite3.Connection, number: int, state: dict) -> None:
    db.execute("INSERT INTO machine_signals(structure, at, data) VALUES (?, ?, ?) "
               "ON CONFLICT(structure) DO UPDATE SET at=excluded.at, data=excluded.data",
               (number, state["at"], encode(state)))


@lru_cache(maxsize=64)
def circuit_of(data: str) -> tuple[str, tuple[tuple, ...]]:
    """A machine's name and its parts, from its design's JSON."""
    style = json.loads(data).get("style", {})
    parts = tuple(((x, y, z), kind, facing, setting) for x, y, z, kind, facing, setting in style.get("circuit", []))
    return style.get("machine", ""), parts


def live_machines(db: sqlite3.Connection) -> list[tuple[int, str, str, tuple[tuple, ...]]]:
    """(id, its name, machine name, parts) of every machine Mimo finished, oldest first."""
    rows = db.execute("SELECT id, name, data FROM structures WHERE kind=? AND status='done' ORDER BY id",
                      (KIND,)).fetchall()
    return [(row[0], row[1], *circuit_of(row[2])) for row in rows]


Footsteps = tuple[list[float], list[Cell]]  # when Mimo reached each cell, in time order, and the cells


def cell_of(point: dict) -> Cell:
    return tuple(round(point.get(axis, 0.0)) for axis in "xyz")


def footsteps(life: dict) -> Footsteps:
    """Where Mimo's walks took it, in time order: the walk under way (all of it, the way ahead too) and
    the recent ones that keep their path, each finished one only as far as it went (a walk cut short never
    reached the rest). With none of them, where Mimo stands, all along."""
    walks = [life.get("action") or {}, *(life.get("recent_actions") or [])]
    points = sorted((point["at"], cell_of(point)) for walk in walks for point in walk.get("path") or []
                    if "at" in point and point["at"] <= walk.get("ended_at", math.inf))
    if not points:
        points = [(-math.inf, cell_of(life.get("position") or {}))]
    return [at for at, _ in points], [cell for _, cell in points]


def stepped_on(state: dict, cell: Cell, since: float, until: float, walked: Footsteps | None = None) -> bool:
    """Mimo was in `cell` at some time from `since` to `until`: it stood there at `since` (before its first
    known step, where that walk set off), or a walk reached it in between. A cell a walk reaches only after
    `until` does not count (fix round 1: a plate read the way ahead). `walked`: footsteps(state), when the
    caller has worked it out already."""
    times, cells = footsteps(state) if walked is None else walked
    cell = tuple(cell)
    first = bisect_right(times, since)
    return cells[max(0, first - 1)] == cell or cell in cells[first:bisect_right(times, until)]


def plates_walked(circuit: Circuit, walked: Footsteps, since: float, until: float) -> bool:
    """A walk reached one of the circuit's plates after `since`, up to `until`, so its plates may read on
    and off again in that time. (Stepping off one alone shows in how it reads at `until`.)"""
    plates = {part[0] for part in circuit.parts if part[1] == "plate"}
    times, cells = walked
    return any(cell in plates for cell in cells[bisect_right(times, since):bisect_right(times, until)])


def readings_at(circuit: Circuit, state: dict, grid: Grid, life: dict, at: float, scale: float,
                walked: Footsteps | None = None) -> dict[int, int]:
    """What each source gives out at `at`: a lever as its block shows, a button while its pulse lasts, a
    plate while Mimo is on it or was in the PLATE_SECONDS before `at` (`walked`: footsteps(life), when the
    caller has it), a sensor by day."""
    found = {}
    for index, (cell, kind, _, _) in enumerate(circuit.parts):
        if kind == "lever":
            found[index] = FULL if grid.material(*cell) == "lever_on" else 0
        elif kind == "button":
            if grid.material(*cell) == "button_on" and index not in state["press"]:
                state["press"][index] = BUTTON_STEPS
            found[index] = FULL if state["press"].get(index, 0) > 0 else 0
        elif kind == "plate":
            walked = footsteps(life) if walked is None else walked
            found[index] = FULL if stepped_on(life, cell, at - PLATE_SECONDS / scale, at, walked) else 0
        elif kind == "sensor":
            phase = clock_at(life.get("born_at", 0.0), at, scale)["phase"]
            found[index] = 0 if phase in NIGHT_PHASES else FULL
    return found


def missing_parts(grid: Grid, parts: tuple[tuple, ...]) -> list[int]:
    """Which of a machine's parts (their places in its design) have lost their block."""
    return [index for index, part in enumerate(parts) if grid.material(*part[0]) not in MATERIALS[part[1]]]


def present_parts(grid: Grid, parts: tuple[tuple, ...], missing: list[int] | None = None) -> tuple[tuple, ...]:
    """The parts whose block is there (`missing`: missing_parts, when the caller has it)."""
    gone = set(missing_parts(grid, parts) if missing is None else missing)
    return tuple(part for index, part in enumerate(parts) if index not in gone)


def draw(grid: Grid, circuit: Circuit, state: dict) -> None:
    """Put the blocks whose look changed: a wire, gate or lamp lit or not, a button back up."""
    for index, (cell, kind, _, _) in enumerate(circuit.parts):
        if kind in DRAWN:
            wanted = MATERIALS[kind][1 if drawn_on(circuit, state, index) else 0]
            if grid.material(*cell) != wanted:
                grid.put(*cell, wanted)
        elif kind == "button" and state["press"].get(index) == 0:
            state["press"].pop(index)
            if grid.material(*cell) == "button_on":
                grid.put(*cell, "button")


def corner_of(parts: tuple[tuple, ...]) -> tuple[int, int, int]:
    """The least x and z of a machine's parts (all of them, present or not), and their height."""
    return (min(part[0][0] for part in parts), parts[0][0][1], min(part[0][2] for part in parts))


def note_outputs(circuit: Circuit, state: dict, name: str = "", parts: tuple[tuple, ...] = ()) -> None:
    """What the viewer is told (machines.workshop_view): the doors held open (their cells), how many lamps
    are lit and (T3, READOUTS) what the machine reads out."""
    if name in READOUTS and parts:
        state["readout"] = READOUTS[name](circuit, state, corner_of(parts))
    state["doors"] = [list(part[0]) for index, part in enumerate(circuit.parts)
                      if part[1] == "door" and state["lit"].get(index)]
    state["lamps"] = sum(1 for index, part in enumerate(circuit.parts) if part[1] == "lamp" and state["lit"].get(index))


def run_machine(db: sqlite3.Connection, grid: Grid, life: dict, number: int, name: str, parts: tuple[tuple, ...],
                at: float, scale: float, budget: int, events: list) -> int:
    """Bring one machine's circuit up to `at` within `budget` cells; returns the cells worked out. Its state
    goes with which of its parts are there (fix round 1: not how many), so any change to them starts it
    again."""
    missing = missing_parts(grid, parts)
    present = present_parts(grid, parts, missing)
    circuit = compile_circuit(present)
    state = machine_state(db, number)
    if state is None or state.get("missing") != missing:
        state = fresh_state(circuit)
        start = STARTS.get(name)
        held, forced = start(life, at, scale, circuit, corner_of(parts)) if start is not None else ({}, {})
        settle(circuit, state, {**readings_at(circuit, state, grid, life, at, scale), **forced}, held)
        state["at"], state["missing"] = at, missing
        draw(grid, circuit, state)
        note_outputs(circuit, state, name, parts)
        save_state(db, number, state)
        return 0
    due = math.floor((at - state["at"]) * scale / STEP + 1e-9)
    if due <= 0:
        return 0
    if due > MAX_BEHIND:
        state["at"] = at - MAX_BEHIND * STEP / scale
        due = MAX_BEHIND
    cost, before = 0, encode(state)
    last = state["at"] + due * STEP / scale
    walked = footsteps(life) if any(part[1] == "plate" for part in circuit.parts) else None
    if (state["quiet"]
            and not (walked is not None and plates_walked(circuit, walked, state["at"] - PLATE_SECONDS / scale, last))
            and all(state["out"][source] == reading
                    for source, reading in readings_at(circuit, state, grid, life, last, scale, walked).items())):
        due, state["at"] = 0, last  # nothing is under way and nothing changed: it is simply later
    for _ in range(due):
        when = state["at"] + STEP / scale
        readings = readings_at(circuit, state, grid, life, when, scale, walked)
        bound = step_bound(circuit, state, readings)
        if cost + bound > budget and not (cost == 0 and budget >= MAX_CELLS):
            break
        spent, rang = step(circuit, state, readings)
        for press in [index for index, left in state["press"].items() if left > 0]:
            state["press"][press] -= 1
        events.extend((when, index) for index in rang)
        state["at"] = when
        cost += spent
    draw(grid, circuit, state)
    note_outputs(circuit, state, name, parts)
    if encode(state) != before:
        save_state(db, number, state)
    return cost


def run_signals(state: dict, context, at: float) -> None:
    """The tick's signal pass (after renewal): every machine Mimo finished, within MAX_CELLS, a different one
    first each tick (state["signal_turn"]), so a busy machine never leaves the others no budget for good.
    A crash is logged once and the tick goes on; a machine that crashes (fix round 1) is left for this
    tick, and the machines after it still run."""
    db = context.db
    if db is None or state.get("died_at") is not None:
        return
    try:
        scale = context.clock_at(at)["time_scale"]
        budget, machines = MAX_CELLS, live_machines(db)
    except Exception as error:
        log_once(logger, "signals", error)
        return
    turn = state.get("signal_turn", 0) % max(1, len(machines))
    state["signal_turn"] = turn + 1
    for number, title, name, parts in machines[turn:] + machines[:turn]:
        if budget <= 0:
            break
        rang: list = []
        try:
            budget -= run_machine(db, context.grid, state, number, name, parts, at, scale, budget, rang)
        except Exception as error:
            log_once(logger, f"signals {number}", error)
            continue
        context.events.extend((when, "bell", f"The bell on {title} rang.") for when, _ in rang[:1])
