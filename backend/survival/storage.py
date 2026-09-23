"""A lighter load: build_storage and drop_items (spec section 8, inventory limit).

Mimo carries at most 16 stacks (backend.survival.carrying). build_storage puts a chest in the
back corner the shelter design keeps for it, under the roof, making it from 8 planks when Mimo
carries none, and puts away what Mimo does not need to carry: loose blocks, materials beyond what
a day's work takes (KEEP), and food beyond a day's worth. It takes food back out when Mimo
carries less than a meal's worth. It is offered at the built shelter when Mimo's arms are getting
full (13 stacks) or the chest holds food Mimo needs, and scores higher the fuller Mimo is.

drop_items leaves behind what is no use at all: food Mimo knows is poisonous, pickaxes and axes a
better one replaced, and flowers. When its arms are full and there is no chest to use, the least
useful loose blocks (moss, gravel, sand, clay) go too. It scores low while Mimo has room and
high when it is full.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.crafting import TOOL_RANK
from backend.survival.building import current_shelter
from backend.survival.carrying import CARRY_STACKS, CHEST_STACKS, room_for, stacks
from backend.survival.cooking import made
from backend.survival.foraging import FOOD_WANTED, whole_walk
from backend.survival.housework import chest_key
from backend.survival.purposes import Purpose, foods, register
from backend.survival.situation import Situation
from backend.survival.steps import AXES, FOOD, REACH
from backend.survival.structures import blueprint_of

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

STORE_FROM = 13  # stacks from which putting things away is worth a trip home
DROP_FROM = 10
TAKE_BELOW = 20.0  # hunger points of food carried below which Mimo takes food out
STORE_STEPS = 8
# What Mimo keeps on it of each material; the rest goes into the chest. Items not listed (tools,
# stations, food up to a day's worth) stay with Mimo.
KEEP = {"cobblestone": 16, "planks": 16, "oak_log": 8, "sticks": 8, "coal": 8, "iron_ore": 3, "iron_ingot": 3,
        "seeds": 8, "sapling": 4, "wheat": 6, "torch": 4, "dirt": 0, "gravel": 0, "sand": 0, "clay": 0, "moss": 0,
        "basalt": 0, "limestone": 0, "sandstone": 0, "brick": 0, "glass": 0, "copper_ore": 0, "copper_ingot": 0}
FLOWERS = ("flower_orange", "flower_pink", "flower_yellow")
LEAST_USEFUL = ("moss", "gravel", "sand", "clay")


def chest_spot(s: Situation) -> tuple[int, int, int] | None:
    """The chest corner of the shelter Mimo built, or None before it has one."""
    structure = current_shelter(s)
    if structure is None or structure["status"] != "done":
        return None
    return blueprint_of(structure).one("chest")


def chest_placed(s: Situation, cell) -> bool:
    return cell is not None and s.grid.material(*cell) == "chest"


def chest_contents(s: Situation, cell) -> dict[str, int]:
    return dict(s.state.get("chests", {}).get(chest_key(cell), {})) if cell else {}


def spare_food(s: Situation) -> list[tuple[str, int]]:
    """Food beyond a day's worth (60 hunger), the least filling first."""
    kept, spare = 0.0, []
    for item in foods(s.inventory, s.poisons):
        count = s.inventory[item]
        keep = 0
        while keep < count and kept < FOOD_WANTED:
            keep += 1
            kept += FOOD[item]
        if count > keep:
            spare.append((item, count - keep))
    return list(reversed(spare))


def to_store(s: Situation, cell) -> list[tuple[str, int]]:
    """(item, amount) Mimo would put away, most first, as far as the chest has room."""
    chest = chest_contents(s, cell)
    wanted = [(item, count - KEEP[item]) for item, count in s.inventory.items()
              if item in KEEP and count > KEEP[item]] + spare_food(s)
    found = []
    for item, amount in sorted(wanted, key=lambda entry: (-entry[1], entry[0])):
        amount = min(amount, room_for(chest, item, CHEST_STACKS))
        if amount > 0:
            chest[item] = chest.get(item, 0) + amount
            found.append((item, amount))
    return found[:STORE_STEPS]


def carried_food(s: Situation) -> float:
    return sum(FOOD[item] * s.inventory[item] for item in foods(s.inventory, s.poisons))


