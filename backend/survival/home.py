"""Home (L4a final fix wave, I1): the one home lookup.

Mimo remembers one home at a time (memory.remember, memory.set_home): the first sheltered spot it
found until it finishes a shelter of its own, then the shelter it lives in, noted BUILT (a bigger
one moves it again). Whatever asks where home is reads it here, from the world itself and once per
Situation, however far Mimo has walked. Before this, several modules looked for home only near
where Mimo stood (within 64 blocks, or within Situation.places' sight), so once Mimo was farther
out a pen, a farm, a pen's count or a trip's leash followed Mimo instead of home: pens went up 76
to 86 blocks out, and the herd goal never counted them.

- home_place(s): the remembered home, or None; home_cell(s): its cell.
- built_home(s): home is a shelter Mimo built.
- home_structure(s): that shelter (its structures row), or None.
- from_home(s, x, z): blocks from home to a column, level (None without a home).
- by_home(s, kind, reach): the structures of a kind Mimo started whose anchor lies within `reach`
  blocks of home, oldest first.
- walked_near_home(s): the patches Mimo walked within FARTHEST_TRIP of home (I4).
"""

from __future__ import annotations

import math

from backend.survival.grid import Cell
from backend.survival.memory import BUILT, PATCH, cell_of, explored, places, structures
from backend.survival.situation import Situation

YARD = 32.0  # blocks from home within which a pen is home's own (pens.design_pen puts one within 10)
# I4: the farthest from home a day trip goes (curiosity.trip_reach grows up to it as the land near
# home is walked); going home at dusk looks this far for the home Mimo built (purposes.GO_HOME_RANGE).
# Overnight expeditions, farther still, are L4b's.
FARTHEST_TRIP = 240.0


def home_place(s: Situation) -> dict | None:
    """The home Mimo remembers (there is only ever one), read once per Situation."""
    def look() -> dict | None:
        if s.db is None:
            return None
        found = places(s.db, ("home",))
        return found[0] if found else None
    return s.sensed("home place", look)


def home_cell(s: Situation) -> Cell | None:
    home = home_place(s)
    return None if home is None else cell_of(home)


def built_home(s: Situation) -> bool:
    home = home_place(s)
    return home is not None and home["note"] == BUILT


def all_structures(s: Situation) -> list[dict]:
    """Everything Mimo started, oldest first, read once per Situation (the key building.py uses)."""
    return s.sensed("structures", lambda: structures(s.db) if s.db is not None else [])


def home_structure(s: Situation) -> dict | None:
    """The shelter Mimo lives in: the one whose inside cell is the home it built."""
    if not built_home(s):
        return None
    cell = home_cell(s)
    return next((found for found in reversed(all_structures(s))
                 if found["kind"] == "shelter" and (found["x"], found["y"], found["z"]) == cell), None)


def from_home(s: Situation, x: float, z: float) -> float | None:
    """Blocks from home to the column (x, z), level; None without a home."""
    home = home_place(s)
    return None if home is None else math.hypot(x - home["x"], z - home["z"])


def walked_near_home(s: Situation) -> dict[tuple[int, int], tuple[int, float]]:
    """{(rx, rz): (visits, last_at)} for the patches Mimo walked within FARTHEST_TRIP (and a patch)
    of home, read once per Situation ({} without a home)."""
    def look() -> dict:
        home = home_cell(s)
        return {} if home is None or s.db is None else explored(s.db, home, FARTHEST_TRIP + PATCH)
    return s.sensed("walked near home", look)


def by_home(s: Situation, kind: str, reach: float = YARD) -> list[dict]:
    """The structures of `kind` Mimo started within `reach` blocks of home, oldest first ([] without
    a home)."""
    if home_place(s) is None:
        return []
    return [found for found in all_structures(s)
            if found["kind"] == kind and from_home(s, found["x"], found["z"]) <= reach]
