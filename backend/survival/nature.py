"""The living world's rules that M4 adds: what picking and harvesting give, what grows from a
seed and on what ground, crop stages, chance drops and fish stocks.

Chance comes from `roll`: a number in [0, 1) fixed by the world seed, a cell, a channel and a
salt (usually a time), so an outcome never depends on how often the tick ran and tests can patch
`roll` to force one.
"""

from __future__ import annotations

import math

from backend.services.worldgen import hash32
from backend.survival.clock import DAY_SECONDS
from backend.survival.grid import Cell

CROPS = ("wheat", "carrot")
RIPE_STAGE = 3
CROP_BLOCKS = tuple(f"{crop}_{stage}" for crop in CROPS for stage in range(RIPE_STAGE + 1))
RIPE_CROPS = tuple(f"{crop}_{RIPE_STAGE}" for crop in CROPS)
# What a planted item grows into, and the ground under it that it needs.
SEEDS = {"seeds": "wheat_0", "carrot": "carrot_0", "sapling": "sapling"}
SOIL = {"wheat_0": ("farmland",), "carrot_0": ("farmland",), "sapling": ("grass", "dirt", "moss")}
TILLABLE = ("grass", "dirt", "moss")
# pick(cell): what a wild plant gives and what the cell turns into.
PICKS = {"berry_bush_ripe": ({"berries": 3}, "berry_bush"),
         "brown_mushroom": ({"brown_mushroom": 1}, "air"),
         "red_mushroom": ({"red_mushroom": 1}, "air")}
MUSHROOMS = ("brown_mushroom", "red_mushroom")
# harvest(cell): what a ripe crop gives. The crop's cell turns to air; the farmland stays.
HARVESTS = {"wheat_3": {"wheat": 1, "seeds": 2}, "carrot_3": {"carrot": 3}}
# Extra drops when a block is mined, or a leaf decays: (item, chance, roll channel).
CHANCE_DROPS = {"tall_grass": (("seeds", 0.2, 30), ("carrot", 0.05, 31)),
                "leaves": (("sapling", 1 / 12, 32), ("apple", 1 / 20, 33)),
                "gravel": (("flint", 1 / 8, 38),)}  # L2: flint for arrows


# L3: birch and spruce leaves decay like oak's and drop saplings too, but no apples.
LEAVES = ("leaves", "birch_leaves", "spruce_leaves")
CHANCE_DROPS.update({leaf: (("sapling", 1 / 12, 32),) for leaf in LEAVES[1:]})


def roll(seed: str, cell: Cell, channel: int, salt: int = 0) -> float:
    """A number in [0, 1) fixed by the world seed, the cell, the channel and the salt."""
    x, y, z = cell
    return hash32(x, y, z + salt * 1_000_003, seed, channel) / 4294967296


def crop_stage(material: str) -> tuple[str, int] | None:
    """("wheat", 2) for wheat_2; None for anything that is not a crop."""
    name, _, stage = material.rpartition("_")
    if name in CROPS and stage.isdigit() and int(stage) <= RIPE_STAGE:
        return name, int(stage)
    return None


def next_stage(material: str) -> str | None:
    """The crop block one stage on (wheat_0 -> wheat_1), or None when ripe or not a crop."""
    stage = crop_stage(material)
    if stage is None or stage[1] >= RIPE_STAGE:
        return None
    return f"{stage[0]}_{stage[1] + 1}"


def chance_drops(seed: str, cell: Cell, block: str) -> list[str]:
    """The extra items a mined or decayed block drops at this cell."""
    return [item for item, chance, channel in CHANCE_DROPS.get(block, ()) if roll(seed, cell, channel) < chance]


# Fish ------------------------------------------------------------------------------------------
# state["fish"] = {"rx,rz": {"stock": n, "since": server time}} for 16x16 regions below a full
# stock. A region not listed is full. `since` is when the stock last grew (or first fell).

FISH_CATCH = 34
FISH_TIME = 35
FISH_SECONDS = (20.0, 60.0)
FULL_STOCK = 12
CATCH_CHANCE = 0.9  # with a full stock; the chance falls with the stock
REGION = 16


def region_of(cell: Cell) -> str:
    return f"{cell[0] // REGION},{cell[2] // REGION}"


def fish_stock(state: dict, cell: Cell) -> int:
    return state.get("fish", {}).get(region_of(cell), {"stock": FULL_STOCK})["stock"]


def fish_seconds(seed: str, cell: Cell, at: float) -> float:
    """How long one catch takes (game seconds): 20 to 60."""
    low, high = FISH_SECONDS
    return low + (high - low) * roll(seed, cell, FISH_TIME, int(at))


def catches(seed: str, cell: Cell, at: float, stock: int, bonus: float = 0.0) -> bool:
    """Whether a catch started at `at` lands a fish, with the region's stock as it is. `bonus` (the
    fish Mimo can see near the hook, backend.survival.creatures.fishing) adds to the chance while
    the region has any stock."""
    chance = CATCH_CHANCE * stock / FULL_STOCK + (bonus if stock > 0 else 0.0)
    return roll(seed, cell, FISH_CATCH, int(at)) < chance


def take_fish(state: dict, cell: Cell, at: float) -> None:
    entry = state.setdefault("fish", {}).setdefault(region_of(cell), {"stock": FULL_STOCK, "since": at})
    entry["stock"] = max(0, entry["stock"] - 1)


def recover_fish(state: dict, at: float, scale: float) -> None:
    """Every region gains one fish per game day until it is full again."""
    stocks = state.get("fish") or {}
    for key in list(stocks):
        entry = stocks[key]
        days = math.floor((at - entry["since"]) * scale / DAY_SECONDS)
        if days <= 0:
            continue
        entry["stock"] = min(FULL_STOCK, entry["stock"] + days)
        entry["since"] += days * DAY_SECONDS / scale
        if entry["stock"] >= FULL_STOCK:
            del stocks[key]
