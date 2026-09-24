"""Fish in the water and Mimo's fishing (spec L1: fish are "where fishing's catch shows").

Fish are not hunted. Fishing's stock stays M4's (backend.survival.nature: a 16x16 region's stock
sets the chance of a bite), and each fish swimming within 8 blocks of the hook adds 2 points to
that chance, at most 10, while the region has stock at all. When a catch lands, the nearest of
those fish darts to the hook and leaps (`caught_at`, which the viewer shows as a splash); it swims
on afterwards, since the catch comes from the stock, not from the fish Mimo can see.
"""

from __future__ import annotations

import math

from backend.survival.creatures.kinds import kind_of
from backend.survival.creatures.moves import move, where
from backend.survival.creatures.table import dead
from backend.survival.grid import Cell, Grid

BITE_REACH = 8.0
BITE_BONUS = 0.02  # added to the catch chance for each fish within BITE_REACH of the hook
BITE_MOST = 0.1
DART_SECONDS = 0.3


def is_fish(creature: dict) -> bool:
    kind = kind_of(creature["kind"])
    return kind is not None and kind.water


def fish_near(grid: Grid, hook: Cell, at: float) -> list[dict]:
    """Living fish within BITE_REACH blocks of the hook, nearest first."""
    if grid.herd is None:
        return []
    found = [creature for creature in grid.herd.near(hook[0], hook[2], BITE_REACH)
             if not dead(creature) and is_fish(creature)]
    return sorted(found, key=lambda creature: (math.dist(where(creature, at), hook), creature["id"]))


def bite_bonus(grid: Grid, hook: Cell, at: float) -> float:
    return min(BITE_MOST, BITE_BONUS * len(fish_near(grid, hook, at)))


def show_catch(grid: Grid, hook: Cell, at: float) -> None:
    """The nearest fish darts to the hook and leaps there, if one is near."""
    found = fish_near(grid, hook, at)
    if not found:
        return
    fish = found[0]
    fish["next_at"] = max(fish["next_at"], move(fish, [hook], at, DART_SECONDS, "swimming"))
    fish["state"]["caught_at"] = at
    grid.herd.save(fish)
