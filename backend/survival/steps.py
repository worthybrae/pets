"""What each timed step needs, how long it takes and what it changes.

A queued step is a small dict, for example {"kind": "mine", "target": [x, y, z]}. `start_step`
checks it against the world and returns the running step with its start and end times.
`finish_step` applies it at its end time. Both raise StepFailed (a ValueError) with a short
reason; crafting errors from backend.services.crafting are ValueErrors too. `validate_step` runs
first inside `start_step`, so a malformed spec (a stray planner bug, a corrupted queue) fails
with a clean StepFailed instead of a TypeError from as_cell or a dict lookup further in.
"""

from __future__ import annotations

import math

from backend.services.blocks import hardness, is_replaceable, mining_tool
from backend.services.crafting import BLOCKS, add_item, can_harvest, craft, smelt, take_items
from backend.survival.grid import Cell, Grid
from backend.survival.pathing import route, timed_path

REACH = 4.0
STATION_REACH = 6.0
WORKSTATIONS = ("crafting_table", "furnace")
PLACE_SECONDS = 0.3
EAT_SECONDS = 1.6
CRAFT_SECONDS = 1.0
SMELT_SECONDS = 5.0
PICKAXE_SPEED = {"wooden_pickaxe": 2.0, "stone_pickaxe": 4.0, "iron_pickaxe": 6.0}
# Axe recipes arrive with purposeful building (M5). Any axe doubles the speed on wood.
AXES = ("wooden_axe", "stone_axe", "iron_axe")
AXE_SPEED = 2.0
# Hunger each food restores (spec section 7). The food items themselves arrive in M4.
FOOD = {"berries": 8.0, "brown_mushroom": 6.0, "carrot": 10.0, "bread": 25.0, "raw_fish": 8.0, "cooked_fish": 30.0}
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


def in_reach(here: Cell, target: Cell) -> bool:
    return math.dist(here, target) <= REACH


def stations_near(grid: Grid, here: Cell) -> set[str]:
    return grid.placed_near(here[0], here[2], STATION_REACH, WORKSTATIONS)


KNOWN_KINDS = frozenset({"walk", "mine", "place", "eat", "craft", "smelt", "sleep", "wait"})
CELL_FIELD = {"walk": "target", "mine": "target", "place": "target"}
STRING_FIELD = {"place": "block", "eat": "item", "craft": "recipe", "smelt": "item"}


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_step(spec: dict) -> None:
    """Check a queued step's shape before it touches the world or an inventory dict.

    A field that is present but the wrong shape (a target that isn't a cell, a block that isn't
    a string, a non-finite reach or wait) raises StepFailed here, short and clear, instead of a
    TypeError from as_cell or a dict lookup deeper in start_step. A field that is simply missing
    is left to the checks below, which already raise their own StepFailed for it.
    """
    kind = spec.get("kind")
    if kind not in KNOWN_KINDS:
        raise StepFailed(f"unknown step {kind!r}")
    cell_field = CELL_FIELD.get(kind)
    if cell_field and cell_field in spec:
        try:
            as_cell(spec[cell_field])
        except ValueError:
            raise StepFailed(f"bad step: {cell_field}")
    string_field = STRING_FIELD.get(kind)
    if string_field and string_field in spec and not isinstance(spec[string_field], str):
        raise StepFailed(f"bad step: {string_field}")
    if kind == "walk" and "reach" in spec and not (_finite_number(spec["reach"]) and spec["reach"] >= 0):
        raise StepFailed("bad step: reach")
    if kind == "wait" and "seconds" in spec and not _finite_number(spec["seconds"]):
        raise StepFailed("bad step: seconds")


