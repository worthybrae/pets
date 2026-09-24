"""What each timed step needs, how long it takes and what it changes.

A queued step is a small dict, for example {"kind": "mine", "target": [x, y, z]}. `start_step`
checks it against the world and returns the running step with its start and end times.
`finish_step` applies it at its end time. Both raise StepFailed (a ValueError) with a short
reason; crafting errors from backend.services.crafting are ValueErrors too. `validate_step` runs
first inside `start_step`, so a malformed spec (a stray planner bug, a corrupted queue) fails
with a clean StepFailed instead of a TypeError from as_cell or a dict lookup further in.

Every kind of step is a StepKind in the STEP_KINDS registry: how it starts and finishes, the
pet's status while it runs, whether it counts as work and whether a reflex may cut it short. The
engine (backend.survival.actions) asks the registry, so a new kind only has to register. M4's
field work (pick, harvest, till, plant, fish, cook) lives in backend.survival.fieldwork, M5's
housework (store, take, drop) in backend.survival.housework and L1's attack in
backend.survival.creatures.combat. Mining leaves or tall grass may drop
more (nature.CHANCE_DROPS): saplings, apples, seeds. Sleep on a bed is sleep in a bed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from backend.services.blocks import hardness, is_replaceable, mining_tool
from backend.services.crafting import BLOCKS, SMELTING, add_item, can_harvest, craft, smelt, take_items
from backend.survival import nature
from backend.survival.carrying import fits
from backend.survival.grid import Cell, Grid
from backend.survival.pathing import route, timed_path

REACH = 4.0
STATION_REACH = 6.0
WORKSTATIONS = ("crafting_table", "furnace", "campfire")
PLACE_SECONDS = 0.3
EAT_SECONDS = 1.6
CRAFT_SECONDS = 1.0
SMELT_SECONDS = 5.0
PICKAXE_SPEED = {"wooden_pickaxe": 2.0, "stone_pickaxe": 4.0, "iron_pickaxe": 6.0}
# Axes are crafting recipes (M5). Any axe doubles the speed on wood.
AXES = ("wooden_axe", "stone_axe", "iron_axe")
AXE_SPEED = 2.0
# Hunger each food restores (spec section 7). A red mushroom fills like a brown one but is poisonous.
FOOD = {"berries": 8.0, "brown_mushroom": 6.0, "red_mushroom": 6.0, "carrot": 10.0, "bread": 25.0, "raw_fish": 8.0,
        "cooked_fish": 30.0, "apple": 15.0,
        # L1: meat from hunting. Raw it fills little; cooked at a fire it fills far more.
        "raw_beef": 8.0, "raw_mutton": 8.0, "raw_chicken": 6.0, "raw_rabbit": 6.0,
        "cooked_beef": 35.0, "cooked_mutton": 30.0, "cooked_chicken": 25.0, "cooked_rabbit": 25.0}
# Health a food changes when eaten: a red mushroom is poisonous. Poison never takes the last point
# of health (it is not a cause of death).
FOOD_HEALTH = {"red_mushroom": -10.0}
# Food that only sometimes makes Mimo sick: (chance, health). Raw chicken is a gamble, not poison, so
# Mimo never learns to shun it (backend.survival.learning); cooking makes it safe.
FOOD_RISK = {"raw_chicken": (0.25, -4.0)}
RISK_CHANNEL = 39
# A far walk re-plans segment by segment; after this many extra segments it gives up.
MAX_SEGMENTS = 12


FAILURE_CODES = ("no_path", "out_of_reach", "gone", "missing_item", "blocked", "bad_step")


class StepFailed(ValueError):
    """A step cannot start or finish. The message says why; `code` (one of FAILURE_CODES) sorts
    it for the brain: no way there, out of reach, the block is gone, something is missing, the
    cell is blocked, or the step itself is malformed."""

    def __init__(self, message: str, code: str = "bad_step"):
        super().__init__(message)
        self.code = code


def failure_code(error: Exception) -> str:
    """The failure code of anything start_step or finish_step raised. Crafting and smelting raise
    plain ValueErrors: missing materials or a missing station mean something is missing."""
    if isinstance(error, StepFailed):
        return error.code
    if str(error).startswith(("Missing materials", "A placed")):
        return "missing_item"
    return "bad_step"


def _whole(value) -> int:
    """`value` as an int, only when it already is one: 3 or 3.0, never 3.5, NaN, inf or a bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"not a whole number: {value!r}")
    if value != int(value):
        raise ValueError(f"not a whole number: {value!r}")
    return int(value)


