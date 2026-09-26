"""Machines (Making, T2): what Mimo builds with copper wire, and the first circuits.

A machine is a structure of kind "machine" (structures.start) whose design places its parts and carries
their circuit (style "circuit", run by backend.survival.signals once the machine is done). Each kind of
machine is a Machine in MACHINES: its layout (signals.parse's rows), the lesson it takes, where it goes
and what Mimo does once it is built (throws its levers, presses its first button: trying it out).
Where a machine goes (`design`):
- "yard": the spot near the workshop (or home, without one) within its reach that costs the least to
  level (T3, below) plus its distance; Mimo stands on the walkway round it, or in the layout's gaps,
  to build;
- "porch": the same, by home's door, within PORCH_REACH blocks;
- "door": the home's own door, with a pressure plate in front of it and one inside (the door itself is
  the output; it is the home's, never placed).
T3: a yard need not be flat. Mimo levels it first: a column of it up to LEVEL blocks above the floor is
dug down and one up to LEVEL below is filled with dirt, and what grows on it (a tree's trunk up to
CLEAR_UP above the floor, anything else up to head height) comes out. Of the spots within reach, the one
with the least digging and filling, plus its distance, is chosen; every other spot is tried for the wide
machines (the counter and the computer may stand farther out). The walkway round it is where the ground
lies within a block of the floor.

build_machine ("build a machine") works on the machine a making goal is up to (MACHINE_GOALS, in order,
the first not built whose lesson Mimo knows), or on one it started: by day, by home. A batch makes up to
PARTS_PER_BATCH parts Mimo can make now (making.craft_plan: at the workshop's own stations when there
is a finished workshop, walking in there first, else where it stands) and puts them in, in the layout's
order; when the last part is in, the machine is done ("Pip built a lamp on a lever.",
building.finish_if_built) and its circuit runs. Then one more batch tries it out: it throws its levers
and presses its first button; it counts as tried once a flip is done (the final fix wave's M3), so a
try-out that a reflex or a failed walk cut short is tried again. Work band: 55 plus a tenth of
creativity. While a making goal is Mimo's goal, the parts of its next machine are what making wants
(making.NEEDS): copper ore for mine_ore (and gather_stone, with a stone pickaxe, digs on to prospect
for copper it knows none of within reach: work.prospecting) and sand for gather_materials. The
automatic door wants the plates its design really lays (the final fix wave's I4), and the computer is
named for Mimo ("Pip's computer": a Machine's title may name it, the final fix wave's M1).

The first circuits (T2), the goal "First circuits" (after the workshop): copper mined, the lesson that
copper carries a spark (backend.survival.tinker), then three machines: a lamp on a lever (its first
circuit), an automatic door (pressure plates by home's door, so it opens as Mimo comes), and a
night-light (a daylight sensor feeds an inverter, which drives a lamp: dark by day, lit at night). A lit
lamp gives light 15, like a lantern (backend.survival.light), so the night-light keeps home's door lit.

The flip step (registered here): throw a lever within reach (lever <-> lever_on) or press a button
(button_on, which the engine lets back up a second later).
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable

from backend.services.worldgen import TREE_LEAVES, TREE_LOGS
from backend.survival.blueprints import SCAN, Blueprint, Planned, open_cell
from backend.survival.building import site_center, structural_batch
from backend.survival.foraging import whole_walk
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.grid import Cell, Grid
from backend.survival.home import all_structures, home_structure
from backend.survival.memory import structures as structure_rows
from backend.survival.making import NEEDS, craft_plan, place_steps
from backend.survival.pens import near_home
from backend.survival.purposes import Purpose, register
from backend.survival.signals import KIND, MATERIALS, machine_state, parse
from backend.survival.situation import Situation
from backend.survival.steps import (
    PLACE_SECONDS, StepFailed, StepKind, as_cell, as_point, in_reach, register_step,
)
from backend.survival import structures
from backend.survival.structures import blueprint_of, clearing, start, todo
from backend.survival.triggers import ensure_brain
from backend.survival.workshop import current_workshop

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

YARD_REACH = 12
PORCH_REACH = 6
PARTS_PER_BATCH = 12
MACHINE_BATCHES = 6
PART = "part"
LEVEL = 2  # T3: a yard column this much above or below the floor is dug down or filled up first
CLEAR = "clear"  # T3: a cell of the yard Mimo digs out before the parts go in
CLEAR_UP = 5  # T3: a trunk on the yard is taken down this far above the floor (as high as Mimo reaches)
LOGS = frozenset(TREE_LOGS.values())
GROWTH = LOGS | frozenset(TREE_LEAVES.values()) | {"cactus", "pumpkin", "melon"}  # what a yard's clearing takes
PLAIN = {kind: materials[0] for kind, materials in MATERIALS.items()}  # the item each part is placed as
structures.STANDS_IN.update({off: (off, on) for off, on in MATERIALS.values() if off != on})


@dataclass(frozen=True)
class Machine:
    name: str  # "lamp_lever"
    title: str  # "a lamp on a lever": the structure's name ("{name}'s computer": formatted with Mimo's name)
    lesson: str  # the lesson it takes (backend.survival.tinker)
    layout: tuple[str, ...] = ()  # signals.parse's rows ("door" machines have none)
    where: str = "yard"  # "yard", "porch" or "door"
    try_out: bool = True  # once built, Mimo throws its levers and presses its first button
    reach: int = YARD_REACH  # T3: blocks from the yard's middle a yard machine may stand (the big ones farther)


MACHINES: dict[str, Machine] = {}
# A making goal -> the machines it builds, in order (the first circuits here; T3's thinking machine).
MACHINE_GOALS: dict[str, tuple[str, ...]] = {}


def register_machine(machine: Machine) -> Machine:
    MACHINES[machine.name] = machine
    return machine


register_machine(Machine("lamp_lever", "a lamp on a lever", "copper_spark", ("L w w * ",)))
register_machine(Machine("auto_door", "an automatic door", "copper_spark", where="door", try_out=False))
register_machine(Machine("night_light", "a night-light", "copper_spark", ("S n>* ",), where="porch",
                         try_out=False))


# Designs -----------------------------------------------------------------------------------------

def yard_column(grid: Grid, x: int, z: int, reference: int) -> tuple[int, list[Cell]] | None:
    """T3: a column's natural ground under what grows on it, and the cells of that growth (a tree's logs and
    leaves, a cactus, a pumpkin or a melon), looked for from SCAN above `reference` down; None where the
    column holds water, or anything Mimo placed, dug or claimed, or (fix round 1, as blueprints.look_at's
    firm check does) where the ground does not rest on something solid."""
    growth: list[Cell] = []
    for y in range(reference + SCAN, reference - SCAN - 1, -1):
        cell = (x, y, z)
        material = grid.material(*cell)
        if material == "water" or grid.claimed(cell) or material != grid.natural_material(*cell):
            return None
        if material in GROWTH:
            growth.append(cell)
        elif not open_cell(material):
            under = grid.material(x, y - 1, z)
            if under == "water" or not grid.solid((x, y - 1, z)):
                return None
            return y, growth
    return None


def levelled(columns: dict[tuple[int, int], tuple[int, list[Cell]]]) -> int | None:
    """T3: the floor height that takes the least digging and filling (the higher of two alike), or None
    when the columns lie more than 2 * LEVEL apart."""
    grounds = [ground for ground, _ in columns.values()]
    low, high = min(grounds), max(grounds)
    if high - low > 2 * LEVEL:
        return None
    return min(range(high - LEVEL, low + LEVEL + 1), key=lambda floor: (sum(abs(g - floor) for g in grounds), -floor))


def ring_of(ox: int, oz: int, width: int, depth: int) -> list[tuple[int, int]]:
    """The columns round a layout: its walkway, clear of water and of anything Mimo built."""
    return [(ox + i, oz + j) for i in range(-1, width + 1) for j in range(-1, depth + 1)
            if i in (-1, width) or j in (-1, depth)]


def layout_design(grid: Grid, machine: Machine, center: Cell, reach: int, owner: str = "Mimo") -> Blueprint | None:
    """The machine where its layout, levelled, costs the least digging and filling plus distance from
    `center` (T3): its parts on the floor, the cells to clear (dug down, then what grows there) and the
    floor blocks to fill; a walkway round it clear of water and of what Mimo built, and stands on it where
    its ground is within a block of the floor. Every other spot is tried for the wide machines. None when
    nothing fits."""
    width, depth = len(machine.layout[0]) // 2, len(machine.layout)
    cx, cy, cz = center
    columns: dict[tuple[int, int], tuple[int, list[Cell]] | None] = {}

    def column(x: int, z: int) -> tuple[int, list[Cell]] | None:
        if (x, z) not in columns:
            columns[(x, z)] = yard_column(grid, x, z, cy - 1)
        return columns[(x, z)]

    stride = 2 if reach > 12 else 1
    spots = sorted((math.hypot(dx, dz), dx, dz) for dx in range(-reach, reach + 1, stride)
                   for dz in range(-reach, reach + 1, stride) if math.hypot(dx, dz) <= reach)
    best = None
    for distance, dx, dz in spots:
        if best is not None and distance >= best[0]:
            break
        ox, oz = cx + dx - width // 2, cz + dz - depth // 2
        found = {(ox + i, oz + j): column(ox + i, oz + j) for i in range(width) for j in range(depth)}
        if None in found.values() or any(column(x, z) is None for x, z in ring_of(ox, oz, width, depth)):
            continue
        floor = levelled(found)
        if floor is None:
            continue
        clear: list[Cell] = []
        fill: list[Cell] = []
        for (x, z), (ground, growth) in found.items():
            clear += [(x, y, z) for y in range(ground, floor, -1)]
            fill += [(x, y, z) for y in range(ground + 1, floor + 1)]
            clear += [cell for cell in growth if cell[1] <= floor + 2
                      or (cell[1] <= floor + CLEAR_UP and grid.material(*cell) in LOGS)]
        cost = len(clear) + len(fill) + distance
        if best is None or cost < best[0]:
            best = (cost, ox, oz, floor, clear, fill)
    if best is None:
        return None
    _, ox, oz, floor, clear, fill = best
    parts = parse(machine.layout, (ox, floor + 1, oz))
    taken = {(x, z) for x, _, z, _, _, _ in parts}
    stands = []
    for x, z in ring_of(ox, oz, width, depth):
        found = column(x, z)
        if found is not None and abs(found[0] - floor) <= 1 and not any(cell[1] <= found[0] + 2 for cell in found[1]):
            stands.append((x, found[0] + 1, z))
    stands += [(ox + i, floor + 1, oz + j) for j in range(depth) for i in range(width) if (ox + i, oz + j) not in taken]
    clear.sort(key=lambda cell: (-cell[1], cell))
    return machine_blueprint(machine, (ox, floor + 1, oz), parts, tuple(stands), fill, clear, owner)


def title_of(machine: Machine, owner: str) -> str:
    """The machine's name: its title formatted with Mimo's name (the final fix wave's M1: "Pip's computer")."""
    return machine.title.format(name=owner)


def machine_blueprint(machine: Machine, anchor: Cell, parts: list[list], stands: tuple[Cell, ...],
                      floors: list[Cell] = (), clear: list[Cell] = (), owner: str = "Mimo") -> Blueprint:
    """The design: the yard's cells to clear and its floor blocks (T3), then the parts; named `title_of`."""
    cells = tuple(Planned(cell, CLEAR, "air") for cell in clear)
    cells += tuple(Planned(cell, "floor", "dirt") for cell in floors)
    cells += tuple(Planned((x, y, z), PART, PLAIN[kind]) for x, y, z, kind, _, _ in parts if kind != "door")
    return Blueprint(KIND, title_of(machine, owner), anchor, cells, stands,
                     style={"machine": machine.name, "circuit": parts})


def door_design(s: Situation, machine: Machine) -> Blueprint | None:
    """Pressure plates in front of home's door (when that cell is level with the door) and inside it."""
    home = home_structure(s)
    if home is None or home["status"] != "done":
        return None
    blueprint = blueprint_of(home)
    door = next((planned.cell for planned in blueprint.parts("door") if planned.block == "door"), None)
    front = blueprint.front
    if door is None or front is None:
        return None
    inside = (2 * door[0] - front[0], door[1], 2 * door[2] - front[2])
    plates = [cell for cell in (front, inside) if cell[1] == door[1]]
    parts = [[*cell, "plate", "", 0] for cell in plates] + [[*door, "door", "", 0]]
    return machine_blueprint(machine, door, parts, tuple(blueprint.stands) + (front,), owner=s.state["name"])


def design(s: Situation, machine: Machine) -> Blueprint | None:
    """Where the machine goes (read once per Situation)."""
    def look() -> Blueprint | None:
        if machine.where == "door":
            return door_design(s, machine)
        home = home_structure(s)
        if machine.where == "porch" and home is not None and blueprint_of(home).front is not None:
            return layout_design(s.grid, machine, blueprint_of(home).front, PORCH_REACH, s.state["name"])
        workshop = current_workshop(s)
        center = workshop_front(workshop) if workshop is not None and workshop["status"] == "done" else site_center(s)
        return layout_design(s.grid, machine, center, machine.reach, s.state["name"])
    return s.sensed(f"machine design {machine.name}", look)


def workshop_front(workshop: dict) -> Cell:
    blueprint = blueprint_of(workshop)
    return blueprint.front or blueprint.anchor


# Which machine -----------------------------------------------------------------------------------

def machines_built(s: Situation) -> dict[str, dict]:
    """Every machine Mimo started, by its machine name (the newest of each)."""
    return {found["data"].get("style", {}).get("machine", ""): found for found in all_structures(s)
            if found["kind"] == KIND}


def built(s: Situation, name: str) -> bool:
    found = machines_built(s).get(name)
    return found is not None and found["status"] == "done"


def started(s: Situation) -> dict | None:
    """A machine Mimo started and has not finished."""
    return next((found for found in machines_built(s).values() if found["status"] == "building"), None)


def next_machine(s: Situation) -> Machine | None:
    """The machine a making goal that is Mimo's goal is up to: the first of its list not built, when Mimo
    knows the lesson it takes; None otherwise."""
    goal = active(s)
    for name in MACHINE_GOALS.get(goal.name if goal is not None else "", ()):
        if not built(s, name):
            return MACHINES[name] if MACHINES[name].lesson in s.lessons else None
    return None


def untried(s: Situation) -> tuple[dict, Blueprint] | None:
    """A machine built but not tried out yet (its levers thrown, its first button pressed), when it has a
    lever or a button to try."""
    tried = set(ensure_brain(s.state).get("machines_tried", []))
    for name, found in machines_built(s).items():
        machine = MACHINES.get(name)
        if (machine is not None and machine.try_out and found["status"] == "done" and found["id"] not in tried
                and flips(s, blueprint_of(found))):
            return found, blueprint_of(found)
    return None


def working(s: Situation) -> tuple[Machine, Blueprint, dict | None] | None:
    """(machine, design, structure or None) for what build_machine works on now."""
    def look():
        found = started(s)
        if found is not None:
            machine = MACHINES.get(found["data"].get("style", {}).get("machine", ""))
            return None if machine is None else (machine, blueprint_of(found), found)
        machine = next_machine(s)
        blueprint = design(s, machine) if machine is not None else None
        return None if blueprint is None else (machine, blueprint, None)
    return s.sensed("machine working", look)


def parts_left(s: Situation, blueprint: Blueprint) -> list[Planned]:
    return todo(s.grid, blueprint, (PART,))


def machine_needs(s: Situation) -> dict[str, int]:
    """making.NEEDS: the parts still missing from the machine Mimo started, or all the parts of the next
    one (from its layout: no site is looked for here; for the automatic door, the plates its design at
    home's door really lays: the final fix wave's I4, one on uneven ground)."""
    found = started(s)
    if found is not None:
        blocks = [planned.block for planned in parts_left(s, blueprint_of(found))]
    else:
        machine = next_machine(s)
        if machine is None:
            return {}
        if machine.where == "door":
            blueprint = door_design(s, machine)
            blocks = [planned.block for planned in blueprint.parts(PART)] if blueprint is not None else []
        else:
            blocks = [PLAIN[kind] for _, _, _, kind, _, _ in parse(machine.layout) if kind != "door"]
    wanted: dict[str, int] = {}
    for block in blocks:
        wanted[block] = wanted.get(block, 0) + 1
    return wanted


NEEDS.append(machine_needs)


# build_machine -----------------------------------------------------------------------------------

def makeable(s: Situation, blueprint: Blueprint) -> list[Planned]:
    """The next parts, up to PARTS_PER_BATCH, that Mimo can make now (at the workshop when it has one)."""
    where = at_workshop(s)
    chosen: list[Planned] = []
    wanted: dict[str, int] = {}
    for planned in parts_left(s, blueprint):
        trial = {**wanted, planned.block: wanted.get(planned.block, 0) + 1}
        if craft_plan(where, trial) is not None:
            chosen.append(planned)
            wanted = trial
        if len(chosen) >= PARTS_PER_BATCH:
            break
    return chosen


def at_workshop(s: Situation) -> Situation:
    """`s` as Mimo will be inside its finished workshop, its stations within reach (s itself without one)."""
    workshop = current_workshop(s)
    if workshop is None or workshop["status"] != "done":
        return s
    anchor = blueprint_of(workshop).anchor
    return replace(s, state={**s.state, "position": dict(zip("xyz", map(float, anchor)))}, memo={})


def flips(s: Situation, blueprint: Blueprint, number: int | None = None) -> list[tuple[Cell, list[dict]]]:
    """Throw each lever that is not on, and press the first button (each flip naming the machine's
    structure `number`, when given, so finish_flip marks it tried)."""
    mark = {} if number is None else {"machine": number}
    jobs = []
    for x, y, z, kind, _, _ in blueprint.style.get("circuit", []):
        cell = (x, y, z)
        if kind == "lever" and s.grid.material(*cell) == "lever":
            jobs.append((cell, [{"kind": "flip", "target": [x, y, z], **mark}]))
    buttons = [(x, y, z) for x, y, z, kind, _, _ in blueprint.style.get("circuit", []) if kind == "button"]
    if buttons:
        jobs.append((buttons[0], [{"kind": "flip", "target": list(buttons[0]), **mark}]))
    return jobs


def yard_left(s: Situation, blueprint: Blueprint) -> list[Planned]:
    """T3: the yard's cells still to clear, the highest first."""
    return [planned for planned in blueprint.parts(CLEAR) if not open_cell(s.grid.material(*planned.cell))]


def yard_stands(s: Situation, blueprint: Blueprint) -> list[Cell]:
    """T3: where Mimo can stand while it levels the yard: the design's stands, and every cell of the layout,
    that is open with ground under it now."""
    cells = list(blueprint.stands) + [(x, y, z) for x, y, z, kind, _, _ in blueprint.style.get("circuit", [])
                                      if kind != "door" and (x, y, z) not in blueprint.stands]
    return [cell for cell in cells if open_cell(s.grid.material(*cell)) and s.grid.solid((cell[0], cell[1] - 1, cell[2]))]


def machine_batch(s: Situation, blueprint: Blueprint) -> list[dict]:
    """The yard cleared (T3: what is too high dug down, what grows there taken out) and its floor blocks
    put in (building.structural_batch), then make the next parts (at the workshop, walking in there first,
    when there is one) and put them in."""
    digging = yard_left(s, blueprint)
    if digging:
        jobs = [(planned.cell, [{"kind": "mine", "target": list(planned.cell)}])
                for planned in digging[:PARTS_PER_BATCH]]
        return place_steps(s, yard_stands(s, blueprint), jobs)
    if todo(s.grid, blueprint):
        if not blueprint.stands:
            return []
        stand = s.here if s.here in blueprint.stands else blueprint.stands[0]
        work = structural_batch(s, blueprint, stand)
        return ([] if stand == s.here else [whole_walk(stand)]) + work if work else []
    chosen = makeable(s, blueprint)
    if not chosen:
        return []
    where = at_workshop(s)
    wanted: dict[str, int] = {}
    for planned in chosen:
        wanted[planned.block] = wanted.get(planned.block, 0) + 1
    crafting = craft_plan(where, wanted) or []
    walk = [whole_walk(where.here)] if crafting and where is not s and where.here != s.here else []
    jobs = [(planned.cell, [*clearing(s.grid, planned.cell),
                            {"kind": "place", "target": list(planned.cell), "block": planned.block}])
            for planned in chosen]
    return walk + crafting + place_steps(s, blueprint.stands, jobs, at=where.here if walk else None)


def machine_valid(s: Situation) -> bool:
    if s.night or not near_home(s):
        return False
    if untried(s) is not None:
        return True
    found = working(s)
    return found is not None and bool(machine_batch(s, found[1]))


def machine_facts(s: Situation) -> str:
    trying = untried(s)
    if trying is not None:
        return f"{trying[0]['name']} is built; time to try it out"
    machine, blueprint, _ = working(s)
    left = parts_left(s, blueprint)
    return (f"building {title_of(machine, s.state['name'])}: {len(left)} parts to go, "
            f"{len(makeable(s, blueprint))} it can make now")


def plan_machine(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.db is None or s.brain["batches"] >= MACHINE_BATCHES or not machine_valid(s):
        return []
    trying = untried(s)
    if trying is not None:
        found, blueprint = trying
        return place_steps(s, blueprint.stands, flips(s, blueprint, found["id"]))
    machine, blueprint, found = working(s)
    if found is None:
        start(s.db, s.grid, blueprint, s.at)
    return machine_batch(s, blueprint)


register(Purpose(
    "build_machine", "build a machine",
    "Build a machine of copper wire, levers, gates and lamps by the workshop, part by part, and try it out.",
    valid=machine_valid, facts=machine_facts, score=lambda s: 55.0 + s.trait("creativity") / 10, plan=plan_machine,
    thoughts=("A spark runs down the copper. Let's build something!", "One more part and it should work.")))


# The flip step -----------------------------------------------------------------------------------

def start_flip(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = as_cell(spec["target"])
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    if grid.material(*target) not in ("lever", "lever_on", "button"):
        raise StepFailed("there is no lever or button there", "gone")
    return {"kind": "flip", "started_at": at, "ends_at": round(at + PLACE_SECONDS / scale, 3),
            "target": as_point(target), "block": grid.material(*target),
            **({"machine": spec["machine"]} if spec.get("machine") is not None else {})}


def finish_flip(step: dict, state: dict, grid: Grid, at: float) -> None:
    """Throw the lever or press the button. A machine's try-out flip marks it tried only now (the final fix
    wave's M3: marked when planned, a walk or flip cut short left it untried for good)."""
    target = as_cell(step["target"])
    material = grid.material(*target)
    flipped = {"lever": "lever_on", "lever_on": "lever", "button": "button_on"}.get(material)
    if flipped is None:
        raise StepFailed("there is no lever or button there", "gone")
    grid.put(*target, flipped)
    if step.get("machine") is not None:
        tried = ensure_brain(state).setdefault("machines_tried", [])
        if step["machine"] not in tried:
            tried.append(step["machine"])
    return None


register_step(StepKind("flip", start_flip, finish_flip, "tinkering", working=True, cell_field="target"))


# The first circuits ------------------------------------------------------------------------------

FIRST = "first_circuits"
MACHINE_GOALS[FIRST] = ("lamp_lever", "auto_door", "night_light")
COPPER_WANTED = 3


def whole(done: bool) -> float:
    return 1.0 if done else 0.0


def copper_mined(s: Situation) -> float:
    if built(s, "lamp_lever"):
        return 1.0
    return min(1.0, (s.count("copper_ore", "copper_ingot") + s.count("copper_wire") / 12) / COPPER_WANTED)


def knows(lesson: str) -> Callable[[Situation], float]:
    return lambda s: whole(lesson in s.lessons)


def machine_share(name: str) -> Callable[[Situation], float]:
    def share(s: Situation) -> float:
        found = machines_built(s).get(name)
        if found is None:
            return 0.0
        if found["status"] == "done":
            return 1.0
        blueprint = blueprint_of(found)
        total = len(blueprint.parts(PART))
        return 1.0 - len(parts_left(s, blueprint)) / total if total else 1.0
    return share


register_goal(Goal(
    FIRST, "First circuits",
    "Copper carries a spark: with a lever, wire and a lamp Mimo can make light, open doors and more.",
    (Milestone("Mine copper", copper_mined, ("mine_ore", "gather_stone")),
     Milestone("Learn that copper carries a spark", knows("copper_spark"), ("tinker", "mine_ore")),
     Milestone("Build a lamp on a lever", machine_share("lamp_lever"), ("build_machine", "mine_ore"), ("lamp",)),
     Milestone("Build an automatic door", machine_share("auto_door"), ("build_machine",), ("pressure_plate",)),
     Milestone("Build a night-light", machine_share("night_light"), ("build_machine", "gather_materials", "mine_ore"),
               ("daylight_sensor",))),
    score=lambda s: 40.0 + s.trait("curiosity") / 10 + s.trait("creativity") / 10,
    thought="Copper, a lever, a lamp... I want to make a spark.", after=("workshop",)))


# What the viewer is told -------------------------------------------------------------------------

def workshop_view(db: sqlite3.Connection) -> dict:
    """What Mimo made, for /api/mimo (read only): its workshop ({name, status} or None), its machines,
    oldest first ({id, name, machine, status, x, y, z, lamps lit, and the count a counter or computer
    shows: {value, bits, shown} or None}) and the doors its machines hold open ([x, y, z]). A world from
    before M5 or Making (an archive) made nothing."""
    try:
        found = structure_rows(db, ("workshop", KIND))
    except sqlite3.OperationalError:
        return {"workshop": None, "machines": [], "doors_open": []}
    workshops = [row for row in found if row["kind"] == "workshop"]
    machines, doors = [], []
    for row in found:
        if row["kind"] != KIND:
            continue
        state = machine_state(db, row["id"]) if row["status"] == "done" else None
        machines.append({"id": row["id"], "name": row["name"], "machine": row["data"].get("style", {}).get("machine"),
                         "status": row["status"], "x": row["x"], "y": row["y"], "z": row["z"],
                         "lamps": (state or {}).get("lamps", 0), "readout": (state or {}).get("readout")})
        doors += (state or {}).get("doors", [])
    workshop = {"name": workshops[-1]["name"], "status": workshops[-1]["status"]} if workshops else None
    return {"workshop": workshop, "machines": machines, "doors_open": doors}