def to_take(s: Situation, cell) -> list[tuple[str, int]]:
    """Food to take out of the chest when Mimo carries less than a meal's worth, best first."""
    if carried_food(s) >= TAKE_BELOW:
        return []
    chest, have, found = chest_contents(s, cell), carried_food(s), []
    for item in foods(chest, s.poisons):
        amount = 0
        while amount < chest[item] and have < FOOD_WANTED:
            amount += 1
            have += FOOD[item]
        if amount:
            found.append((item, amount))
    return found


def storage_valid(s: Situation) -> bool:
    cell = chest_spot(s)
    if cell is None or s.night:
        return False
    if not chest_placed(s, cell):
        can_have = s.count("chest") > 0 or made(dict(s.inventory), "chest") is not None
        return can_have and stacks(s.inventory) >= STORE_FROM
    return (stacks(s.inventory) >= STORE_FROM and bool(to_store(s, cell))) or bool(to_take(s, cell))


def storage_facts(s: Situation) -> str:
    cell = chest_spot(s)
    chest = chest_contents(s, cell)
    where = "a chest at home" if chest_placed(s, cell) else "no chest yet"
    return (f"carrying {stacks(s.inventory)} of {CARRY_STACKS} stacks; {where} holding {stacks(chest)} of "
            f"{CHEST_STACKS} stacks")


def storage_score(s: Situation) -> float:
    cell = chest_spot(s)
    if chest_placed(s, cell) and to_take(s, cell) and stacks(s.inventory) < STORE_FROM:
        return 55.0
    return 50.0 + 5.0 * max(0, stacks(s.inventory) - STORE_FROM) + (5.0 if s.state.get("full_at") else 0.0)


def plan_storage(s: Situation, context: ActionContext) -> list[dict]:
    """Walk home, make and place the chest if it is not there, put things away and take food out."""
    cell = chest_spot(s)
    if cell is None or s.brain["batches"] > 0:
        return []
    structure = current_shelter(s)
    home = blueprint_of(structure).anchor
    steps = [] if s.distance(cell) <= REACH and s.here in blueprint_of(structure).stands else [whole_walk(home)]
    if not chest_placed(s, cell):
        if s.count("chest") < 1:
            crafting = made(dict(s.inventory), "chest")
            if crafting is None:
                return []
            steps.extend(crafting)
        steps.append({"kind": "place", "target": list(cell), "block": "chest"})
    for kind, moves in (("store", to_store(s, cell)), ("take", to_take(s, cell))):
        steps.extend({"kind": kind, "target": list(cell), "item": item, "amount": amount} for item, amount in moves)
    return steps


register(Purpose(
    "build_storage", "put things away",
    "Put a chest in the shelter and store what it does not need to carry; take food back out when short.",
    valid=storage_valid, facts=storage_facts, score=storage_score, plan=plan_storage,
    thoughts=("My arms are getting full. Time to tidy up.", "A chest would keep all this safe.")))


def junk(s: Situation) -> list[tuple[str, int]]:
    """(item, amount) that is no use to carry: known poison, replaced tools, flowers; and, full with
    no chest to use, the least useful loose blocks."""
    found = [(item, s.inventory[item]) for item in s.poisons if s.inventory.get(item, 0) > 0]
    best = max((TOOL_RANK[tool] for tool in TOOL_RANK if s.count(tool)), default=0)
    found += [(tool, s.count(tool)) for tool, rank in TOOL_RANK.items() if s.count(tool) and rank < best]
    axes = [axe for axe in AXES if s.count(axe)]
    found += [(axe, s.count(axe)) for axe in axes[:-1]]
    found += [(flower, s.count(flower)) for flower in FLOWERS if s.count(flower)]
    if stacks(s.inventory) >= CARRY_STACKS and not chest_placed(s, chest_spot(s)):
        found += [(item, s.count(item)) for item in LEAST_USEFUL if s.count(item)]
    return found


def plan_drop(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return [{"kind": "drop", "item": item, "amount": amount} for item, amount in junk(s)]


register(Purpose(
    "drop_items", "drop what it cannot use",
    "Leave behind food it knows is poisonous, tools a better one replaced and other things of no use.",
    valid=lambda s: stacks(s.inventory) >= DROP_FROM and bool(junk(s)),
    facts=lambda s: f"carrying {stacks(s.inventory)} of {CARRY_STACKS} stacks; no use for "
                    + ", ".join(item.replace("_", " ") for item, _ in junk(s)),
    score=lambda s: 30.0 + 8.0 * max(0, stacks(s.inventory) - DROP_FROM),
    plan=plan_drop,
    thoughts=("I don't need all of this.", "Lighter is better.")))
