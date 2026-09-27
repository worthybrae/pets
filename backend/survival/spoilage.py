"""W1: food that spoils ("Hazards" 3 of the Wild World spec), for a wild pet only.

Perishable food ages: PERISHABLE gives its shelf life in Mimo's arms, in game days (raw meat and fish 1.5;
berries, nightberries and brown mushrooms 2; cooked meat and fish 4; apples and carrots 5; bread 6). In a
chest it ages half as fast. Sunleaf, seeds and wheat never spoil (nor does anything not listed).

Each perishable item keeps at most LOTS lots, [count, wear], with wear from 0 to 1 (the share of its shelf
life used): `state["lots"]` for Mimo's arms, and `state["chest_lots"]` ({chest key: {item: lots}}) beside the
contents in `state["chests"]` (a key inside a chest's own dict would read as an item there). Food added within
a game minute of the newest lot (its wear no more than a minute's) joins it; a fourth lot merges into the
oldest. Eating, dropping, crafting and cooking take the most worn food first, and so do storing and taking,
which carry their lots across (`observe_lots`, after each finished step: steps.OBSERVERS). The lots of an item
always add up to its count: `settle_lots`, after each vitals step and each finished step, repairs any gap
toward the count (new food is fresh, food gone takes the most worn first), so a path that moves food without
a step (the owner's help, what a full pair of arms leaves behind) never leaves them out of step.

The tick ages Mimo's lots every vitals step and its chests' once a game minute (`age`). A lot that reaches
wear 1 becomes that many `spoiled_food` ("Pip's raw beef went bad.", a "spoiled" event), in its arms or its
chest; SPOILS then hears of it (backend.survival.knocks). Spoiled food fills 4 hunger and gives a tummy ache 6
times in 10 (backend.survival.meals). A pet that knows `wild:keeping` throws it out, cooks raw food before it
turns (cook scores 20 more while raw food it carries is past half its shelf life) and puts spare food in its
chest; one that does not eats spoiled food when hungry with nothing else, and keeps its spare food on it.

A gentle pet never has a lot: every function here leaves a gentle pet's state alone. A crash is logged once
and changes nothing.
"""

from __future__ import annotations

import logging

from backend.survival.clock import DAY_SECONDS
from backend.survival.once import log_once
from backend.survival.steps import OBSERVERS, label
from backend.survival.wild import is_wild

logger = logging.getLogger(__name__)

SPOILED = "spoiled_food"
PERISHABLE = {"raw_beef": 1.5, "raw_mutton": 1.5, "raw_chicken": 1.5, "raw_rabbit": 1.5, "raw_fish": 1.5,
              "berries": 2.0, "nightberries": 2.0, "brown_mushroom": 2.0,
              "cooked_beef": 4.0, "cooked_mutton": 4.0, "cooked_chicken": 4.0, "cooked_rabbit": 4.0, "cooked_fish": 4.0,
              "apple": 5.0, "carrot": 5.0, "bread": 6.0}
LOTS = 3
CHEST_RATE = 0.5  # food in a chest ages half as fast
JOIN = 60.0  # game seconds: food added within a game minute of the newest lot joins it
CHEST_EVERY = 60.0  # game seconds between two agings of the chests
TURNING = 0.5  # wear past which keeping cooks raw food first
# W1: functions (state, context, item, count, where, at) run when food spoils (backend.survival.knocks);
# `where` is "arms" or "chest". One that crashes is logged once.
SPOILS: list = []


def arms_lots(state: dict) -> dict:
    return state.setdefault("lots", {})


def chest_lots(state: dict, key: str) -> dict:
    return state.setdefault("chest_lots", {}).setdefault(key, {})


def total(lots: list) -> int:
    return sum(count for count, _ in lots)


def most_worn_first(lots: list) -> list:
    return sorted(lots, key=lambda lot: -lot[1])


def add(lots: list, count: int, wear: float, item: str) -> list:
    """`count` food of wear `wear` added to `lots`: joining the newest lot when it is no older than a game
    minute, else a lot of its own; past LOTS lots the newcomer merges into the oldest."""
    if count <= 0:
        return lots
    newest = min(lots, key=lambda lot: lot[1], default=None)
    fresh_enough = JOIN / (PERISHABLE[item] * DAY_SECONDS)
    if newest is not None and abs(newest[1] - wear) <= fresh_enough:
        newest[0] += count
        return lots
    if len(lots) >= LOTS:
        oldest = max(lots, key=lambda lot: lot[1])
        oldest[0] += count
        return lots
    return [*lots, [count, wear]]


def take(lots: list, count: int) -> tuple[list, list]:
    """Take `count` food from `lots`, the most worn first: (what is left, what was taken, as lots)."""
    left, taken = [], []
    for lot_count, wear in most_worn_first(lots):
        moved = min(count, lot_count)
        if moved:
            taken.append([moved, wear])
            count -= moved
        if lot_count - moved:
            left.append([lot_count - moved, wear])
    return left, taken


