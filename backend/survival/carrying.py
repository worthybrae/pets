"""How much Mimo can carry, and how much a chest holds (spec section 8).

Items come in stacks of up to 32 of one kind; a tool or station is a stack of its own. Mimo
carries at most 16 stacks and a chest holds 24. When a finished step brings in more than fits,
the part that does not fit stays behind (there are no dropped items to pick up later), the way
a full inventory in a block game leaves the new item on the ground. Only what the step brought
in is left: what Mimo already carried is never lost. Being full makes putting things away in a
chest and dropping low-value items worth doing (backend.survival.storage).
"""

from __future__ import annotations

import math

STACK = 32
CARRY_STACKS = 16
CHEST_STACKS = 24


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


def settle(inventory: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    """Leave behind what a step brought in that Mimo cannot carry: while it carries more than
    CARRY_STACKS stacks, each item that grew goes back down (a stack at a time, never below what
    it was before the step). Changes `inventory` in place and returns what was left behind."""
    left: dict[str, int] = {}
    for item in sorted(item for item, count in inventory.items() if count > before.get(item, 0)):
        while stacks(inventory) > CARRY_STACKS and inventory.get(item, 0) > before.get(item, 0):
            count = inventory[item]
            drop = min(count % STACK or STACK, count - before.get(item, 0))
            inventory[item] = count - drop
            left[item] = left.get(item, 0) + drop
            if inventory[item] == 0:
                del inventory[item]
    return left


def after_step(state: dict, before: dict[str, int], at: float) -> None:
    """Settle the inventory after a finished step. `state["full_at"]` is the time Mimo last found
    its hands full (something had to stay behind), cleared once it carries less than the limit."""
    if settle(state["inventory"], before) and state.get("full_at") is None:
        state["full_at"] = at
        state["last_thought"] = "My arms are full. I can't carry any more."
    elif not full(state["inventory"]):
        state["full_at"] = None
