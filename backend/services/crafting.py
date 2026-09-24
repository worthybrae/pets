"""Block properties and a small survival crafting chain for Mimo."""

from __future__ import annotations

from copy import deepcopy

from backend.services.blocks import BLOCK_PROPERTIES

# Block properties live in shared/blocks.json so the viewer uses the same list.
BLOCKS = BLOCK_PROPERTIES

RECIPES = {
    "planks": {"ingredients": {"oak_log": 1}, "output": {"planks": 4}},
    "sticks": {"ingredients": {"planks": 2}, "output": {"sticks": 4}},
    "crafting_table": {"ingredients": {"planks": 4}, "output": {"crafting_table": 1}},
    "furnace": {"ingredients": {"cobblestone": 8}, "output": {"furnace": 1}, "station": "crafting_table"},
    "wooden_pickaxe": {"ingredients": {"planks": 3, "sticks": 2}, "output": {"wooden_pickaxe": 1}, "station": "crafting_table"},
    "stone_pickaxe": {"ingredients": {"cobblestone": 3, "sticks": 2}, "output": {"stone_pickaxe": 1}, "station": "crafting_table"},
    "iron_pickaxe": {"ingredients": {"iron_ingot": 3, "sticks": 2}, "output": {"iron_pickaxe": 1}, "station": "crafting_table"},
    "bread": {"ingredients": {"wheat": 3}, "output": {"bread": 1}, "station": "crafting_table"},
    "campfire": {"ingredients": {"oak_log": 2, "sticks": 3}, "output": {"campfire": 1}},
    "torch": {"ingredients": {"coal": 1, "sticks": 1}, "output": {"torch": 4}},
    "chest": {"ingredients": {"planks": 8}, "output": {"chest": 1}},
    "bed": {"ingredients": {"planks": 6}, "output": {"bed": 1}},
    "wooden_axe": {"ingredients": {"planks": 3, "sticks": 2}, "output": {"wooden_axe": 1}, "station": "crafting_table"},
    "stone_axe": {"ingredients": {"cobblestone": 3, "sticks": 2}, "output": {"stone_axe": 1}, "station": "crafting_table"},
    "iron_axe": {"ingredients": {"iron_ingot": 3, "sticks": 2}, "output": {"iron_axe": 1}, "station": "crafting_table"},
    "wooden_sword": {"ingredients": {"planks": 2, "sticks": 1}, "output": {"wooden_sword": 1}, "station": "crafting_table"},
    "stone_sword": {"ingredients": {"cobblestone": 2, "sticks": 1}, "output": {"stone_sword": 1}, "station": "crafting_table"},
    "iron_sword": {"ingredients": {"iron_ingot": 2, "sticks": 1}, "output": {"iron_sword": 1}, "station": "crafting_table"},
}

TOOL_RANK = {"wooden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3}
SMELTING = {"iron_ore": "iron_ingot", "copper_ore": "copper_ingot", "sand": "glass", "clay": "brick",
            "raw_fish": "cooked_fish", "raw_beef": "cooked_beef", "raw_mutton": "cooked_mutton",
            "raw_chicken": "cooked_chicken", "raw_rabbit": "cooked_rabbit"}
# Food cooks at a lit campfire or a furnace and burns no fuel: the fire is already lit.
COOKING = frozenset({"raw_fish", "raw_beef", "raw_mutton", "raw_chicken", "raw_rabbit"})
FIRES = ("campfire", "furnace")


def add_item(inventory: dict[str, int], item: str, amount: int = 1) -> None:
    inventory[item] = inventory.get(item, 0) + amount


def take_items(inventory: dict[str, int], ingredients: dict[str, int]) -> dict[str, int]:
    if any(inventory.get(item, 0) < amount for item, amount in ingredients.items()):
        missing = [item for item, amount in ingredients.items() if inventory.get(item, 0) < amount]
        raise ValueError(f"Missing materials: {', '.join(missing)}")
    result = deepcopy(inventory)
    for item, amount in ingredients.items():
        result[item] -= amount
        if result[item] == 0:
            del result[item]
    return result


def craft(inventory: dict[str, int], recipe_name: str, nearby_stations: set[str]) -> dict[str, int]:
    recipe = RECIPES.get(recipe_name)
    if not recipe:
        raise ValueError("Unknown recipe")
    if recipe.get("station") and recipe["station"] not in nearby_stations:
        raise ValueError(f"A placed {recipe['station']} is required")
    result = take_items(inventory, recipe["ingredients"])
    for item, amount in recipe["output"].items():
        add_item(result, item, amount)
    return result


def smelt(inventory: dict[str, int], input_item: str, nearby_stations: set[str]) -> dict[str, int]:
    output = SMELTING.get(input_item)
    if not output:
        raise ValueError("That material cannot be smelted")
    if input_item in COOKING:
        if not set(nearby_stations).intersection(FIRES):
            raise ValueError("A placed campfire or furnace is required")
        result = take_items(inventory, {input_item: 1})
    else:
        if "furnace" not in nearby_stations:
            raise ValueError("A placed furnace is required")
        fuel = "coal" if inventory.get("coal", 0) else "planks"
        result = take_items(inventory, {input_item: 1, fuel: 1})
    add_item(result, output)
    return result


def can_harvest(material: str, inventory: dict[str, int]) -> bool:
    required = BLOCKS.get(material, {}).get("requires")
    if not required:
        return True
    return max((TOOL_RANK.get(item, 0) for item in inventory if inventory[item] > 0), default=0) >= TOOL_RANK[required]