def as_cell(value) -> Cell:
    """A cell from [x, y, z] (queued steps) or {"x", "y", "z"} (running steps, paths and positions).

    One rule for both shapes: exactly three integer-valued finite numbers, nothing rounded or
    truncated. A caller with a genuinely fractional value (the pet's position mid-fall or
    mid-swim never has one today; see actions.py) needs its own floor/round helper instead of a
    looser as_cell.
    """
    try:
        if isinstance(value, dict):
            x, y, z = value["x"], value["y"], value["z"]
        else:
            x, y, z = value
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"not a cell: {value!r}")
    return _whole(x), _whole(y), _whole(z)


def as_point(cell) -> dict:
    x, y, z = as_cell(cell)
    return {"x": x, "y": y, "z": z}


def position_of(point: dict) -> dict:
    """A state position (floats, as M1 stores it) from a path entry or point."""
    return {"x": float(point["x"]), "y": float(point["y"]), "z": float(point["z"])}


def label(name: str) -> str:
    return name.replace("_", " ")


def tool_speed(material: str, inventory: dict[str, int]) -> float:
    """How much faster than a bare hand Mimo mines `material` with what it carries."""
    owned = {item for item, amount in inventory.items() if amount > 0}
    tool = mining_tool(material)
    if tool == "pickaxe":
        return max((PICKAXE_SPEED[item] for item in owned if item in PICKAXE_SPEED), default=1.0)
    if tool == "axe" and owned.intersection(AXES):
        return AXE_SPEED
    return 1.0


def mine_seconds(material: str, inventory: dict[str, int]) -> float | None:
    """Hardness divided by tool speed, or None for blocks that cannot be mined."""
    seconds = hardness(material)
    return None if seconds is None else seconds / tool_speed(material, inventory)


def seed_of(state: dict) -> str:
    """The world seed chance is rolled from (tests without one roll from "0")."""
    return state.get("world_seed", "0")


def in_reach(here: Cell, target: Cell) -> bool:
    return math.dist(here, target) <= REACH


def stations_near(grid: Grid, here: Cell) -> set[str]:
    return grid.placed_near(here[0], here[2], STATION_REACH, WORKSTATIONS)


@dataclass(frozen=True)
class StepKind:
    """One kind of step in the registry that every planned step runs through.

    `start(spec, state, grid, at, scale)` checks a queued spec against the world and returns the
    running step from `at` to its end time (`ends_at`, None when it has no fixed end).
    `finish(step, state, grid, at)` applies it at its end and returns an event (kind, text) worth
    logging, or None. Both raise StepFailed. `status` is the pet's status while it runs, `working`
    makes it count as work for the vitals, and `interruptible` lets a takeover (a reflex) cut it
    short; the other kinds last a few seconds at most and finish first. validate_step checks that
    the spec's `cell_field` is a cell and its `string_field` a string before `start` sees it.
    """

    name: str
    start: Callable[[dict, dict, Grid, float, float], dict]
    finish: Callable[[dict, dict, Grid, float], "tuple[str, str] | None"]
    status: str
    working: bool = False
    interruptible: bool = False
    cell_field: str | None = None
    string_field: str | None = None


STEP_KINDS: dict[str, StepKind] = {}


def register_step(kind: StepKind) -> StepKind:
    """Add a step kind, or replace the one with the same name."""
    STEP_KINDS[kind.name] = kind
    return kind


def step_kind(name) -> StepKind | None:
    """The registered kind called `name`, or None (also when `name` is not a string)."""
    return STEP_KINDS.get(name) if isinstance(name, str) else None


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_step(spec: dict) -> None:
    """Check a queued step's shape before it touches the world or an inventory dict.

    A field that is present but the wrong shape (a target that isn't a cell, a block that isn't
    a string, a non-finite reach or wait) raises StepFailed here, short and clear, instead of a
    TypeError from as_cell or a dict lookup deeper in start_step. A field that is simply missing
    is left to the checks below, which already raise their own StepFailed for it.
    """
    kind = step_kind(spec.get("kind"))
    if kind is None:
        raise StepFailed(f"unknown step {spec.get('kind')!r}")
    if kind.cell_field and kind.cell_field in spec:
        try:
            as_cell(spec[kind.cell_field])
        except ValueError:
            raise StepFailed(f"bad step: {kind.cell_field}")
    if kind.string_field and kind.string_field in spec and not isinstance(spec[kind.string_field], str):
        raise StepFailed(f"bad step: {kind.string_field}")
    if kind.name == "walk" and "reach" in spec and not (_finite_number(spec["reach"]) and spec["reach"] >= 0):
        raise StepFailed("bad step: reach")
    if kind.name == "wait" and "seconds" in spec and not _finite_number(spec["seconds"]):
        raise StepFailed("bad step: seconds")


