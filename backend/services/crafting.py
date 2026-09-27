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
    "door": {"ingredients": {"planks": 6}, "output": {"door": 1}},
    "wooden_axe": {"ingredients": {"planks": 3, "sticks": 2}, "output": {"wooden_axe": 1}, "station": "crafting_table"},
    "stone_axe": {"ingredients": {"cobblestone": 3, "sticks": 2}, "output": {"stone_axe": 1}, "station": "crafting_table"},
    "iron_axe": {"ingredients": {"iron_ingot": 3, "sticks": 2}, "output": {"iron_axe": 1}, "station": "crafting_table"},
    "wooden_sword": {"ingredients": {"planks": 2, "sticks": 1}, "output": {"wooden_sword": 1}, "station": "crafting_table"},
    "stone_sword": {"ingredients": {"cobblestone": 2, "sticks": 1}, "output": {"stone_sword": 1}, "station": "crafting_table"},
    "iron_sword": {"ingredients": {"iron_ingot": 2, "sticks": 1}, "output": {"iron_sword": 1}, "station": "crafting_table"},
    "bow": {"ingredients": {"sticks": 3, "string": 3}, "output": {"bow": 1}, "station": "crafting_table"},
    "arrow": {"ingredients": {"flint": 1, "sticks": 1, "feather": 1}, "output": {"arrow": 4}, "station": "crafting_table"},
    "leather": {"ingredients": {"rabbit_hide": 4}, "output": {"leather": 1}},
    "leather_cap": {"ingredients": {"leather": 2}, "output": {"leather_cap": 1}, "station": "crafting_table"},
    "leather_tunic": {"ingredients": {"leather": 3}, "output": {"leather_tunic": 1}, "station": "crafting_table"},
}

