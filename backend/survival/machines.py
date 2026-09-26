"""Machines (Making, T2): what Mimo builds with copper wire, and the first circuits.

A machine is a structure of kind "machine" (structures.start) whose design places its parts and carries
their circuit (style "circuit", run by backend.survival.signals once the machine is done). Each kind of
machine is a Machine in MACHINES: its layout (signals.parse's rows), the lesson it takes, where it goes
and what Mimo does once it is built (throws its levers, presses its first button: trying it out).
Where a machine goes (`design`):
- "yard": the nearest flat, untouched ground to the workshop (or home, without one) within YARD_REACH
  blocks where its whole layout and a walkway round it lie at one height (the walkway within a block
  of it); Mimo stands on the walkway, or in the layout's gaps, to build;
- "porch": the same, by home's door, within PORCH_REACH blocks;
- "door": the home's own door, with a pressure plate in front of it and one inside (the door itself is
  the output; it is the home's, never placed).

build_machine ("build a machine") works on the machine a making goal is up to (MACHINE_GOALS, in order,
the first not built whose lesson Mimo knows), or on one it started: by day, by home. A batch makes up to
PARTS_PER_BATCH parts Mimo can make now (making.craft_plan: at the workshop's own stations when there
is a finished workshop, walking in there first, else where it stands) and puts them in, in the layout's
order; when the last part is in, the machine is done ("Pip built a lamp on a lever.",
building.finish_if_built) and its circuit runs. Then one more batch tries it out: it throws its levers
and presses its first button. Work band: 55 plus a tenth of creativity. While a making goal is Mimo's
goal, the parts of its next machine are what making wants (making.NEEDS): copper ore for mine_ore
(and gather_stone, with a stone pickaxe, digs on to prospect for copper it has not seen yet:
work.prospecting) and sand for gather_materials.

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
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable

from backend.survival.blueprints import Blueprint, Planned, Survey
from backend.survival.building import site_center
from backend.survival.foraging import whole_walk
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.grid import Cell, Grid
from backend.survival.home import all_structures, home_structure
from backend.survival.making import NEEDS, craft_plan, place_steps
from backend.survival.pens import near_home
from backend.survival.purposes import Purpose, register
from backend.survival.signals import KIND, MATERIALS, parse
from backend.survival.situation import Situation
from backend.survival.steps import (
    PLACE_SECONDS, REACH, StepFailed, StepKind, as_cell, as_point, in_reach, register_step,
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
PLAIN = {kind: materials[0] for kind, materials in MATERIALS.items()}  # the item each part is placed as
structures.STANDS_IN.update({off: (off, on) for off, on in MATERIALS.values() if off != on})


@dataclass(frozen=True)
class Machine:
    name: str  # "lamp_lever"
    title: str  # "a lamp on a lever": the structure's name
    lesson: str  # the lesson it takes (backend.survival.tinker)
    layout: tuple[str, ...] = ()  # signals.parse's rows ("door" machines have none)
    where: str = "yard"  # "yard", "porch" or "door"
    try_out: bool = True  # once built, Mimo throws its levers and presses its first button


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

def layout_design(grid: Grid, machine: Machine, center: Cell, reach: int) -> Blueprint | None:
    """The machine on the nearest flat, untouched ground to `center`: its layout and a walkway round it
    at one height (the walkway within a block of it), or None."""
    width, depth = len(machine.layout[0]) // 2, len(machine.layout)
    survey = Survey(grid, center[1] - 1)
    cx, _, cz = center
    spots = sorted((math.hypot(dx, dz), dx, dz) for dx in range(-reach, reach + 1) for dz in range(-reach, reach + 1)
                   if math.hypot(dx, dz) <= reach)
    for _, dx, dz in spots:
        ox, oz = cx + dx - width // 2, cz + dz - depth // 2
        floor = survey.height(ox, oz)
        if floor is None or any(survey.height(ox + i, oz + j) != floor or not survey.room(ox + i, oz + j, floor + 2)
                                for i in range(width) for j in range(depth)):
            continue
        ring = [(ox + i, oz + j) for i in range(-1, width + 1) for j in range(-1, depth + 1)
                if i in (-1, width) or j in (-1, depth)]
        grounds = [survey.height(x, z) for x, z in ring]
        if any(ground is None or abs(ground - floor) > 1 for ground in grounds):
            continue
        parts = parse(machine.layout, (ox, floor + 1, oz))
        taken = {(x, z) for x, _, z, _, _, _ in parts}
        stands = [(x, ground + 1, z) for (x, z), ground in zip(ring, grounds)]
        stands += [(ox + i, floor + 1, oz + j) for j in range(depth) for i in range(width)
                   if (ox + i, oz + j) not in taken]
        return machine_blueprint(machine, (ox, floor + 1, oz), parts, tuple(stands))
    return None


def machine_blueprint(machine: Machine, anchor: Cell, parts: list[list], stands: tuple[Cell, ...]) -> Blueprint:
    cells = tuple(Planned((x, y, z), PART, PLAIN[kind]) for x, y, z, kind, _, _ in parts if kind != "door")
    return Blueprint(KIND, machine.title, anchor, cells, stands, style={"machine": machine.name, "circuit": parts})


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
    return machine_blueprint(machine, door, parts, tuple(blueprint.stands) + (front,))


def design(s: Situation, machine: Machine) -> Blueprint | None:
    """Where the machine goes (read once per Situation)."""
    def look() -> Blueprint | None:
        if machine.where == "door":
            return door_design(s, machine)
        home = home_structure(s)
        if machine.where == "porch" and home is not None and blueprint_of(home).front is not None:
            return layout_design(s.grid, machine, blueprint_of(home).front, PORCH_REACH)
        workshop = current_workshop(s)
        center = workshop_front(workshop) if workshop is not None and workshop["status"] == "done" else site_center(s)
        return layout_design(s.grid, machine, center, YARD_REACH)
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
    one (from its layout: no site is looked for here)."""
    found = started(s)
    if found is not None:
        blocks = [planned.block for planned in parts_left(s, blueprint_of(found))]
    else:
        machine = next_machine(s)
        if machine is None:
            return {}
        blocks = ["pressure_plate", "pressure_plate"] if machine.where == "door" else [
            PLAIN[kind] for _, _, _, kind, _, _ in parse(machine.layout) if kind != "door"]
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