def start_step(spec: dict, state: dict, grid: Grid, at: float) -> dict:
    """Check a queued step against the world and return it running, from `at` to its end time."""
    validate_step(spec)
    kind = spec.get("kind")
    here = as_cell(state["position"])
    inventory = state["inventory"]
    if kind == "walk":
        target = as_cell(spec["target"])
        reach = float(spec.get("reach", 0.0))
        segments = int(spec.get("segments", 0))
        if segments > MAX_SEGMENTS:
            raise StepFailed("no way there", "no_path")
        cells, reached = route(grid, here, target, reach)
        if not cells and not reached:
            raise StepFailed("no way there", "no_path")
        path = timed_path(grid, here, cells, at)
        return {"kind": "walk", "started_at": at, "ends_at": path[-1]["at"], "path": path,
                "target": as_point(target), "reach": reach, "reached": reached, "segments": segments}
    if kind == "mine":
        target = as_cell(spec["target"])
        if not in_reach(here, target):
            raise StepFailed("out of reach", "out_of_reach")
        material = grid.material(*target)
        seconds = mine_seconds(material, inventory)
        if seconds is None:
            raise StepFailed(f"{label(material)} cannot be mined", "blocked")
        if not can_harvest(material, inventory):
            raise StepFailed(f"a stronger pickaxe is needed for {label(material)}", "missing_item")
        return {"kind": "mine", "started_at": at, "ends_at": round(at + seconds, 3),
                "target": as_point(target), "block": material}
    if kind == "place":
        target, block = as_cell(spec["target"]), spec["block"]
        if inventory.get(block, 0) < 1:
            raise StepFailed(f"no {label(block)} to place", "missing_item")
        if block not in BLOCKS:
            raise StepFailed(f"{label(block)} is not a block")
        if not in_reach(here, target):
            raise StepFailed("out of reach", "out_of_reach")
        if target == here:
            raise StepFailed("that is where it stands", "blocked")
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken", "blocked")
        return {"kind": "place", "started_at": at, "ends_at": round(at + PLACE_SECONDS, 3),
                "target": as_point(target), "block": block}
    if kind == "eat":
        item = spec["item"]
        if item not in FOOD:
            raise StepFailed(f"{label(item)} is not food")
        if inventory.get(item, 0) < 1:
            raise StepFailed(f"no {label(item)} to eat", "missing_item")
        return {"kind": "eat", "started_at": at, "ends_at": round(at + EAT_SECONDS, 3), "item": item}
    if kind == "craft":
        craft(inventory, spec["recipe"], stations_near(grid, here))
        return {"kind": "craft", "started_at": at, "ends_at": round(at + CRAFT_SECONDS, 3), "recipe": spec["recipe"]}
    if kind == "smelt":
        smelt(inventory, spec["item"], stations_near(grid, here))
        return {"kind": "smelt", "started_at": at, "ends_at": round(at + SMELT_SECONDS, 3), "item": spec["item"]}
    if kind == "sleep":
        # Sleep has no fixed end: actions.py ends it once Mimo is rested and it is not night.
        return {"kind": "sleep", "started_at": at, "ends_at": None}
    if kind == "wait":
        seconds = float(spec.get("seconds", 1.0))
        if seconds <= 0:
            raise StepFailed("a wait needs some time")
        return {"kind": "wait", "started_at": at, "ends_at": round(at + seconds, 3)}
    raise StepFailed(f"unknown step {kind!r}")


def finish_step(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str] | None:
    """Apply a running step at its end. Returns an event (kind, text) worth logging, if any."""
    kind, name = step["kind"], state["name"]
    if kind == "walk":
        state["position"] = position_of(step["path"][-1])
        return None
    if kind == "mine":
        target = as_cell(step["target"])
        if grid.material(*target) != step["block"]:
            raise StepFailed(f"the {label(step['block'])} is gone", "gone")
        grid.put(*target, "air")
        drop = BLOCKS.get(step["block"], {}).get("drop")
        if drop:
            add_item(state["inventory"], drop)
        return None
    if kind == "place":
        target = as_cell(step["target"])
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken", "blocked")
        state["inventory"] = take_items(state["inventory"], {step["block"]: 1})
        grid.put(*target, step["block"])
        return None
    if kind == "eat":
        state["inventory"] = take_items(state["inventory"], {step["item"]: 1})
        state["vitals"]["hunger"] = min(100.0, state["vitals"]["hunger"] + FOOD[step["item"]])
        return "ate", f"{name} ate {label(step['item'])}."
    if kind == "craft":
        stations = stations_near(grid, as_cell(state["position"]))
        state["inventory"] = craft(state["inventory"], step["recipe"], stations)
        return "craft", f"{name} crafted {label(step['recipe'])}."
    if kind == "smelt":
        stations = stations_near(grid, as_cell(state["position"]))
        state["inventory"] = smelt(state["inventory"], step["item"], stations)
        return "smelt", f"{name} smelted {label(step['item'])}."
    return None
