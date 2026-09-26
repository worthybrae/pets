"""Housework: the step kinds M5 adds for chests and for leaving things behind, registered in
backend.survival.steps.

- store(cell, item, amount): put carried items into the chest at the cell, within reach. What the
  chest has no room for (24 stacks of 32, backend.survival.carrying) stays with Mimo.
- take(cell, item, amount): take items out of the chest, as many as it holds and Mimo can carry. Making
  wave 2: take(..., away=True) leaves them behind at once (clearing rubble out of a full chest).
- drop(item, amount): leave carried items behind for good. There are no item entities in the
  world, so dropped things are gone.
Each takes 0.3 s, like placing a block. Chest contents live in the state, in state["chests"]
keyed "x,y,z", so they are saved with Mimo and sent to the viewer. A chest that is gone takes
what was in it along.
"""

from __future__ import annotations

from backend.services.crafting import add_item, take_items
from backend.survival.carrying import CARRY_STACKS, CHEST_STACKS, room_for
from backend.survival.grid import Cell, Grid
from backend.survival.steps import (
    PLACE_SECONDS, StepFailed, StepKind, as_cell, as_point, in_reach, label, register_step,
)


def chest_key(cell: Cell) -> str:
    return f"{cell[0]},{cell[1]},{cell[2]}"


def chest_items(state: dict, cell: Cell) -> dict[str, int]:
    """What the chest at `cell` holds (a live dict inside the state; empty for a new chest)."""
    return state.setdefault("chests", {}).setdefault(chest_key(cell), {})


def amount_of(spec: dict) -> int:
    amount = spec.get("amount", 1)
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
        raise StepFailed("bad step: amount")
    return amount


def chest_in_reach(spec: dict, state: dict, grid: Grid) -> Cell:
    target = as_cell(spec["target"])
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    if grid.material(*target) != "chest":
        state.get("chests", {}).pop(chest_key(target), None)
        raise StepFailed("there is no chest there", "gone")
    return target


def running(kind: str, at: float, scale: float, item: str, amount: int, target: Cell | None = None) -> dict:
    step = {"kind": kind, "started_at": at, "ends_at": round(at + PLACE_SECONDS / scale, 3), "item": item,
            "amount": amount}
    if target is not None:
        step["target"] = as_point(target)
    return step


def start_store(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item, amount = spec["item"], amount_of(spec)
    target = chest_in_reach(spec, state, grid)
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to put away", "missing_item")
    if room_for(chest_items(state, target), item, CHEST_STACKS) < 1:
        raise StepFailed("the chest is full", "blocked")
    return running("store", at, scale, item, amount, target)


def finish_store(step: dict, state: dict, grid: Grid, at: float) -> None:
    target = chest_in_reach(step, state, grid)
    chest, item = chest_items(state, target), step["item"]
    moved = min(step["amount"], state["inventory"].get(item, 0), room_for(chest, item, CHEST_STACKS))
    if moved > 0:
        state["inventory"] = take_items(state["inventory"], {item: moved})
        add_item(chest, item, moved)
    return None


def start_take(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item, amount = spec["item"], amount_of(spec)
    target = chest_in_reach(spec, state, grid)
    if chest_items(state, target).get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} in the chest", "missing_item")
    away = spec.get("away") is True
    if not away and room_for(state["inventory"], item, CARRY_STACKS) < 1:
        raise StepFailed("its arms are full", "blocked")
    return {**running("take", at, scale, item, amount, target), **({"away": True} if away else {})}


def finish_take(step: dict, state: dict, grid: Grid, at: float) -> None:
    """Take the items out; one `away` (Making wave 2: clearing a full chest of rubble) leaves them behind at
    once, as a drop does, so it needs no room in Mimo's arms."""
    target = chest_in_reach(step, state, grid)
    chest, item = chest_items(state, target), step["item"]
    away = step.get("away") is True
    room = step["amount"] if away else room_for(state["inventory"], item, CARRY_STACKS)
    moved = min(step["amount"], chest.get(item, 0), room)
    if moved > 0:
        chest[item] -= moved
        if chest[item] == 0:
            del chest[item]
        if not away:
            add_item(state["inventory"], item, moved)
    return None


def start_drop(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    item, amount = spec["item"], amount_of(spec)
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {label(item)} to drop", "missing_item")
    return running("drop", at, scale, item, amount)


def finish_drop(step: dict, state: dict, grid: Grid, at: float) -> None:
    dropped = min(step["amount"], state["inventory"].get(step["item"], 0))
    if dropped > 0:
        state["inventory"] = take_items(state["inventory"], {step["item"]: dropped})
    return None


register_step(StepKind("store", start_store, finish_store, "storing", cell_field="target", string_field="item"))
register_step(StepKind("take", start_take, finish_take, "taking", cell_field="target", string_field="item"))
register_step(StepKind("drop", start_drop, finish_drop, "dropping", string_field="item"))