def flips(s: Situation, blueprint: Blueprint) -> list[tuple[Cell, list[dict]]]:
    """Throw each lever that is not on, and press the first button."""
    jobs = []
    for x, y, z, kind, _, _ in blueprint.style.get("circuit", []):
        cell = (x, y, z)
        if kind == "lever" and s.grid.material(*cell) == "lever":
            jobs.append((cell, [{"kind": "flip", "target": [x, y, z]}]))
    buttons = [(x, y, z) for x, y, z, kind, _, _ in blueprint.style.get("circuit", []) if kind == "button"]
    if buttons:
        jobs.append((buttons[0], [{"kind": "flip", "target": list(buttons[0])}]))
    return jobs


def machine_batch(s: Situation, blueprint: Blueprint) -> list[dict]:
    """Make the next parts (at the workshop, walking in there first, when there is one) and put them in."""
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
    return found is not None and bool(makeable(s, found[1]))


def machine_facts(s: Situation) -> str:
    trying = untried(s)
    if trying is not None:
        return f"{trying[0]['name']} is built; time to try it out"
    machine, blueprint, _ = working(s)
    left = parts_left(s, blueprint)
    return f"building {machine.title}: {len(left)} parts to go, {len(makeable(s, blueprint))} it can make now"


def plan_machine(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.db is None or s.brain["batches"] >= MACHINE_BATCHES or not machine_valid(s):
        return []
    trying = untried(s)
    if trying is not None:
        found, blueprint = trying
        tried = ensure_brain(s.state).setdefault("machines_tried", [])
        tried.append(found["id"])
        return place_steps(s, blueprint.stands, flips(s, blueprint))
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
            "target": as_point(target), "block": grid.material(*target)}


def finish_flip(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = as_cell(step["target"])
    material = grid.material(*target)
    flipped = {"lever": "lever_on", "lever_on": "lever", "button": "button_on"}.get(material)
    if flipped is None:
        raise StepFailed("there is no lever or button there", "gone")
    grid.put(*target, flipped)
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
