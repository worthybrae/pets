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
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival.carrying import crafts_fit
from backend.survival.creatures.harm import covered
from backend.survival.clock import DAY_SECONDS
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import STATION_REACH, WORKSTATIONS
from backend.survival.toolmaking import Short, make, place_station, station_spots

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
