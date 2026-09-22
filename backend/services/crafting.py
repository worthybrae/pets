"""Block properties and a small survival crafting chain for Mimo."""

from __future__ import annotations

from copy import deepcopy

BLOCKS = {
    "grass": {"color": [127, 173, 137], "drop": "dirt"},
    "dirt": {"color": [126, 105, 89], "drop": "dirt"},
    "stone": {"color": [153, 151, 148], "drop": "cobblestone", "requires": "wooden_pickaxe"},
    "cobblestone": {"color": [130, 137, 137], "drop": "cobblestone"},
    "bedrock": {"color": [67, 72, 75], "drop": None},
    "sand": {"color": [222, 203, 158], "drop": "sand", "gravity": True},
    "gravel": {"color": [159, 166, 162], "drop": "gravel", "gravity": True},
    "clay": {"color": [166, 190, 192], "drop": "clay"},
    "brick": {"color": [184, 105, 86], "drop": "brick"},
    "basalt": {"color": [75, 83, 86], "drop": "basalt"},
    "oak_log": {"color": [139, 105, 82], "drop": "oak_log"},
    "planks": {"color": [202, 171, 125], "drop": "planks"},
    "leaves": {"color": [101, 164, 128], "drop": None},
    "coal_ore": {"color": [88, 94, 97], "drop": "coal", "requires": "wooden_pickaxe"},
    "iron_ore": {"color": [182, 138, 107], "drop": "iron_ore", "requires": "stone_pickaxe"},
    "copper_ore": {"color": [170, 116, 91], "drop": "copper_ore", "requires": "stone_pickaxe"},
    "glass": {"color": [160, 218, 218], "drop": "glass", "opacity": 0.38},
    "water": {"color": [103, 179, 203], "drop": None, "opacity": 0.58, "fluid": True},
    "lava": {"color": [244, 117, 57], "drop": None, "opacity": 0.85, "fluid": True, "glow": True},
    "wool": {"color": [238, 226, 204], "drop": "wool"},
    "moss": {"color": [85, 139, 100], "drop": "moss"},
    "lantern": {"color": [247, 213, 143], "drop": "lantern", "glow": True},
    "crafting_table": {"color": [169, 117, 72], "drop": "crafting_table"},
    "furnace": {"color": [88, 91, 89], "drop": "furnace", "glow": True},
}

RECIPES = {
    "planks": {"ingredients": {"oak_log": 1}, "output": {"planks": 4}},
    "sticks": {"ingredients": {"planks": 2}, "output": {"sticks": 4}},
    "crafting_table": {"ingredients": {"planks": 4}, "output": {"crafting_table": 1}},
    "furnace": {"ingredients": {"cobblestone": 8}, "output": {"furnace": 1}, "station": "crafting_table"},
    "wooden_pickaxe": {"ingredients": {"planks": 3, "sticks": 2}, "output": {"wooden_pickaxe": 1}, "station": "crafting_table"},
    "stone_pickaxe": {"ingredients": {"cobblestone": 3, "sticks": 2}, "output": {"stone_pickaxe": 1}, "station": "crafting_table"},
    "iron_pickaxe": {"ingredients": {"iron_ingot": 3, "sticks": 2}, "output": {"iron_pickaxe": 1}, "station": "crafting_table"},
}

TOOL_RANK = {"wooden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3}
SMELTING = {"iron_ore": "iron_ingot", "copper_ore": "copper_ingot", "sand": "glass", "clay": "brick"}


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
