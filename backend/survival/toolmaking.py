"""craft_tools: make the next pickaxe, with portable stations.

The ladder is wooden pickaxe, stone pickaxe, iron pickaxe. Only the next one Mimo lacks is on
offer, and only when everything it needs can be made from what Mimo carries. The planner works
the whole chain out on a copy of the inventory: logs into planks, planks into sticks, a crafting
table, and for iron a furnace and three smelted ingots (coal as fuel when Mimo has it, planks
otherwise, as crafting.smelt does). Stations are portable: Mimo places a table or furnace in an
open cell beside it (or above it), crafts or smelts, then mines the station back into its
inventory, so it never has to remember where it left one. A station already placed within
reach is used as it is and left there. One tool per choice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.blocks import is_replaceable
from backend.services.crafting import RECIPES, SMELTING, TOOL_RANK
from backend.survival.grid import Cell
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import STATION_REACH, WORKSTATIONS

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

LADDER = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe")
STATIONS = {"wooden_pickaxe": ("crafting_table",), "stone_pickaxe": ("crafting_table",),
            "iron_pickaxe": ("crafting_table", "furnace")}
SMELTED = {output: ore for ore, output in SMELTING.items()}
# Cells beside Mimo at its level, then the one above it.
NEIGHBOURS = ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0))
MAX_DEPTH = 12
RETRIES = 8


class Short(Exception):
    """Something the chain needs cannot be made from what Mimo carries."""


def next_tool(inventory: dict) -> str | None:
    """The next pickaxe up the ladder, or None when Mimo has the best one."""
    rank = max((TOOL_RANK[tool] for tool in TOOL_RANK if inventory.get(tool, 0) > 0), default=0)
    return LADDER[rank] if rank < len(LADDER) else None


def make(inventory: dict, item: str, amount: int, steps: list[dict], depth: int = 0) -> None:
    """Add craft and smelt steps until `inventory` holds `amount` of `item`, changing `inventory`
    the way the steps will. Raises Short when something is missing."""
    if depth > MAX_DEPTH:
        raise Short(item)
    while inventory.get(item, 0) < amount:
        recipe = RECIPES.get(item)
        if recipe is not None:
            # An ingredient made later can use up one made earlier (sticks are made from planks).
            for _ in range(RETRIES):
                short = [(name, count) for name, count in recipe["ingredients"].items()
                         if inventory.get(name, 0) < count]
                if not short:
                    break
                for name, count in short:
                    make(inventory, name, count, steps, depth + 1)
            else:
                raise Short(item)
            for name, count in recipe["ingredients"].items():
                inventory[name] -= count
            for name, count in recipe["output"].items():
                inventory[name] = inventory.get(name, 0) + count
            steps.append({"kind": "craft", "recipe": item})
        elif item in SMELTED:
            ore = SMELTED[item]
            if inventory.get(ore, 0) < 1:
                raise Short(ore)
            fuel = "coal" if inventory.get("coal", 0) else "planks"
            make(inventory, fuel, 1, steps, depth + 1)
            inventory[ore] -= 1
            inventory[fuel] -= 1
            inventory[item] = inventory.get(item, 0) + 1
            steps.append({"kind": "smelt", "item": ore})
        else:
            raise Short(item)


def free_cells(s: Situation) -> list[Cell]:
    """Open cells beside Mimo (or above it) where a station can stand."""
    x, y, z = s.here
    cells = []
    for dx, dy, dz in NEIGHBOURS:
        cell = (x + dx, y + dy, z + dz)
        material = s.grid.material(*cell)
        if material != "water" and is_replaceable(material):
            cells.append(cell)
    return cells


def tool_plan(s: Situation) -> list[dict] | None:
    """The steps that make the next pickaxe, or None when it cannot be made now."""
    tool = next_tool(s.inventory)
    if tool is None:
        return None
    inventory = dict(s.inventory)
    x, _, z = s.here
    near = s.grid.placed_near(x, z, STATION_REACH, WORKSTATIONS)
    free = free_cells(s)
    steps: list[dict] = []
    placed: list[Cell] = []
    try:
        for station in STATIONS[tool]:
            if station in near:
                continue
            make(inventory, station, 1, steps)
            if not free:
                raise Short(station)
            cell = free.pop(0)
            steps.append({"kind": "place", "target": list(cell), "block": station})
            inventory[station] -= 1
            placed.append(cell)
        make(inventory, tool, 1, steps)
    except Short:
        return None
    steps.extend({"kind": "mine", "target": list(cell)} for cell in reversed(placed))
    return steps


def plan_tools(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return tool_plan(s) or []


register(Purpose(
    "craft_tools", "craft tools", "Make the next pickaxe from carried materials with a portable crafting table.",
    valid=lambda s: tool_plan(s) is not None,
    facts=lambda s: f"can make a {next_tool(s.inventory).replace('_', ' ')} now",
    score=lambda s: 70.0 + s.trait("diligence") / 10,
    plan=plan_tools,
    thoughts=("I can make a better pickaxe now.", "Time to make a proper tool.")))
