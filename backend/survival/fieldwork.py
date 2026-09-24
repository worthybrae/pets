"""Field work: the step kinds M4 adds, registered in backend.survival.steps.

- pick(cell): take what a wild plant gives (nature.PICKS). A ripe berry bush gives 3 berries and
  turns back into a bush that regrows; a mushroom is taken whole.
- harvest(cell): take a ripe crop (nature.HARVESTS). The farmland under it stays.
- till(cell): turn grass, dirt or moss with nothing growing on it into farmland.
- plant(cell, item): put seeds or a carrot on farmland, or a sapling on grass, dirt or moss.
- fish(water cell): 20 to 60 s per catch. Whether a fish bites depends on the stock of the water
  cell's 16x16 region (nature.catches); a catch takes one fish from it. A reflex may cut it short.
- cook(item): 5 s at a lit campfire or furnace within 6 blocks, with no fuel (crafting.smelt's
  rule for food). Like crafting and smelting, it does not start when the cooked food would not
  fit (backend.survival.carrying).
All of them work on a cell within reach, like mining. steps.py imports this module last, so
start_step always knows these kinds.
"""

from __future__ import annotations

from backend.services.blocks import is_replaceable
from backend.services.crafting import COOKING, FIRES, SMELTING, add_item, smelt, take_items
from backend.survival import nature
from backend.survival.grid import Cell, Grid
from backend.survival.steps import (
    StepFailed, StepKind, as_cell, as_point, in_reach, label, register_step, room_to_make, seed_of, stations_near,
)

PICK_SECONDS = 0.5
HARVEST_SECONDS = 0.5
TILL_SECONDS = 1.0
PLANT_SECONDS = 0.3
COOK_SECONDS = 5.0


def target_in_reach(spec: dict, state: dict) -> Cell:
    target = as_cell(spec["target"])
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    return target


def running(kind: str, at: float, seconds: float, target: Cell, **fields) -> dict:
    return {"kind": kind, "started_at": at, "ends_at": round(at + seconds, 3), "target": as_point(target), **fields}


def still_there(step: dict, grid: Grid) -> Cell:
    target = as_cell(step["target"])
    if grid.material(*target) != step["block"]:
        raise StepFailed(f"the {label(step['block'])} is gone", "gone")
    return target


def open_for_planting(material: str) -> bool:
    """Air, or a plant that gives way (tall grass, flowers). Never water."""
    return material != "water" and is_replaceable(material)


def check_planting(grid: Grid, target: Cell, grows: str) -> None:
    x, y, z = target
    if not open_for_planting(grid.material(*target)):
        raise StepFailed("that cell is taken", "blocked")
    if grid.material(x, y - 1, z) not in nature.SOIL[grows]:
        raise StepFailed(f"{label(grows)} needs {' or '.join(nature.SOIL[grows])} under it", "blocked")


def start_pick(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = target_in_reach(spec, state)
    material = grid.material(*target)
    if material not in nature.PICKS:
        raise StepFailed("nothing to pick there", "gone")
    return running("pick", at, PICK_SECONDS / scale, target, block=material)


def finish_pick(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = still_there(step, grid)
    items, becomes = nature.PICKS[step["block"]]
    for item, amount in items.items():
        add_item(state["inventory"], item, amount)
    grid.put(*target, becomes)
    return None


def start_harvest(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = target_in_reach(spec, state)
    material = grid.material(*target)
    if material not in nature.HARVESTS:
        stage = nature.crop_stage(material)
        if stage is not None:
            raise StepFailed(f"the {stage[0]} is not ripe yet", "blocked")
        raise StepFailed("nothing to harvest there", "gone")
    return running("harvest", at, HARVEST_SECONDS / scale, target, block=material)


def finish_harvest(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = still_there(step, grid)
    for item, amount in nature.HARVESTS[step["block"]].items():
        add_item(state["inventory"], item, amount)
    grid.put(*target, "air")
    return None


def start_till(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = target_in_reach(spec, state)
    x, y, z = target
    material = grid.material(*target)
    if material not in nature.TILLABLE:
        raise StepFailed(f"{label(material)} cannot be tilled", "blocked")
    if not open_for_planting(grid.material(x, y + 1, z)):
        raise StepFailed("something is on it", "blocked")
    return running("till", at, TILL_SECONDS / scale, target, block=material)


def finish_till(step: dict, state: dict, grid: Grid, at: float) -> None:
    grid.put(*still_there(step, grid), "farmland")
    return None


def start_plant(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item = spec["item"]
    grows = nature.SEEDS.get(item)
    if grows is None:
        raise StepFailed(f"{label(item)} cannot be planted")
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to plant", "missing_item")
    target = target_in_reach(spec, state)
    check_planting(grid, target, grows)
    return running("plant", at, PLANT_SECONDS / scale, target, item=item, block=grows)


def finish_plant(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = as_cell(step["target"])
    check_planting(grid, target, step["block"])
    state["inventory"] = take_items(state["inventory"], {step["item"]: 1})
    grid.put(*target, step["block"])
    return None


def start_fish(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = target_in_reach(spec, state)
    if grid.material(*target) != "water":
        raise StepFailed("there is no water there", "gone")
    return running("fish", at, nature.fish_seconds(seed_of(state), target, at) / scale, target)


def finish_fish(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str] | None:
    target = as_cell(step["target"])
    if not nature.catches(seed_of(state), target, step["started_at"], nature.fish_stock(state, target)):
        return None
    nature.take_fish(state, target, at)
    add_item(state["inventory"], "raw_fish")
    return "fish", f"{state['name']} caught a fish."


def start_cook(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item = spec["item"]
    if item not in COOKING:
        raise StepFailed(f"{label(item)} cannot be cooked")
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to cook", "missing_item")
    stations = stations_near(grid, as_cell(state["position"]))
    if not stations.intersection(FIRES):
        raise StepFailed("no fire to cook on", "missing_item")
    room_to_make(state["inventory"], smelt(state["inventory"], item, stations), SMELTING[item])
    return {"kind": "cook", "started_at": at, "ends_at": round(at + COOK_SECONDS / scale, 3), "item": item}


def finish_cook(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    stations = stations_near(grid, as_cell(state["position"]))
    state["inventory"] = smelt(state["inventory"], step["item"], stations)
    return "cook", f"{state['name']} cooked {label(step['item'])}."


register_step(StepKind("pick", start_pick, finish_pick, "picking", working=True, cell_field="target"))
register_step(StepKind("harvest", start_harvest, finish_harvest, "harvesting", working=True, cell_field="target"))
register_step(StepKind("till", start_till, finish_till, "tilling", working=True, cell_field="target"))
register_step(StepKind("plant", start_plant, finish_plant, "planting", working=True, cell_field="target",
                       string_field="item"))
register_step(StepKind("fish", start_fish, finish_fish, "fishing", interruptible=True, cell_field="target"))
register_step(StepKind("cook", start_cook, finish_cook, "cooking", string_field="item"))