# L3, the bigger world: birch and spruce make planks of their own, cobblestone makes stone bricks.
RECIPES.update({
    "birch_planks": {"ingredients": {"birch_log": 1}, "output": {"birch_planks": 4}},
    "spruce_planks": {"ingredients": {"spruce_log": 1}, "output": {"spruce_planks": 4}},
    "stone_bricks": {"ingredients": {"cobblestone": 4}, "output": {"stone_bricks": 4}},
    # Gold and diamond tiers, at a crafting table like iron's.
    "gold_pickaxe": {"ingredients": {"gold_ingot": 3, "sticks": 2}, "output": {"gold_pickaxe": 1}, "station": "crafting_table"},
    "diamond_pickaxe": {"ingredients": {"diamond": 3, "sticks": 2}, "output": {"diamond_pickaxe": 1}, "station": "crafting_table"},
    "gold_sword": {"ingredients": {"gold_ingot": 2, "sticks": 1}, "output": {"gold_sword": 1}, "station": "crafting_table"},
    "diamond_sword": {"ingredients": {"diamond": 2, "sticks": 1}, "output": {"diamond_sword": 1}, "station": "crafting_table"},
    # Iron armor at a crafting table; a lantern (L2's light 15) from an iron ingot and a torch, anywhere.
    "iron_cap": {"ingredients": {"iron_ingot": 5}, "output": {"iron_cap": 1}, "station": "crafting_table"},
    "iron_tunic": {"ingredients": {"iron_ingot": 8}, "output": {"iron_tunic": 1}, "station": "crafting_table"},
    "lantern": {"ingredients": {"iron_ingot": 1, "torch": 1}, "output": {"lantern": 1}},
    # Ladders Mimo can climb and fences nothing can cross, anywhere.
    "ladder": {"ingredients": {"sticks": 7}, "output": {"ladder": 3}},
    "fence": {"ingredients": {"planks": 4, "sticks": 2}, "output": {"fence": 3}},
})
# L5, the frontier: gold nuggets that far-off hostiles and ruins give, 4 to a gold ingot, anywhere.
RECIPES.update({
    "gold_nuggets": {"ingredients": {"gold_nugget": 4}, "output": {"gold_ingot": 1}},
})
# Making (T1): paper and books, dyes and coloured wool, rugs, bookshelves, a kiln, stairs, slabs, glass panes,
# trapdoors, iron bars, flower pots, signs, barrels, composters and candles.
RECIPES.update({
    "paper": {"ingredients": {"sugar_cane": 3}, "output": {"paper": 3}, "station": "crafting_table"},
    "book": {"ingredients": {"paper": 3, "leather": 1}, "output": {"book": 1}},
    "dye_orange": {"ingredients": {"flower_orange": 1}, "output": {"dye_orange": 2}},
    "dye_pink": {"ingredients": {"flower_pink": 1}, "output": {"dye_pink": 2}},
    "dye_yellow": {"ingredients": {"flower_yellow": 1}, "output": {"dye_yellow": 2}},
    "wool_orange": {"ingredients": {"wool": 1, "dye_orange": 1}, "output": {"wool_orange": 1}},
    "wool_pink": {"ingredients": {"wool": 1, "dye_pink": 1}, "output": {"wool_pink": 1}},
    "wool_yellow": {"ingredients": {"wool": 1, "dye_yellow": 1}, "output": {"wool_yellow": 1}},
    "rug_orange": {"ingredients": {"wool_orange": 2}, "output": {"rug_orange": 3}},
    "rug_pink": {"ingredients": {"wool_pink": 2}, "output": {"rug_pink": 3}},
    "rug_yellow": {"ingredients": {"wool_yellow": 2}, "output": {"rug_yellow": 3}},
    "bookshelf": {"ingredients": {"planks": 6, "book": 1}, "output": {"bookshelf": 1}, "station": "crafting_table"},
    "kiln": {"ingredients": {"brick": 3, "cobblestone": 5}, "output": {"kiln": 1}, "station": "crafting_table"},
    "stairs": {"ingredients": {"planks": 6}, "output": {"stairs": 4}, "station": "crafting_table"},
    "slab": {"ingredients": {"planks": 3}, "output": {"slab": 6}, "station": "crafting_table"},
    "glass_pane": {"ingredients": {"glass": 6}, "output": {"glass_pane": 16}, "station": "crafting_table"},
    "trapdoor": {"ingredients": {"planks": 6}, "output": {"trapdoor": 2}, "station": "crafting_table"},
    "iron_bars": {"ingredients": {"iron_ingot": 6}, "output": {"iron_bars": 16}, "station": "crafting_table"},
    "flower_pot": {"ingredients": {"brick": 3}, "output": {"flower_pot": 1}},
    "sign": {"ingredients": {"planks": 6, "sticks": 1}, "output": {"sign": 3}, "station": "crafting_table"},
    "barrel": {"ingredients": {"planks": 6, "slab": 2}, "output": {"barrel": 1}, "station": "crafting_table"},
    "composter": {"ingredients": {"slab": 7}, "output": {"composter": 1}},
    "candle": {"ingredients": {"tallow": 1, "sticks": 1}, "output": {"candle": 1}},  # final fix wave: no string
})
# Making (T2): the parts of a machine. A copper ingot draws into twelve wires; the gates take torches for
# their sparks, as redstone torches would.
RECIPES.update({
    "copper_wire": {"ingredients": {"copper_ingot": 1}, "output": {"copper_wire": 12}, "station": "crafting_table"},
    "lever": {"ingredients": {"sticks": 1, "cobblestone": 1}, "output": {"lever": 1}},
    "button": {"ingredients": {"planks": 1}, "output": {"button": 1}},
    "pressure_plate": {"ingredients": {"planks": 2}, "output": {"pressure_plate": 1}},
    "daylight_sensor": {"ingredients": {"glass": 3, "slab": 3, "copper_wire": 1}, "output": {"daylight_sensor": 1},
                        "station": "crafting_table"},
    "repeater": {"ingredients": {"cobblestone": 3, "torch": 2, "copper_wire": 1}, "output": {"repeater": 1},
                 "station": "crafting_table"},
    "inverter": {"ingredients": {"torch": 1, "copper_wire": 1}, "output": {"inverter": 1}},
    "joiner": {"ingredients": {"cobblestone": 3, "torch": 1, "copper_wire": 2}, "output": {"joiner": 1},
               "station": "crafting_table"},
    "lamp": {"ingredients": {"copper_ingot": 1, "torch": 1}, "output": {"lamp": 1}, "station": "crafting_table"},
    "bell": {"ingredients": {"copper_ingot": 2, "sticks": 1}, "output": {"bell": 1}, "station": "crafting_table"},
})
# Any wood does where a recipe asks for oak (L3): birch and spruce logs stand in for an oak log, and
# their planks for plain planks. A recipe takes the item it names first, then its stand-ins in order.
LOGS = ("oak_log", "birch_log", "spruce_log")
PLANKS = ("planks", "birch_planks", "spruce_planks")
PLANKS_OF = dict(zip(LOGS, PLANKS))  # the planks each log makes, which is also that recipe's name
STAND_INS = {"oak_log": LOGS[1:], "planks": PLANKS[1:]}

