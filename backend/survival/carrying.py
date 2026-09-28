"""How much Mimo can carry, and how much a chest holds (spec section 8).

Items come in stacks of up to 32 of one kind; a tool or station is a stack of its own. Mimo
carries at most 16 stacks and a chest holds 24. When a finished step brings in more than fits,
the part that does not fit stays behind (there are no dropped items to pick up later), the way
a full inventory in a block game leaves the new item on the ground. Only what the step brought
in is left, with one exception: something valuable (food, seeds, saplings, wheat, ore, ingots,
coal, tools and swords) pushes out the least valuable block Mimo carries instead (LOW_VALUE, moss first
and cobblestone last; never the rare clay), a stack at a time; anything else Mimo already carried is never lost. Being
full makes putting things away in a chest and dropping low-value items worth doing
(backend.survival.storage).

L4a final fix wave, C1: goals load Mimo with gear, ores, leather, feathers and hides, all of them
kept on hand, so its 16 stacks could fill with no LOW_VALUE block among them; every berry it picked
was then left behind and one pet starved 536 blocks from home. Food outranks more than blocks now:
with no LOW_VALUE block left, it pushes out a stack of what GIVES_WAY_TO_FOOD lists (unused plants,
then spare gear materials, then hides, then extra ores: all of it comes back with the next hunt or
dig), and food that still does not fit is eaten there and then while Mimo is hungry
(`eat_what_is_left`: from EAT_BELOW, up to FULL, as a meal eats, never food that can make it sick).
Food work is offered only while its food would be kept or eaten (foraging.room_for_food).

Crafting, smelting and cooking never make something that would be left behind: their steps do
not start when the output would not fit once the inputs are used up (`fits`, checked in
backend.survival.steps and backend.survival.fieldwork), and planners leave out crafts that could
not run (`crafts_fit`).
"""

from __future__ import annotations

import math

from backend.services.crafting import add_item, craft, smelt, take_items

STACK = 32
CARRY_STACKS = 16
CHEST_STACKS = 24
# Carried blocks worth least, the least first: a valuable newcomer that does not fit pushes one out. The Making
# final fix wave: never clay, which is rare (only on some shores) and what the workshop's kiln is fired from; on
# the gate's route check every clay a pet dug was pushed out by the next meat or ore it picked up. Clay no
# project wants is still a loose block drop_items leaves behind (storage.LEAST_USEFUL).
LOW_VALUE = ("moss", "gravel", "sand", "dirt", "basalt", "limestone", "sandstone", "cobblestone")
VALUABLE = ("seeds", "sapling", "wheat", "coal", "bow", "arrow", "leather_cap", "leather_tunic")  # L2: gear


def stacks(items: dict[str, int]) -> int:
    """How many stacks `items` fill."""
    return sum(math.ceil(count / STACK) for count in items.values() if count > 0)


def room_for(items: dict[str, int], item: str, limit: int) -> int:
    """How many more of `item` fit in `items` without going over `limit` stacks."""
    have = items.get(item, 0)
    in_last = (-have) % STACK if have > 0 else 0
    return in_last + max(0, limit - stacks(items)) * STACK


def full(items: dict[str, int]) -> bool:
    return stacks(items) >= CARRY_STACKS


def fits(before: dict[str, int], after: dict[str, int], limit: int = CARRY_STACKS) -> bool:
    """Whether what a change from `before` to `after` makes (a craft, a smelt, a cook) fits in
    `limit` stacks once what it used up is gone: room_for on a copy of `before` minus the inputs."""
    trial = {item: min(count, after.get(item, 0)) for item, count in before.items()}
    for item in sorted(after):
        grown = after[item] - before.get(item, 0)
        if grown > 0:
            if room_for(trial, item, limit) < grown:
                return False
            trial[item] = trial.get(item, 0) + grown
    return True


ANY_STATION = {"crafting_table", "furnace", "campfire"}


