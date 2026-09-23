"""What each timed step needs, how long it takes and what it changes.

A queued step is a small dict, for example {"kind": "mine", "target": [x, y, z]}. `start_step`
checks it against the world and returns the running step with its start and end times.
`finish_step` applies it at its end time. Both raise StepFailed (a ValueError) with a short
reason; crafting errors from backend.services.crafting are ValueErrors too.
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


class StepFailed(ValueError):
    """A step cannot start or finish. The message says why."""


def as_cell(value) -> Cell:
    """A cell from [x, y, z] (queued steps) or {"x", "y", "z"} (running steps, paths and positions)."""
    if isinstance(value, dict):
        return round(value["x"]), round(value["y"]), round(value["z"])
    x, y, z = value
    return int(x), int(y), int(z)


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


def start_step(spec: dict, state: dict, grid: Grid, at: float) -> dict:
    """Check a queued step against the world and return it running, from `at` to its end time."""
    kind = spec.get("kind")
    here = as_cell(state["position"])
    inventory = state["inventory"]
    if kind == "walk":
        target = as_cell(spec["target"])
        reach = float(spec.get("reach", 0.0))
        segments = int(spec.get("segments", 0))
        if segments > MAX_SEGMENTS:
            raise StepFailed("no way there")
        cells, reached = route(grid, here, target, reach)
        if not cells and not reached:
            raise StepFailed("no way there")
        path = timed_path(grid, here, cells, at)
        return {"kind": "walk", "started_at": at, "ends_at": path[-1]["at"], "path": path,
                "target": as_point(target), "reach": reach, "reached": reached, "segments": segments}
    if kind == "mine":
        target = as_cell(spec["target"])
        if not in_reach(here, target):
            raise StepFailed("out of reach")
        material = grid.material(*target)
        seconds = mine_seconds(material, inventory)
        if seconds is None:
            raise StepFailed(f"{label(material)} cannot be mined")
        if not can_harvest(material, inventory):
            raise StepFailed(f"a stronger pickaxe is needed for {label(material)}")
        return {"kind": "mine", "started_at": at, "ends_at": round(at + seconds, 3),
                "target": as_point(target), "block": material}
    if kind == "place":
        target, block = as_cell(spec["target"]), spec["block"]
        if inventory.get(block, 0) < 1:
            raise StepFailed(f"no {label(block)} to place")
        if block not in BLOCKS:
            raise StepFailed(f"{label(block)} is not a block")
        if not in_reach(here, target):
            raise StepFailed("out of reach")
        if target == here:
            raise StepFailed("that is where it stands")
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken")
        return {"kind": "place", "started_at": at, "ends_at": round(at + PLACE_SECONDS, 3),
                "target": as_point(target), "block": block}
    if kind == "eat":
        item = spec["item"]
        if item not in FOOD:
            raise StepFailed(f"{label(item)} is not food")
        if inventory.get(item, 0) < 1:
            raise StepFailed(f"no {label(item)} to eat")
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
            raise StepFailed(f"the {label(step['block'])} is gone")
        grid.put(*target, "air")
        drop = BLOCKS.get(step["block"], {}).get("drop")
        if drop:
            add_item(state["inventory"], drop)
        return None
    if kind == "place":
        target = as_cell(step["target"])
        if not is_replaceable(grid.material(*target)):
            raise StepFailed("that cell is taken")
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
