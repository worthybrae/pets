"""craft_tools: make the next pickaxe, and swords, with portable stations.

The ladder is wooden pickaxe, stone pickaxe, iron pickaxe, gold pickaxe, diamond pickaxe (L3). Only
the next one Mimo lacks is on offer (and, over an iron pickaxe, a diamond one first: diamonds need
no smelting, so gold may be skipped), and only when everything it needs can be made from what Mimo
carries. Swords (L1) climb a ladder of their own (wooden, stone, iron, gold, diamond: 2 planks,
cobblestone, ingots or diamonds and a stick, at a crafting table) no higher than the best pickaxe
Mimo has. The sword a new pickaxe opens up is
made in the same batch, right after it, when the materials stretch that far; with no pickaxe to
make, the best sword Mimo may make comes alone. The planner works the whole chain out on a copy
of the inventory: logs into planks, planks into sticks, a crafting
table, and for iron a furnace and three smelted ingots (coal as fuel when Mimo has it, planks
otherwise, as crafting.smelt does). Stations are portable: Mimo places a table or furnace in an
open cell beside it (or above it), crafts or smelts, then mines the station back into its
inventory, so it never has to remember where it left one. The mine-back steps are marked `keep`:
they still run when a new purpose, a failure or a reflex drops the rest of the plan. A station
already placed within reach is used as it is and left there. One pickaxe (with its sword) or one
sword per choice, and none while something the chain makes would not fit in Mimo's arms
(carrying.crafts_fit).

Below the natural surface an open cell beside Mimo may be its only way out, and the cell above
its head is the headroom it needs to climb, so there Mimo digs a niche into a solid side wall
(under a solid ceiling, so no floor is dug away) and puts the station in it. The reflex warm_up
places a carried furnace the same way. A station never goes where something Mimo built keeps its
room, door or way in (structures.reserved), so inside its shelter Mimo makes no tools.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.blocks import hardness, is_replaceable, is_solid
from backend.services.crafting import RECIPES, SMELTING, TOOL_RANK, can_harvest, fuel_of, have, paid, planks_recipe
from backend.survival.carrying import crafts_fit
from backend.survival.creatures.harm import IRON_ARMOR, armor_wanted
from backend.survival.grid import Cell
from backend.survival.purposes import Purpose, register, underground
from backend.survival.situation import Situation
from backend.survival.steps import STATION_REACH, WORKSTATIONS
from backend.survival.structures import reserved

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

LADDER = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe", "gold_pickaxe", "diamond_pickaxe")
SWORD_LADDER = ("wooden_sword", "stone_sword", "iron_sword", "gold_sword", "diamond_sword")
STATIONS = {"wooden_pickaxe": ("crafting_table",), "stone_pickaxe": ("crafting_table",),
            "iron_pickaxe": ("crafting_table", "furnace"), "wooden_sword": ("crafting_table",),
            "stone_sword": ("crafting_table",), "iron_sword": ("crafting_table", "furnace"),
            "gold_pickaxe": ("crafting_table", "furnace"), "gold_sword": ("crafting_table", "furnace"),
            "diamond_pickaxe": ("crafting_table",), "diamond_sword": ("crafting_table",),
            "iron_cap": ("crafting_table", "furnace"), "iron_tunic": ("crafting_table", "furnace"), "lantern": ()}
LANTERNS_WANTED = 4  # lanterns Mimo makes to carry home (light_up hangs them), from spare iron
# L5: an item small pieces make too, by the recipe named here (4 gold nuggets make a gold ingot),
# made that way when there is no ore to smelt for it (`pooled`).
POOLED = {"gold_ingot": "gold_nuggets"}
SMELTED = {output: ore for ore, output in SMELTING.items()}
# Cells beside Mimo at its level, then the one above it.
SIDES = ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1))
NEIGHBOURS = (*SIDES, (0, 1, 0))
MAX_DEPTH = 12
RETRIES = 8


class Short(Exception):
    """Something the chain needs cannot be made from what Mimo carries."""


def next_tool(inventory: dict) -> str | None:
    """The next pickaxe up the ladder, or None when Mimo has the best one."""
    rank = max((TOOL_RANK[tool] for tool in TOOL_RANK if inventory.get(tool, 0) > 0), default=0)
    return LADDER[rank] if rank < len(LADDER) else None


def open_swords(inventory: dict) -> list[str]:
    """The swords Mimo may make now, best first: better than the best one it has, and no better
    than the tier of its best pickaxe."""
    sword = max((rank for rank, name in enumerate(SWORD_LADDER, start=1) if inventory.get(name, 0) > 0), default=0)
    pickaxe = max((TOOL_RANK[tool] for tool in TOOL_RANK if inventory.get(tool, 0) > 0), default=0)
    return list(reversed(SWORD_LADDER[sword:pickaxe]))


def upgrades(inventory: dict) -> list[str]:
    """The pickaxes craft_tools may make next, best first: the next one up the ladder and, over an
    iron pickaxe, the diamond one before the gold one (L3)."""
    pickaxe = next_tool(inventory)
    if pickaxe == "gold_pickaxe":
        return ["diamond_pickaxe", "gold_pickaxe"]
    return [] if pickaxe is None else [pickaxe]


def tool_orders(inventory: dict, armor: bool = False) -> list[tuple[str, ...]]:
    """What craft_tools may make, first choice first: the next pickaxe with the best sword it opens
    up, the pickaxe alone, then a sword alone; then (L3) with `armor` (a creature has hurt Mimo) the
    iron armor it lacks, and lanterns from spare iron once it wears both pieces."""
    orders: list[tuple[str, ...]] = []
    for pickaxe in upgrades(inventory):
        orders += [(pickaxe, sword) for sword in open_swords({**inventory, pickaxe: 1})]
        orders.append((pickaxe,))
    orders += [(sword,) for sword in open_swords(inventory)]
    return orders + (armor_orders(inventory) if armor else []) + lantern_orders(inventory)


def armor_orders(inventory: dict) -> list[tuple[str, ...]]:
    """Iron armor once Mimo has an iron pickaxe or better (L3): the pieces it lacks together, then each
    alone. The ingots are smelted at a furnace placed for it, like the iron pickaxe's."""
    if max((TOOL_RANK[tool] for tool in TOOL_RANK if inventory.get(tool, 0) > 0), default=0) < TOOL_RANK["iron_pickaxe"]:
        return []
    missing = tuple(piece for piece in IRON_ARMOR if inventory.get(piece, 0) < 1)
    return ([missing] if len(missing) > 1 else []) + [(piece,) for piece in missing]