def crafts_fit(inventory: dict[str, int], steps: list[dict]) -> bool:
    """Whether every craft, smelt and cook in `steps`, run in order from `inventory`, has room for
    what it makes (the steps would fail to start otherwise). A place uses up its block, and a mine
    of a cell placed earlier in `steps` (a portable station's mine-back) needs room for it again.
    Stations and materials are the steps' own business: a step that could not run is skipped."""
    trial, placed = dict(inventory), {}
    for step in steps:
        kind = step.get("kind")
        target = tuple(step["target"]) if isinstance(step.get("target"), list) else None
        try:
            if kind == "craft":
                after = craft(trial, step["recipe"], ANY_STATION)
            elif kind in ("smelt", "cook"):
                after = smelt(trial, step["item"], ANY_STATION)
            elif kind == "place":
                trial = take_items(trial, {step["block"]: 1})
                placed[target] = step["block"]
                continue
            elif kind == "mine" and target in placed:
                after = dict(trial)
                add_item(after, placed.pop(target))
            else:
                continue
        except (KeyError, ValueError):
            continue
        if not fits(trial, after):
            return False
        trial = after
    return True


# L3: diamonds, creature seeds, iron armor and lanterns are worth carrying too.
TREASURES = ("diamond", "creature_seed", "iron_cap", "iron_tunic", "lantern")
TREASURES += ("amber", "gold_nugget")  # L5: the frontier's riches (backend.survival.loot)
# backend.survival.frontier_gear adds its warding lantern and amber-studded armor.


def valuable(item: str) -> bool:
    """Food that will not make Mimo sick, seeds, saplings, wheat, ore, ingots, coal, tools and swords: worth
    more than any LOW_VALUE block. Food that can make Mimo sick (steps.FOOD_HEALTH), like a red
    mushroom, is not: it is thrown away by drop_items as soon as Mimo learns it is poisonous, so it
    should never cost a good dirt or cobblestone stack in the meantime."""
    from backend.survival.steps import AXES, FOOD, FOOD_HEALTH, PICKAXE_SPEED  # imported here: steps imports this module
    return ((item in FOOD and FOOD_HEALTH.get(item, 0.0) >= 0) or item in VALUABLE or item in PICKAXE_SPEED
            or item in AXES or item in TREASURES or item.endswith(("_ore", "_ingot", "_sword")))


# L4a final fix wave, C1: what gives way to food once no LOW_VALUE block is left, the least useful
# first: plants nothing uses yet, spare gear materials, hides, then extra ores. The Making final fix wave:
# not copper any more, which the tinker bench and every machine are made of; on the gate's route check a pet
# that had just mined the bench's three copper lost them to the fish it caught next.
GIVES_WAY_TO_FOOD = ("flower_orange", "flower_pink", "flower_yellow", "cactus", "sugar_cane", "pumpkin", "melon",
                     "gloom_dust", "wool", "string", "feather", "flint", "rabbit_hide", "leather",
                     "gold_ore", "gold_ingot")


def good_food(item: str) -> bool:
    """Food that is not poisonous (steps.FOOD_HEALTH): worth carrying."""
    from backend.survival.steps import FOOD, FOOD_HEALTH  # imported here: steps imports this module
    return item in FOOD and FOOD_HEALTH.get(item, 0.0) >= 0


def keeps_alive(item: str) -> bool:
    """Good food that cannot make Mimo sick raw either (steps.FOOD_RISK): safe to eat on the spot."""
    from backend.survival.steps import FOOD_RISK  # imported here: steps imports this module
    return good_food(item) and item not in FOOD_RISK


def gives_way(inventory: dict[str, int], newcomer: str) -> list[str]:
    """What Mimo carries that gives way to `newcomer`, the first first: a LOW_VALUE block for anything
    valuable, then (C1) for good food, what GIVES_WAY_TO_FOOD lists."""
    if not valuable(newcomer):
        return []
    order = LOW_VALUE + (GIVES_WAY_TO_FOOD if good_food(newcomer) else ())
    return [item for item in order if inventory.get(item, 0) > 0]


