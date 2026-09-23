"""Server-side egg roll, ported from the viewer's frontend/src/components/hatch/eggAttributes.ts.

Eggs keep the viewer's EggProfile shape (attributes, name, totalPoints, rarity) so EggScene can
draw the egg the server rolled. Traits come from the egg: rarer eggs raise every trait's floor.
"""

from __future__ import annotations

import random

TIER_PROBABILITIES = (("common", 40), ("uncommon", 25), ("rare", 20), ("legendary", 14), ("mythic", 1))
TIER_POINTS = {"common": 0.0, "uncommon": 0.5, "rare": 1.0, "legendary": 1.5, "mythic": 2.0}
# (name, tier, shader value) per category, in the viewer's order.
ATTRIBUTE_POOLS = (
    ("shape", (("Round", "common", 0), ("Oval", "common", 1), ("Squat", "uncommon", 2),
               ("Elongated", "uncommon", 3), ("Teardrop", "rare", 4), ("Bulbous", "rare", 5),
               ("Gourd", "legendary", 6), ("Spire", "mythic", 7))),
    ("scales", (("Smooth", "common", 0), ("Stippled", "common", 1), ("Hexscale", "uncommon", 2),
                ("Diamond", "uncommon", 3), ("Spiral", "rare", 4), ("Cracked", "rare", 5),
                ("Runic", "legendary", 6), ("Prismatic", "mythic", 7))),
    ("color", (("Stone", "common", 0), ("Moss", "common", 1), ("Amber", "uncommon", 2),
               ("Cobalt", "uncommon", 3), ("Crimson", "rare", 4), ("Violet", "rare", 5),
               ("Obsidian", "legendary", 6), ("Iridescent", "mythic", 7))),
    ("size", (("Tiny", "common", 0), ("Small", "common", 1), ("Standard", "uncommon", 2),
              ("Large", "rare", 3), ("Massive", "legendary", 4), ("Colossal", "mythic", 5))),
    ("mist", (("None", "common", 0), ("Faint", "uncommon", 1), ("Wispy", "rare", 2),
              ("Radiant", "legendary", 3), ("Ethereal", "mythic", 4))),
)
TRAITS = ("curiosity", "creativity", "sociability", "patience", "bravery", "caution", "thrift", "diligence")
RARITY_FLOOR = {"common": 10, "uncommon": 20, "rare": 30, "legendary": 40, "mythic": 50}
# Each attribute nudges two traits, like the viewer's stat biases. Floors rise 10 per tier point.
TRAIT_BIASES = {
    "shape": ("bravery", "diligence"),
    "scales": ("patience", "caution"),
    "color": ("sociability", "creativity"),
    "size": ("bravery", "thrift"),
    "mist": ("curiosity", "creativity"),
}
BIAS_PER_POINT = 10
MAX_FLOOR = 90
NAMES = ("Pip", "Juniper", "Moss", "Tansy", "Bramble", "Fennel", "Clover", "Sorrel", "Wren", "Nettle",
         "Pebble", "Thistle", "Maple", "Hazel", "Quill", "Sprout", "Tuft", "Willow", "Yarrow", "Bean")


def roll_tier(rng: random.Random) -> str:
    roll = rng.random() * 100
    cumulative = 0
    for tier, probability in TIER_PROBABILITIES:
        cumulative += probability
        if roll < cumulative:
            return tier
    return "common"


def rarity_for(total_points: float) -> str:
    if total_points > 8:
        return "mythic"
    if total_points > 6:
        return "legendary"
    if total_points > 4:
        return "rare"
    if total_points > 2:
        return "uncommon"
    return "common"


def egg_name(attributes: list[dict]) -> str:
    """Size (unless Standard), color, scales and shape, as the viewer names eggs."""
    names = {attribute["category"]: attribute["option"]["name"] for attribute in attributes}
    parts = [] if names["size"] == "Standard" else [names["size"]]
    return " ".join([*parts, names["color"], names["scales"], names["shape"]])


def roll_egg(rng: random.Random) -> dict:
    attributes = []
    for category, options in ATTRIBUTE_POOLS:
        tier = roll_tier(rng)
        name, _, value = rng.choice([option for option in options if option[1] == tier])
        attributes.append({"category": category, "option": {"name": name, "tier": tier, "value": value},
                           "points": TIER_POINTS[tier]})
    total = sum(attribute["points"] for attribute in attributes)
    return {"attributes": attributes, "name": egg_name(attributes), "totalPoints": total, "rarity": rarity_for(total)}


def trait_floors(egg: dict) -> dict[str, int]:
    floors = {trait: RARITY_FLOOR[egg["rarity"]] for trait in TRAITS}
    for attribute in egg["attributes"]:
        for trait in TRAIT_BIASES[attribute["category"]]:
            floors[trait] += round(attribute["points"] * BIAS_PER_POINT)
    return {trait: min(MAX_FLOOR, floor) for trait, floor in floors.items()}


def roll_traits(egg: dict, rng: random.Random) -> dict[str, int]:
    return {trait: rng.randint(floor, 100) for trait, floor in trait_floors(egg).items()}


def pick_name(rng: random.Random, taken: set[str] | frozenset[str] = frozenset()) -> str:
    """A name no earlier life used, until every name has been used once."""
    fresh = [name for name in NAMES if name not in taken]
    return rng.choice(fresh or list(NAMES))
