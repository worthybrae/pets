"""Beds: where Mimo sleeps best.

A bed is a solid block. Mimo sleeps in one by lying on top of it: steps.start_sleep notes the
bed under Mimo, and the vitals then rest it at the bed rate (spec section 3). The sleep purpose
and the collapse reflex walk onto a bed within 8 blocks first, when there is one Mimo can lie on.
"""

from __future__ import annotations

from backend.survival.grid import Cell
from backend.survival.situation import Situation

BED_REACH = 8.0


def bed_near(s: Situation, reach: float = BED_REACH) -> Cell | None:
    """The top of the nearest placed bed within `reach` blocks with room to lie on it."""
    x, _, z = s.here
    tops = [(cell[0], cell[1] + 1, cell[2]) for cell, _ in s.grid.placed_cells(x, z, reach, ("bed",))]
    tops = [top for top in tops if s.grid.passable(top)]
    return min(tops, key=lambda top: (s.distance(top), top)) if tops else None


def to_bed(s: Situation) -> list[dict]:
    """A walk onto the nearest bed within 8 blocks, or nothing when there is none or Mimo lies on it."""
    top = bed_near(s)
    if top is None or top == s.here:
        return []
    return [{"kind": "walk", "target": list(top), "reach": 0.0}]
