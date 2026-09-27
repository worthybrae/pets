"""Danger rings around home (L5, "Frontier"): the farther from home, the harder and the richer.

The centre is home: the home Mimo built (memory kind "home", noted "built"), or its birthplace
until a home stands. The distance from it, across, sets the ring, and the ring's number is its
danger:

    ring  name            from (blocks)
    0     Home ground       0
    1     Near wilds       48
    2     Far wilds       128
    3     Frontier        256
    4     Deep frontier   512

Rings move with home: when L4 builds a bigger home and Mimo moves in, the centre moves with it.
Home ground plays exactly as before L5. Worldgen never depends on the rings: the terrain stays a
pure function of the seed and the cell, and only creatures, drops, mining luck and ruin loot read
the ring of a place.

The tick keeps what the rest of the game needs in the state (`state["frontier"]`), so a step or a
creature reads the ring without the database: {"center": [x, z], "birthplace": [x, z], "ring": the
ring Mimo stands in, "reached": the deepest ring it has stood in}. `tend_frontier` (from
brain.notice_step, after every vitals step) reads the home place once, keeps the centre on it (the
birthplace until a home stands; a life from before L5 takes its oldest home place, or where it
stands, as its birthplace), and notes the ring Mimo stands in. The first time Mimo stands in a ring
past the near wilds is a notable "found" event ("Pip reached the far wilds for the first time.").

Readiness: what Mimo needs to go into a ring on purpose (L5's frontier trip). Rings 0 and 1 are
open to every pet. The far wilds (2) take a stone sword or better (or a bow and 8 arrows), armor that
takes a fifth off a blow (leather cap and tunic), 70 health and half a day's food (30 hunger); the
frontier (3) an iron sword, a bow and 8 arrows, iron armor (45 %) and 80 health; the deep frontier
(4) a diamond sword, a bow and 16 arrows, amber armor (60 %) and 90 health. `ready_ring` is the
deepest ring Mimo is ready for, `short_of` what it lacks for one, in words.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.survival.creatures.combat import SWORDS, weapon
from backend.survival.creatures.harm import armor_cut
from backend.survival.foraging import food_points
from backend.survival.memory import BUILT, places
from backend.survival.situation import Situation

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

RINGS = ((0, "Home ground", 0.0), (1, "Near wilds", 48.0), (2, "Far wilds", 128.0), (3, "Frontier", 256.0),
         (4, "Deep frontier", 512.0))
DEEPEST = RINGS[-1][0]
OPEN_RINGS = 1  # rings 0 and 1 are open to every pet
ANNOUNCED_FROM = 2  # the first steps into this ring or a deeper one are notable


@dataclass(frozen=True)
class Ready:
    sword: float  # the least damage the best sword may do (combat.SWORDS): 5 is a stone sword
    armor: float  # the least share of a blow the armor must take off (harm.armor_cut)
    health: float
    arrows: int  # arrows (with a bow) it must carry; 0: a bow with 8 arrows may stand in for the sword
    food: float = 30.0  # hunger points of food it carries


READY = {2: Ready(sword=5.0, armor=0.20, health=70.0, arrows=0),
         3: Ready(sword=6.0, armor=0.45, health=80.0, arrows=8),
         4: Ready(sword=8.0, armor=0.60, health=90.0, arrows=16)}
BOW_INSTEAD = 8  # arrows a bow needs to stand in for a sword on the way into the far wilds
SWORD_WORDS = {5.0: "a stone sword or better", 6.0: "an iron sword or better", 8.0: "a diamond sword"}
ARMOR_WORDS = {0.20: "leather armor or better", 0.45: "iron armor or better", 0.60: "amber-studded armor"}


# Rings -----------------------------------------------------------------------------------------

def ring_of_distance(distance: float) -> int:
    """The ring a place this many blocks (across) from home lies in."""
    return max(number for number, _, start in RINGS if distance >= start)


def ring_name(ring: int) -> str:
    return RINGS[max(0, min(DEEPEST, ring))][1]


def center(state: dict) -> tuple[float, float] | None:
    """The centre of the rings as the tick last saw it, or None before the tick first tended it."""
    found = (state.get("frontier") or {}).get("center")
    return (float(found[0]), float(found[1])) if found else None


def ring_at(state: dict, x: float, z: float) -> int:
    """The ring (x, z) lies in; 0 before the tick first tended the rings."""
    middle = center(state)
    return 0 if middle is None else ring_of_distance(math.hypot(x - middle[0], z - middle[1]))


def ring_here(state: dict) -> int:
    position = state["position"]
    return ring_at(state, position["x"], position["z"])


def distance_home(state: dict) -> float:
    """Blocks (across) from Mimo to the centre; 0 before the tick first tended the rings."""
    middle, position = center(state), state["position"]
    return 0.0 if middle is None else math.hypot(position["x"] - middle[0], position["z"] - middle[1])


# The tick's side -------------------------------------------------------------------------------

def frontier_state(state: dict) -> dict:
    return state.setdefault("frontier", {})


def home_place(db) -> dict | None:
    found = places(db, ("home",))
    return found[0] if found else None


def tend_frontier(state: dict, context: ActionContext, at: float) -> None:
    """Keep the centre on home and note the ring Mimo stands in (see the module docstring)."""
    if context.db is None:
        return
    frontier = frontier_state(state)
    home = home_place(context.db)
    if "birthplace" not in frontier:
        position = state["position"]
        born = (home["x"], home["z"]) if home is not None else (position["x"], position["z"])
        frontier["birthplace"] = [round(born[0]), round(born[1])]
    if home is not None and home["note"] == BUILT:
        frontier["center"] = [home["x"], home["z"]]
    else:
        frontier["center"] = list(frontier["birthplace"])
    ring = ring_here(state)
    frontier["ring"] = ring
    reached = frontier.get("reached", 0)
    if ring > reached:
        frontier["reached"] = ring
        if ring >= ANNOUNCED_FROM:
            context.events.append((at, "found", f"{state['name']} reached the {ring_name(ring).lower()} "
                                                f"for the first time."))


# Readiness -------------------------------------------------------------------------------------

def best_sword(s: Situation) -> float:
    sword = weapon(s.inventory)
    return SWORDS[sword] if sword is not None else 0.0


def arrows(s: Situation) -> int:
    return s.count("arrow") if s.count("bow") > 0 else 0


def short_of(s: Situation, ring: int) -> list[str]:
    """What Mimo lacks to go into `ring` on purpose, in words; [] when it is ready (always for 0 and 1)."""
    need = READY.get(min(ring, DEEPEST))
    if ring <= OPEN_RINGS or need is None:
        return []
    missing = []
    bow_will_do = need.arrows == 0 and arrows(s) >= BOW_INSTEAD
    if best_sword(s) < need.sword and not bow_will_do:
        missing.append(SWORD_WORDS[need.sword])
    if need.arrows and arrows(s) < need.arrows:
        missing.append(f"a bow and {need.arrows} arrows")
    if armor_cut(s.inventory) < need.armor - 1e-9:
        missing.append(ARMOR_WORDS[need.armor])
    if s.vitals["health"] < need.health:
        missing.append(f"{round(need.health)} health")
    if food_points(s) < need.food:
        missing.append("food for half a day")
    return missing


def ready_ring(s: Situation) -> int:
    """The deepest ring Mimo is ready to go into on purpose: OPEN_RINGS (1) or more."""
    def look() -> int:
        ready = OPEN_RINGS
        for ring in range(OPEN_RINGS + 1, DEEPEST + 1):
            if short_of(s, ring):
                break
            ready = ring
        return ready
    return s.sensed("ready ring", look)


# What the viewer and the model are told --------------------------------------------------------

def ring_view(state: dict) -> dict | None:
    """/api/mimo's `ring`: {"level", "name", "center": {"x", "z"}} where Mimo stands, or None
    before the tick first tended the rings (an older save, or a life from before L5)."""
    middle = center(state)
    if middle is None:
        return None
    ring = ring_here(state)
    return {"level": ring, "name": ring_name(ring), "center": {"x": round(middle[0]), "z": round(middle[1])}}


def ring_payload(s: Situation) -> dict:
    """What a model is told about the rings: where Mimo stands, how far from home, the deepest ring it
    is ready for and what it lacks for the next one."""
    ring, ready = ring_here(s.state), ready_ring(s)
    nxt = min(ready + 1, DEEPEST)
    return {"ring": ring, "name": ring_name(ring), "danger": ring, "blocks_from_home": round(distance_home(s.state)),
            "ready_for": ready, "ready_for_name": ring_name(ready),
            "short_of_next": short_of(s, nxt) if ready < DEEPEST else []}