def lantern_orders(inventory: dict) -> list[tuple[str, ...]]:
    """A lantern from a carried iron ingot and a torch, once Mimo wears both iron pieces, while it
    carries fewer than LANTERNS_WANTED (L3)."""
    done = all(inventory.get(piece, 0) > 0 for piece in IRON_ARMOR)
    return [("lantern",)] if done and inventory.get("iron_ingot", 0) > 0 and inventory.get("lantern", 0) < LANTERNS_WANTED else []


def tool_words(tools: tuple[str, ...]) -> str:
    """ "a stone pickaxe and an iron cap" """
    return " and ".join(f"{'an' if tool[0] in 'aeiou' else 'a'} {tool.replace('_', ' ')}" for tool in tools)


def make(inventory: dict, item: str, amount: int, steps: list[dict], depth: int = 0) -> None:
    """Add craft and smelt steps until `inventory` holds `amount` of `item`, changing `inventory`
    the way the steps will. Raises Short when something is missing."""
    if depth > MAX_DEPTH:
        raise Short(item)
    while have(inventory, item) < amount:
        recipe_name = planks_recipe(inventory) if item == "planks" else item
        recipe = RECIPES.get(recipe_name)
        if recipe is not None:
            # An ingredient made later can use up one made earlier (sticks are made from planks).
            for _ in range(RETRIES):
                short = [(name, count) for name, count in recipe["ingredients"].items()
                         if have(inventory, name) < count]
                if not short:
                    break
                for name, count in short:
                    make(inventory, name, count, steps, depth + 1)
            else:
                raise Short(item)
            for name, count in paid(inventory, recipe["ingredients"]).items():
                inventory[name] -= count
            for name, count in recipe["output"].items():
                inventory[name] = inventory.get(name, 0) + count
            steps.append({"kind": "craft", "recipe": recipe_name})
        elif item in SMELTED:
            ore = SMELTED[item]
            if inventory.get(ore, 0) < 1 and pooled(inventory, item, steps):
                continue
            if inventory.get(ore, 0) < 1:
                raise Short(ore)
            if not inventory.get("coal", 0):
                make(inventory, "planks", 1, steps, depth + 1)
            fuel = fuel_of(inventory)
            inventory[ore] -= 1
            inventory[fuel] -= 1
            inventory[item] = inventory.get(item, 0) + 1
            steps.append({"kind": "smelt", "item": ore})
        else:
            raise Short(item)