TOOL_RANK = {"wooden_pickaxe": 1, "stone_pickaxe": 2, "iron_pickaxe": 3, "gold_pickaxe": 4, "diamond_pickaxe": 5}
SMELTING = {"iron_ore": "iron_ingot", "gold_ore": "gold_ingot", "copper_ore": "copper_ingot", "sand": "glass", "clay": "brick",
            "raw_fish": "cooked_fish", "raw_beef": "cooked_beef", "raw_mutton": "cooked_mutton",
            "raw_chicken": "cooked_chicken", "raw_rabbit": "cooked_rabbit"}
# Food cooks at a lit campfire or a furnace and burns no fuel: the fire is already lit.
COOKING = frozenset({"raw_fish", "raw_beef", "raw_mutton", "raw_chicken", "raw_rabbit"})
# Making: a kiln fires clay into bricks and sand into glass and burns no fuel (a furnace still does both,
# with fuel).
KILN_FIRED = frozenset({"clay", "sand"})
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


def have(inventory: dict[str, int], item: str) -> int:
    """How many of `item` a recipe can use: the item itself and what stands in for it."""
    return sum(inventory.get(name, 0) for name in (item, *STAND_INS.get(item, ())))


def paid(inventory: dict[str, int], ingredients: dict[str, int]) -> dict[str, int]:
    """The items `ingredients` take out of `inventory`: each ingredient itself first, then its
    stand-ins in order. What cannot be paid stays under the ingredient's own name, so take_items
    reports it missing."""
    bill: dict[str, int] = {}
    for item, amount in ingredients.items():
        for name in (item, *STAND_INS.get(item, ())):
            take = min(amount, inventory.get(name, 0) - bill.get(name, 0))
            if take > 0:
                bill[name] = bill.get(name, 0) + take
                amount -= take
        if amount > 0:
            bill[item] = bill.get(item, 0) + amount
    return bill


def planks_recipe(inventory: dict[str, int]) -> str:
    """The recipe that turns a carried log into planks of its wood, oak first ("planks" with none)."""
    return PLANKS_OF[next((log for log in LOGS if inventory.get(log, 0) > 0), "oak_log")]


def fuel_of(inventory: dict[str, int]) -> str:
    """What a furnace burns: coal, else the first planks carried ("planks" when there are none)."""
    if inventory.get("coal", 0):
        return "coal"
    return next((planks for planks in PLANKS if inventory.get(planks, 0) > 0), "planks")


def craft(inventory: dict[str, int], recipe_name: str, nearby_stations: set[str]) -> dict[str, int]:
    recipe = RECIPES.get(recipe_name)
    if not recipe:
        raise ValueError("Unknown recipe")
    if recipe.get("station") and recipe["station"] not in nearby_stations:
        raise ValueError(f"A placed {recipe['station']} is required")
    result = take_items(inventory, paid(inventory, recipe["ingredients"]))
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
    elif input_item in KILN_FIRED and "kiln" in nearby_stations:
        result = take_items(inventory, {input_item: 1})
    else:
        if "furnace" not in nearby_stations:
            raise ValueError("A placed furnace is required")
        fuel = fuel_of(inventory)
        result = take_items(inventory, {input_item: 1, fuel: 1})
    add_item(result, output)
    return result


def can_harvest(material: str, inventory: dict[str, int]) -> bool:
    required = BLOCKS.get(material, {}).get("requires")
    if not required:
        return True
    return max((TOOL_RANK.get(item, 0) for item in inventory if inventory[item] > 0), default=0) >= TOOL_RANK[required]
