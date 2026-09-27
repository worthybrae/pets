"""Better loot farther out (L5, "Frontier"): hostile drops and mining luck grow with the ring.

- A hostile born in ring n (its state's "ring", backend.survival.creatures.ringed) drops more than its
  kind's own drops (combat.EXTRA_DROPS):
  - from danger 1, a gloomling drops one more gloom dust, with a chance of 0.4 at 1 and 0.2 more a
    level (1 from the frontier on);
  - from danger 2, 1 to 3 gold nuggets (a chance of 0.3, and 0.1 more a level) and amber, a new gem
    (0.12 a level past 1: 12 % in the far wilds, 24 % in the frontier, 36 % in the deep frontier; a
    thornback's shell holds 0.15 more);
  - from danger 3, a diamond (0.06 a level past 2).
  An elder's chances are doubled (at most 1). Each is rolled from the world seed and the creature on
  a channel of its own, like its kind's own drops (combat.drops_of), so a kill always drops the same.
- Mining an ore in ring n drops one more of what the ore gives (coal, raw iron, a diamond, ...) with a
  chance of EXTRA_ORE_PER_LEVEL (5 %) a level, rolled from the world seed and the cell (steps.MINED).
- Two new items: gold nuggets (4 make a gold ingot, the "gold_nuggets" recipe; toolmaking crafts one
  when it needs gold and has no gold ore to smelt, toolmaking.POOLED) and amber (amber-studded armor,
  backend.survival.frontier_gear). Both are treasures a full pair of arms makes room for
  (carrying.TREASURES).
Home ground (0) drops and mines exactly as before.
"""

from __future__ import annotations

from backend.services.crafting import BLOCKS
from backend.survival import nature
from backend.survival.creatures.combat import EXTRA_DROPS
from backend.survival.creatures.kinds import Kind
from backend.survival.creatures.moves import roll
from backend.survival.grid import Cell
from backend.survival.rings import DEEPEST, ring_at
from backend.survival.steps import MINED

GLOOM_FROM, GLOOM_CHANCE, GLOOM_PER_LEVEL = 1, 0.4, 0.2
GOLD_FROM, GOLD_CHANCE, GOLD_PER_LEVEL, GOLD_COUNT = 2, 0.3, 0.1, (1, 3)
AMBER_FROM, AMBER_PER_LEVEL, THORNBACK_AMBER = 2, 0.12, 0.15
DIAMOND_FROM, DIAMOND_PER_LEVEL = 3, 0.06
ELDER_TIMES = 2.0
EXTRA_ORE_PER_LEVEL = 0.05
ORES = ("coal_ore", "iron_ore", "copper_ore", "gold_ore", "diamond_ore")
# Roll channels (a kind's own drops use combat.DROP_CHANNEL, 70 and up).
GLOOM_ROLL, GOLD_ROLL, GOLD_COUNT_ROLL, AMBER_ROLL, DIAMOND_ROLL, EXTRA_ORE_ROLL = 120, 121, 122, 123, 124, 125


def ring_drops(seed: str, creature: dict, kind: Kind | None) -> dict[str, int]:
    """What a hostile born in a ring drops besides its kind's own (see the module docstring)."""
    state = creature["state"]
    level = min(DEEPEST, int(state.get("ring", 0)))
    if kind is None or not kind.hostile or level <= 0:
        return {}
    times = ELDER_TIMES if state.get("elder") else 1.0

    def lucky(chance: float, channel: int) -> bool:
        return roll(seed, creature["id"], 0, channel) < min(1.0, chance * times)

    found = {}
    if kind.name == "gloomling" and lucky(GLOOM_CHANCE + GLOOM_PER_LEVEL * (level - GLOOM_FROM), GLOOM_ROLL):
        found["gloom_dust"] = 1
    if level >= GOLD_FROM and lucky(GOLD_CHANCE + GOLD_PER_LEVEL * (level - GOLD_FROM), GOLD_ROLL):
        low, high = GOLD_COUNT
        found["gold_nugget"] = low + int(roll(seed, creature["id"], 0, GOLD_COUNT_ROLL) * (high - low + 1))
    amber = AMBER_PER_LEVEL * (level - 1) + (THORNBACK_AMBER if kind.name == "thornback" else 0.0)
    if level >= AMBER_FROM and lucky(amber, AMBER_ROLL):
        found["amber"] = 1
    if level >= DIAMOND_FROM and lucky(DIAMOND_PER_LEVEL * (level - DIAMOND_FROM + 1), DIAMOND_ROLL):
        found["diamond"] = 1
    return found


def extra_ore(state: dict, cell: Cell, block: str) -> list[str]:
    """One more of what a mined ore gives, sometimes, in a ring past home ground."""
    drop = BLOCKS.get(block, {}).get("drop")
    level = min(DEEPEST, ring_at(state, cell[0], cell[2]))
    if block not in ORES or not drop or level <= 0:
        return []
    return [drop] if nature.roll(state["world_seed"], cell, EXTRA_ORE_ROLL) < EXTRA_ORE_PER_LEVEL * level else []


EXTRA_DROPS.append(ring_drops)
MINED.append(extra_ore)