def pooled(inventory: dict, item: str, steps: list[dict]) -> bool:
    """L5: craft one `item` from its small pieces (POOLED) when Mimo carries enough of them; False when
    it does not."""
    name = POOLED.get(item)
    recipe = RECIPES.get(name) if name else None
    if recipe is None or any(have(inventory, part) < count for part, count in recipe["ingredients"].items()):
        return False
    for part, count in paid(inventory, recipe["ingredients"]).items():
        inventory[part] -= count
    for part, count in recipe["output"].items():
        inventory[part] = inventory.get(part, 0) + count
    steps.append({"kind": "craft", "recipe": name})
    return True


def free_cells(s: Situation) -> list[Cell]:
    """Open cells beside Mimo (or above it) where a station can stand, on or above the natural
    surface. Below it, none: an open cell there may be the way out."""
    if underground(s):
        return []
    x, y, z = s.here
    cells = []
    for dx, dy, dz in NEIGHBOURS:
        cell = (x + dx, y + dy, z + dz)
        material = s.grid.material(*cell)
        if material != "water" and is_replaceable(material) and not reserved(s.grid, cell):
            cells.append(cell)
    return cells


def niches(s: Situation) -> list[Cell]:
    """Solid side cells Mimo can mine to make room for a station below the surface, each under a
    solid ceiling (so it is nobody's floor). Cells across the dig heading come first, so the next
    stair down is left alone."""
    x, y, z = s.here
    heading = s.brain.get("dig_heading") or (0, 0)
    along = {(heading[0], heading[1]), (-heading[0], -heading[1])}
    found = []
    for dx, _, dz in sorted(SIDES, key=lambda side: (side[0], side[2]) in along):
        cell = (x + dx, y, z + dz)
        material = s.grid.material(*cell)
        if (is_solid(material) and hardness(material) is not None and can_harvest(material, s.inventory)
                and s.grid.solid((x + dx, y + 1, z + dz))):
            found.append(cell)
    return found


def station_spots(s: Situation) -> list[tuple[Cell, bool]]:
    """Where a station can go, as (cell, mine it first): open cells on the surface, dug niches
    below it. Never the headroom or an open cell below the surface."""
    if underground(s):
        return [(cell, True) for cell in niches(s)]
    return [(cell, False) for cell in free_cells(s)]


def place_station(spots: list[tuple[Cell, bool]], block: str, steps: list[dict]) -> Cell | None:
    """Add the steps that put `block` in the first spot (digging the niche first). None when there
    is no spot left."""
    if not spots:
        return None
    cell, dig = spots.pop(0)
    if dig:
        steps.append({"kind": "mine", "target": list(cell)})
    steps.append({"kind": "place", "target": list(cell), "block": block})
    return cell


def tool_steps(s: Situation, tools: tuple[str, ...]) -> list[dict] | None:
    """The steps that make `tools` in order, or None when they cannot all be made now."""
    inventory = dict(s.inventory)
    x, _, z = s.here
    near = s.grid.placed_near(x, z, STATION_REACH, WORKSTATIONS)
    spots = station_spots(s)
    steps: list[dict] = []
    placed: list[Cell] = []
    try:
        for station in dict.fromkeys(station for tool in tools for station in STATIONS[tool]):
            if station in near:
                continue
            make(inventory, station, 1, steps)
            cell = place_station(spots, station, steps)
            if cell is None:
                raise Short(station)
            inventory[station] -= 1
            placed.append(cell)
        for tool in tools:
            make(inventory, tool, 1, steps)
    except Short:
        return None
    steps.extend({"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(placed))
    return steps if crafts_fit(s.inventory, steps) else None


def tool_choice(s: Situation) -> tuple[tuple[str, ...], list[dict]] | None:
    """The first of tool_orders that can be made now, with its steps; or None."""
    def look() -> tuple[tuple[str, ...], list[dict]] | None:
        for tools in tool_orders(s.inventory, armor_wanted(s.state)):
            steps = tool_steps(s, tools)
            if steps is not None:
                return tools, steps
        return None
    return s.sensed("tool_choice", look)


def tool_plan(s: Situation) -> list[dict] | None:
    """The steps that make the next pickaxe (and the sword it opens up) or a sword, or None."""
    choice = tool_choice(s)
    return None if choice is None else list(choice[1])


def plan_tools(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return tool_plan(s) or []


register(Purpose(
    "craft_tools", "craft tools",
    "Make the next pickaxe, and a sword, from carried materials with a portable crafting table.",
    valid=lambda s: tool_plan(s) is not None,
    facts=lambda s: f"can make {tool_words(tool_choice(s)[0])} now",
    score=lambda s: 70.0 + s.trait("diligence") / 10,
    plan=plan_tools,
    thoughts=("I can make a better pickaxe now.", "Time to make a proper tool.")))