def start_step(spec: dict, state: dict, grid: Grid, at: float, scale: float = 1.0) -> dict:
    """Check a queued step against the world and return it running, from `at` to its end time.

    `scale` (MIMO_ACTION_SCALE, 1 outside manual tests) divides the duration of every step with a
    fixed length except waits, which time things against the clock. Sleep has no fixed end.
    """
    validate_step(spec)
    return STEP_KINDS[spec["kind"]].start(spec, state, grid, at, scale)


def finish_step(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str] | None:
    """Apply a running step at its end. Returns an event (kind, text) worth logging, if any."""
    kind = step_kind(step["kind"])
    return None if kind is None else kind.finish(step, state, grid, at)


def nothing_happens(step: dict, state: dict, grid: Grid, at: float) -> None:
    return None


def start_walk(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    here, target = as_cell(state["position"]), as_cell(spec["target"])
    reach = float(spec.get("reach", 0.0))
    segments = int(spec.get("segments", 0))
    if segments > MAX_SEGMENTS:
        raise StepFailed("no way there", "no_path")
    cells, reached = route(grid, here, target, reach)
    # A walk marked `whole` goes all the way or not at all: part of the way can end in a pit.
    if not reached and (not cells or spec.get("whole")):
        raise StepFailed("no way there", "no_path")
    path = timed_path(grid, here, cells, at, scale)
    return {"kind": "walk", "started_at": at, "ends_at": path[-1]["at"], "path": path,
            "target": as_point(target), "reach": reach, "reached": reached, "segments": segments,
            **({"whole": True} if spec.get("whole") else {})}


def finish_walk(step: dict, state: dict, grid: Grid, at: float) -> None:
    state["position"] = position_of(step["path"][-1])
    return None


def start_mine(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target, inventory = as_cell(spec["target"]), state["inventory"]
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    material = grid.material(*target)
    seconds = mine_seconds(material, inventory)
    if seconds is None:
        raise StepFailed(f"{label(material)} cannot be mined", "blocked")
    if not can_harvest(material, inventory):
        raise StepFailed(f"a stronger pickaxe is needed for {label(material)}", "missing_item")
    return {"kind": "mine", "started_at": at, "ends_at": round(at + seconds / scale, 3),
            "target": as_point(target), "block": material}


def finish_mine(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = as_cell(step["target"])
    if grid.material(*target) != step["block"]:
        raise StepFailed(f"the {label(step['block'])} is gone", "gone")
    grid.put(*target, "air")
    # A chest that is mined takes its contents with it.
    if step["block"] == "chest":
        x, y, z = target
        state.get("chests", {}).pop(f"{x},{y},{z}", None)
    drop = BLOCKS.get(step["block"], {}).get("drop")
    if drop:
        add_item(state["inventory"], drop)
    for item in nature.chance_drops(seed_of(state), target, step["block"]):
        add_item(state["inventory"], item)
    return None


def start_place(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    here, target, block = as_cell(state["position"]), as_cell(spec["target"]), spec["block"]
    if state["inventory"].get(block, 0) < 1:
        raise StepFailed(f"no {label(block)} to place", "missing_item")
    if block not in BLOCKS:
        raise StepFailed(f"{label(block)} is not a block")
    if not in_reach(here, target):
        raise StepFailed("out of reach", "out_of_reach")
    if target == here:
        raise StepFailed("that is where it stands", "blocked")
    if not is_replaceable(grid.material(*target)):
        raise StepFailed("that cell is taken", "blocked")
    return {"kind": "place", "started_at": at, "ends_at": round(at + PLACE_SECONDS / scale, 3),
            "target": as_point(target), "block": block}


def finish_place(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = as_cell(step["target"])
    if not is_replaceable(grid.material(*target)):
        raise StepFailed("that cell is taken", "blocked")
    state["inventory"] = take_items(state["inventory"], {step["block"]: 1})
    grid.put(*target, step["block"])
    return None


def start_eat(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item = spec["item"]
    if item not in FOOD:
        raise StepFailed(f"{label(item)} is not food")
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to eat", "missing_item")
    return {"kind": "eat", "started_at": at, "ends_at": round(at + EAT_SECONDS / scale, 3), "item": item}


def finish_eat(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    item, vitals, name = step["item"], state["vitals"], state["name"]
    state["inventory"] = take_items(state["inventory"], {item: 1})
    vitals["hunger"] = min(100.0, vitals["hunger"] + FOOD[item])
    health = FOOD_HEALTH.get(item, 0.0)
    if health < 0:
        vitals["health"] = max(min(vitals["health"], 1.0), vitals["health"] + health)
        return "sick", f"{name} ate {label(item)} and felt sick."
    chance, risk = FOOD_RISK.get(item, (0.0, 0.0))
    if chance > 0 and nature.roll(seed_of(state), as_cell(state["position"]), RISK_CHANNEL, int(at)) < chance:
        vitals["health"] = max(min(vitals["health"], 1.0), vitals["health"] + risk)
        return "sick", f"{name} ate {label(item)} and felt a little sick."
    return "ate", f"{name} ate {label(item)}."


def room_to_make(before: dict[str, int], after: dict[str, int], what: str) -> None:
    """Fail a craft, smelt or cook whose output would not fit once its inputs are used up: it would
    only be left behind (backend.survival.carrying)."""
    if not fits(before, after):
        raise StepFailed(f"no room to carry the {label(what)}", "blocked")


def start_craft(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    after = craft(state["inventory"], spec["recipe"], stations_near(grid, as_cell(state["position"])))
    room_to_make(state["inventory"], after, spec["recipe"])
    return {"kind": "craft", "started_at": at, "ends_at": round(at + CRAFT_SECONDS / scale, 3),
            "recipe": spec["recipe"]}


def finish_craft(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    stations = stations_near(grid, as_cell(state["position"]))
    state["inventory"] = craft(state["inventory"], step["recipe"], stations)
    return "craft", f"{state['name']} crafted {label(step['recipe'])}."


def start_smelt(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    after = smelt(state["inventory"], spec["item"], stations_near(grid, as_cell(state["position"])))
    room_to_make(state["inventory"], after, SMELTING[spec["item"]])
    return {"kind": "smelt", "started_at": at, "ends_at": round(at + SMELT_SECONDS / scale, 3),
            "item": spec["item"]}


def finish_smelt(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    stations = stations_near(grid, as_cell(state["position"]))
    state["inventory"] = smelt(state["inventory"], step["item"], stations)
    return "smelt", f"{state['name']} smelted {label(step['item'])}."


def start_sleep(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    # Sleep has no fixed end: actions.py ends it once Mimo is rested and it is not night. Lying on
    # a bed (the block under Mimo) it sleeps in the bed, which rests it faster.
    x, y, z = as_cell(state["position"])
    step = {"kind": "sleep", "started_at": at, "ends_at": None}
    if grid.material(x, y - 1, z) == "bed":
        step["bed"] = True
    return step


def start_wait(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    seconds = float(spec.get("seconds", 1.0))
    if seconds <= 0:
        raise StepFailed("a wait needs some time")
    return {"kind": "wait", "started_at": at, "ends_at": round(at + seconds, 3)}


register_step(StepKind("walk", start_walk, finish_walk, "walking", working=True, interruptible=True,
                       cell_field="target"))
register_step(StepKind("mine", start_mine, finish_mine, "mining", working=True, cell_field="target"))
register_step(StepKind("place", start_place, finish_place, "building", working=True, cell_field="target",
                       string_field="block"))
register_step(StepKind("eat", start_eat, finish_eat, "eating", string_field="item"))
register_step(StepKind("craft", start_craft, finish_craft, "crafting", string_field="recipe"))
register_step(StepKind("smelt", start_smelt, finish_smelt, "smelting", string_field="item"))
register_step(StepKind("sleep", start_sleep, nothing_happens, "sleeping", interruptible=True))
register_step(StepKind("wait", start_wait, nothing_happens, "idle", interruptible=True))

# M4's field work (pick, harvest, till, plant, fish, cook), M5's housework (store, take, drop) and
# L1's attack register themselves. They are imported last because they build on everything above.
from backend.survival import fieldwork, housework  # noqa: E402,F401
from backend.survival.creatures import combat  # noqa: E402,F401