def least_valuable(inventory: dict[str, int], newcomer: str) -> str | None:
    """What Mimo carries that gives way to a valuable `newcomer` first (`gives_way`), or None."""
    found = gives_way(inventory, newcomer)
    return found[0] if found else None


def settle(inventory: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    """Leave behind what a step brought in that Mimo cannot carry: while it carries more than
    CARRY_STACKS stacks, each item that grew goes back down (a stack at a time, never below what
    it was before the step), unless it is valuable and a LOW_VALUE block can go instead (its
    part-filled stack first). Push-out only relieves what this step's own growth needs: when
    `before` was already over CARRY_STACKS (an older save, say), that earlier overflow is left
    alone, so one berry never costs two stacks. Changes `inventory` in place and returns what was
    left behind."""
    left: dict[str, int] = {}
    floor = max(CARRY_STACKS, stacks(before))
    for item in sorted(item for item, count in inventory.items() if count > before.get(item, 0)):
        while stacks(inventory) > floor and inventory.get(item, 0) > before.get(item, 0):
            spare = least_valuable(inventory, item)
            gone = spare or item
            count = inventory[gone]
            drop = count % STACK or STACK
            if spare is None:
                drop = min(drop, count - before.get(item, 0))
            inventory[gone] = count - drop
            left[gone] = left.get(gone, 0) + drop
            if inventory[gone] == 0:
                del inventory[gone]
    return left


def eat_what_is_left(state: dict, left: dict[str, int], at: float, events: list | None) -> None:
    """C1: food a step brought in that did not fit is eaten there and then while Mimo is hungry
    (EAT_BELOW, the eat purpose's own line), best first, until it is FULL, as a meal eats; food that
    can make it sick is not. What is eaten comes off `left`."""
    from backend.survival.purposes import EAT_BELOW, FULL  # imported here: purposes imports steps, which imports this
    from backend.survival.steps import FOOD, label

    from backend.survival.meals import STARVING, eat_raw_left  # W1: a wild pet eats only what carries no risk
    from backend.survival.wild import SAFE, is_wild  # at all, unless it is starving

    vitals = state["vitals"]
    if vitals["hunger"] >= EAT_BELOW:
        return
    wild = is_wild(state)
    starving = vitals["hunger"] < STARVING
    # W1 fix round A: a wild pet judges leftover food by its own rules (good_food, the meal's SAFE and
    # starving), not the old gentle FOOD_RISK (keeps_alive), which lists only raw_chicken and so let a
    # starving wild pet's raw chicken sit uneaten while raw beef, mutton and rabbit were already eaten.
    for item in sorted((item for item in left
                        if (good_food(item) if wild else keeps_alive(item)) and (not wild or item in SAFE or starving)),
                       key=lambda item: (-FOOD[item], item)):
        eaten = 0
        while left[item] > 0 and vitals["hunger"] < FULL:
            vitals["hunger"] = min(100.0, vitals["hunger"] + FOOD[item])
            left[item] -= 1
            eaten += 1
        if not left[item]:
            del left[item]
        if eaten and events is not None:
            events.append((at, "ate", f"{state['name']} ate {eaten} {label(item)} it had no room to carry."))
        sick = eat_raw_left(state, item, at) if eaten and wild and item not in SAFE else None
        if sick and events is not None:
            events.append((at, *sick))


def after_step(state: dict, before: dict[str, int], at: float, events: list | None = None) -> None:
    """Settle the inventory after a finished step, eating food that did not fit while Mimo is hungry
    (`eat_what_is_left`, C1). `state["full_at"]` is the time Mimo last found its hands full
    (something had to stay behind), cleared once it carries less than the limit."""
    left = settle(state["inventory"], before)
    eat_what_is_left(state, left, at, events)
    if left and state.get("full_at") is None:
        state["full_at"] = at
        state["last_thought"] = "My arms are full. I can't carry any more."
    elif not full(state["inventory"]):
        state["full_at"] = None
