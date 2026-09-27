"""make_gear: armor, a bow and arrows (spec L2, "Armor" and "Bow").

Gear is made from what animals and hostiles leave behind, at a crafting table Mimo places from
its arms and mines back afterwards, as craft_tools does: a leather cap (2 leather) and a leather
tunic (3 leather), worn by carrying them (backend.survival.creatures.harm: a blow costs 8 % and
12 % less), a bow (3 sticks and 3 string) and arrows (1 flint, 1 stick and 1 feather make 4).
Leather that runs short is made from rabbit hides, 4 to 1, on the way. The order: the missing
armor first (both pieces in one batch when the leather stretches that far), then the bow with a
first bundle of arrows, or the bow alone, then another bundle of arrows while Mimo carries a bow
and fewer than ARROWS_WANTED. Final fix wave: the bow waits until Mimo has had flint for its
arrows (it carries flint or arrows, or its chests hold flint): flint only comes from gravel, 1 in
8, and nothing gathers gravel on purpose before L3, so a bow made first stood unused. What the
gear takes (`GEAR_MATERIALS`) is kept on hand only while the gear it is for is still missing
(`materials_wanted`, backend.survival.storage). One batch per choice, and none while something it
makes would not fit in Mimo's arms (carrying.crafts_fit) or where no table can stand (inside its
shelter). Day work in the work band: 55 plus a tenth of caution, 10 more when a creature hurt
Mimo in the last game day.

Making wave 2, fix round 1 (the re-review's I1): what the gear, the iron armor and the pickaxe ladder take is
never lost in the chest (`gear_wanted`, storage.WANTED_ON_HAND). While a making goal makes room in Mimo's arms
it puts away what L4a keeps on hand (making.kept_for_making), and nothing took armor's leather and iron, the
arrows' flint and feathers or the ladder's gold back out: on the gate armor came 75 to 126 game days late, or
never, with 36 to 63 iron ore in the chests. Now, whatever the goal:
- armor's own keep is never room: the leather and hides its missing leather pieces take, and the iron its
  missing iron armor takes, stay on Mimo, and what the chests hold of them comes back out (storage.taken_back).
  Put away and taken back only once armor was the goal, armor still came 13 to 49 game days late on three of
  the gate's six seeds: iron is scarce, and the armor goal was set aside for want of it while its iron sat
  in the chest;
- what the bow, the arrows and the gold pickaxe take goes in the chest to make room, and comes back out once
  the chests and Mimo's arms hold enough to make one (the bow's string, the missing arrows' flint and feathers,
  a gold pickaxe's gold, work.ladder_ores), so make_gear or craft_tools makes it at once.
While armor is Mimo's goal, build_storage works toward it when it takes armor's leather, hides or iron back out
(storage.TOWARD). Never more of an item than storage.KEEP holds on Mimo, so what comes out is not put straight
back.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.crafting import RECIPES, TOOL_RANK
from backend.survival import storage
from backend.survival.carrying import crafts_fit
from backend.survival.creatures.harm import IRON_ARMOR, armor_iron, covered, worn
from backend.survival.clock import DAY_SECONDS
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import STATION_REACH, WORKSTATIONS
from backend.survival.toolmaking import Short, make, place_station, station_spots
from backend.survival.work import ladder_ores, pickaxe_rank

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

ARMOR_PIECES = ("leather_tunic", "leather_cap")
ARROWS_WANTED = 8
WORDS = {"leather_tunic": "a leather tunic", "leather_cap": "a leather cap", "bow": "a bow", "arrow": "4 arrows"}
GEAR_MATERIALS = ("leather", "rabbit_hide", "string", "flint", "feather")  # what nothing but gear takes


def gear_orders(inventory: dict, flint_seen: bool = False) -> list[tuple[str, ...]]:
    """What make_gear may make, first choice first (see the module docstring). `flint_seen`: Mimo's
    chests hold flint (carried flint or arrows count without it)."""
    orders: list[tuple[str, ...]] = []
    armor = tuple(piece for piece in ARMOR_PIECES if not covered(inventory, piece))  # L3: iron covers a slot too
    if armor:
        orders.append(armor)
        if len(armor) > 1:
            orders += [(piece,) for piece in armor]
    if inventory.get("bow", 0) < 1:
        if flint_seen or inventory.get("flint", 0) > 0 or inventory.get("arrow", 0) > 0:
            orders += [("bow", "arrow"), ("bow",)]
    elif inventory.get("arrow", 0) < ARROWS_WANTED:
        orders.append(("arrow",))
    return orders


def materials_wanted(inventory: dict) -> set[str]:
    """The GEAR_MATERIALS still wanted for gear Mimo lacks: leather and hides for missing armor,
    string for a missing bow, flint and feathers while arrows are still wanted."""
    wanted = set()
    # L4a final fix wave, C1: a slot iron covers wants no leather (the leather piece is dropped as
    # junk once iron replaces it, so asking for the piece itself wanted leather and hides for good).
    if any(not covered(inventory, piece) for piece in ARMOR_PIECES):
        wanted |= {"leather", "rabbit_hide"}
    if inventory.get("bow", 0) < 1:
        wanted.add("string")
    if inventory.get("bow", 0) < 1 or inventory.get("arrow", 0) < ARROWS_WANTED:
        wanted |= {"flint", "feather"}
    return wanted


def flint_stored(s: Situation) -> bool:
    return any(chest.get("flint", 0) > 0 for chest in s.state.get("chests", {}).values())


def gear_steps(s: Situation, items: tuple[str, ...]) -> list[dict] | None:
    """The steps that make one of each of `items` (arrows come 4 at a time), with a crafting table
    placed and mined back when none stands within reach; None when they cannot all be made now."""
    inventory = dict(s.inventory)
    x, _, z = s.here
    steps: list[dict] = []
    placed = []
    try:
        if "crafting_table" not in s.grid.placed_near(x, z, STATION_REACH, WORKSTATIONS):
            make(inventory, "crafting_table", 1, steps)
            cell = place_station(station_spots(s), "crafting_table", steps)
            if cell is None:
                raise Short("crafting_table")
            inventory["crafting_table"] -= 1
            placed.append(cell)
        for item in items:
            make(inventory, item, inventory.get(item, 0) + 1, steps)
    except Short:
        return None
    steps.extend({"kind": "mine", "target": list(cell), "keep": True} for cell in reversed(placed))
    return steps if crafts_fit(s.inventory, steps) else None


def gear_choice(s: Situation) -> tuple[tuple[str, ...], list[dict]] | None:
    """The first of gear_orders that can be made now, with its steps; or None."""
    def look() -> tuple[tuple[str, ...], list[dict]] | None:
        for items in gear_orders(s.inventory, flint_stored(s)):
            steps = gear_steps(s, items)
            if steps is not None:
                return items, steps
        return None
    return s.sensed("gear_choice", look)


def hurt_lately(s: Situation) -> bool:
    hurt_at = s.state.get("hurt_at")
    return hurt_at is not None and (s.at - hurt_at) * s.scale < DAY_SECONDS


def gear_facts(s: Situation) -> str:
    items, _ = gear_choice(s)
    return f"can make {' and '.join(WORDS[item] for item in items)} now; carrying {s.count('arrow')} arrows"


def plan_gear(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] > 0:
        return []
    choice = gear_choice(s)
    return [] if choice is None else list(choice[1])


register(Purpose(
    "make_gear", "make gear",
    "Make armor, a bow or arrows from leather, string, flint and feathers with a portable crafting table.",
    valid=lambda s: not s.night and gear_choice(s) is not None,
    facts=gear_facts,
    score=lambda s: 55.0 + s.trait("caution") / 10 + (10.0 if hurt_lately(s) else 0.0),
    plan=plan_gear,
    thoughts=("A little armor would help at night.", "With a bow I could keep them at a distance.")))


# What comes back out of the chest (Making wave 2, fix round 1) -----------------------------------------------

ARMOR_GOAL = "armor_up"  # backend.survival.life_goals
ARMOR_ITEMS = ("leather", "rabbit_hide", "iron_ore", "iron_ingot")
HIDES_PER_LEATHER = RECIPES["leather"]["ingredients"]["rabbit_hide"]
GOLD_PICKAXE = RECIPES["gold_pickaxe"]["ingredients"]["gold_ingot"]


def either(have: dict[str, int], first: str, second: str, need: int, per: int = 1) -> dict[str, int]:
    """`need` of `first`, what `have` lacks of it made up with `second` (`per` of it for one)."""
    one = min(have.get(first, 0), need)
    return {first: one, second: min(have.get(second, 0), (need - one) * per)}


def gear_wanted(s: Situation) -> dict[str, int]:
    """storage.WANTED_ON_HAND: what Mimo wants on hand now for its armor, gear and next pickaxe, from what its
    arms and chests hold together (see the module docstring), each no more than storage.KEEP holds."""
    inventory, stored = s.inventory, storage.in_chests(s)
    have = {item: inventory.get(item, 0) + stored.get(item, 0)
            for item in ("leather", "rabbit_hide", "iron_ore", "iron_ingot", "gold_ore", "gold_ingot", "string",
                         "flint", "feather")}
    wanted: dict[str, int] = {}
    pieces = [piece for piece in ARMOR_PIECES if not covered(inventory, piece)]
    if pieces:
        leather = sum(RECIPES[piece]["ingredients"]["leather"] for piece in pieces)
        wanted.update(either(have, "leather", "rabbit_hide", leather, HIDES_PER_LEATHER))
    iron = any(not worn(inventory, piece) for piece in IRON_ARMOR)  # L5: an amber piece stands for its iron one
    if iron and pickaxe_rank(inventory) >= TOOL_RANK["iron_pickaxe"]:
        wanted.update(either(have, "iron_ingot", "iron_ore", armor_iron(inventory)))
    if ladder_ores(inventory) and have["gold_ore"] + have["gold_ingot"] >= GOLD_PICKAXE:
        wanted.update(either(have, "gold_ingot", "gold_ore", GOLD_PICKAXE))
    bow = inventory.get("bow", 0) > 0
    flint = have["flint"] > 0 or inventory.get("arrow", 0) > 0
    if not bow and flint and have["string"] >= RECIPES["bow"]["ingredients"]["string"]:
        wanted["string"] = RECIPES["bow"]["ingredients"]["string"]
        bow = True
    arrows = math.ceil(max(0, ARROWS_WANTED - inventory.get("arrow", 0)) / RECIPES["arrow"]["output"]["arrow"])
    if bow and arrows and have["flint"] > 0 and have["feather"] > 0:
        wanted.update({"flint": min(have["flint"], arrows), "feather": min(have["feather"], arrows)})
    return {item: min(count, storage.KEEP.get(item, count)) for item, count in wanted.items() if count > 0}


def armor_taken(s: Situation) -> bool:
    """storage.TOWARD: build_storage works toward armor while it takes armor's leather, hides or iron back out."""
    return any(item in ARMOR_ITEMS for _, item, _ in storage.to_take(s))


storage.WANTED_ON_HAND.append(gear_wanted)
storage.TOWARD[ARMOR_GOAL] = armor_taken