def settle(lots_of: dict, items: dict) -> bool:
    """Bring the lots of every perishable item in `items` in step with its count (fresh food for more, the
    most worn gone for less), and drop the lots of food no longer there. True when a lot changed."""
    changed = False
    for item in list(lots_of):
        if item not in PERISHABLE or items.get(item, 0) <= 0:
            del lots_of[item]
            changed = True
    for item, count in items.items():
        if item not in PERISHABLE or count <= 0:
            continue
        lots = lots_of.get(item, [])
        have = total(lots)
        if have < count:
            lots_of[item] = add([list(lot) for lot in lots], count - have, 0.0, item)
            changed = True
        elif have > count:
            lots_of[item] = take(lots, have - count)[0]
            changed = True
    return changed


def settle_lots(state: dict) -> None:
    """Every lot of a wild pet in step with the food it carries and its chests hold."""
    if not is_wild(state):
        return
    settle(arms_lots(state), state.get("inventory", {}))
    chests = state.get("chests", {})
    kept = state.setdefault("chest_lots", {})
    for key in list(kept):
        if key not in chests:
            del kept[key]
    for key, items in chests.items():
        if any(item in PERISHABLE for item in items) or key in kept:
            settle(chest_lots(state, key), items)
            if not kept.get(key):
                kept.pop(key, None)


def observe_lots(state: dict, step: dict, context, at: float) -> None:
    """steps.OBSERVERS: a store or take step carries its food's lots across, the most worn first; then every
    lot is settled. A crash is logged once."""
    if not is_wild(state):
        return
    try:
        item = step.get("item")
        if (step["kind"] in ("store", "take") and item in PERISHABLE and isinstance(step.get("target"), dict)
                and not step.get("away")):  # food taken out and left behind at once needs no lots
            target = step["target"]
            key = f"{target['x']},{target['y']},{target['z']}"
            arms, chest = arms_lots(state), chest_lots(state, key)
            carried = state["inventory"].get(item, 0)
            if step["kind"] == "store":
                moved = total(arms.get(item, [])) - carried
                source, sink = arms, chest
            else:
                moved = total(chest.get(item, [])) - state.get("chests", {}).get(key, {}).get(item, 0)
                source, sink = chest, arms
            if moved > 0:
                left, taken = take(source.get(item, []), moved)
                source[item] = left
                lots = [list(lot) for lot in sink.get(item, [])]
                for count, wear in taken:
                    lots = add(lots, count, wear, item)
                sink[item] = lots
        settle_lots(state)
    except Exception as error:
        log_once(logger, "lots", error)


OBSERVERS.append(observe_lots)


def spoil(lots_of: dict, items: dict, rate: float, seconds: float) -> dict[str, int]:
    """Age every lot by `seconds` game seconds at `rate`; each lot that reaches wear 1 turns into spoiled food
    in `items`. Returns {item: count spoiled}."""
    spoiled: dict[str, int] = {}
    for item in list(lots_of):
        shelf = PERISHABLE.get(item)
        if shelf is None:
            continue
        kept = []
        for count, wear in lots_of[item]:
            wear = wear + rate * seconds / (shelf * DAY_SECONDS)
            if wear >= 1.0:
                spoiled[item] = spoiled.get(item, 0) + count
            else:
                kept.append([count, round(wear, 6)])
        lots_of[item] = kept
        if spoiled.get(item):
            items[item] = items.get(item, 0) - spoiled[item]
            if items[item] <= 0:
                items.pop(item, None)
            items[SPOILED] = items.get(SPOILED, 0) + spoiled[item]
        if not kept:
            del lots_of[item]
    return spoiled


def went_bad(state: dict, context, spoiled: dict[str, int], where: str, at: float) -> None:
    name = state["name"]
    for item, count in spoiled.items():
        context.events.append((at, "spoiled", f"{name}'s {label(item)} went bad."))
        state["last_thought"] = f"Yuck, my {label(item)} went bad."
        for hears in SPOILS:
            try:
                hears(state, context, item, count, where, at)
            except Exception as error:
                log_once(logger, "spoils", error)


def age(state: dict, context, seconds: float, at: float) -> None:
    """After a vitals step of `seconds` game seconds: a wild pet's lots age, its chests' once a game minute,
    and what reached the end of its shelf life spoils. A crash is logged once and changes nothing."""
    if not is_wild(state):
        return
    try:
        settle_lots(state)
        went_bad(state, context, spoil(arms_lots(state), state["inventory"], 1.0, seconds), "arms", at)
        clock = state.setdefault("wild", {})
        waited = clock.get("chests_aged", 0.0) + seconds
        if waited >= CHEST_EVERY:
            for key, lots_of in list(state.get("chest_lots", {}).items()):
                chest = state.get("chests", {}).get(key)
                if chest is not None:
                    went_bad(state, context, spoil(lots_of, chest, CHEST_RATE, waited), "chest", at)
            waited = 0.0
        clock["chests_aged"] = waited
    except Exception as error:
        log_once(logger, "spoilage", error)


def worn(state: dict, item: str) -> float:
    """How worn the most worn lot of `item` Mimo carries is (0 with none)."""
    return max((wear for _, wear in (state.get("lots") or {}).get(item, [])), default=0.0)


def turning(state: dict, items) -> bool:
    """Some raw food Mimo carries is past TURNING of its shelf life."""
    return any(worn(state, item) > TURNING for item in items)
