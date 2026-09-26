"""What Mimo's thoughts change (Mind M2): small, bounded nudges on what it does.

A thought kept with a nudge (backend.survival.insights) holds it in state["mind"]["nudges"] until a
game day, and while it holds:
- "likes:<purpose>" ("I love fishing by the lake."): that purpose scores LIKED more;
- "wary:<kind>" ("Skitters come out near the caves at night."): from dusk to dawn, the work that
  takes Mimo where that kind is about (WARY_OF) scores WARY less;
- "pack" ("I should pack more food."): an expedition packs PACK_MORE more hunger points of food.
Each is read from the state, never from memory, so it costs the tick nothing; the pickers cap all
nudges on one purpose at pickers.NUDGE_TOP either way, the pack at expedition.PACK_MORE_TOP.
"""

from __future__ import annotations

from backend.survival.expedition import PACK_MORE as PACKING
from backend.survival.pickers import NUDGES
from backend.survival.situation import Situation

LIKED = 5.0
WARY = 10.0
PACK_MORE = 15.0
EVENING = ("dusk", "night", "pre_dawn")
# The work that takes Mimo where each hostile kind is about: skitters in caves, gloomlings in the dark.
WARY_OF = {"skitter": ("mine_ore", "gather_stone", "investigate"),
           "gloomling": ("gather_wood", "gather_stone", "mine_ore", "forage", "fish", "hunt", "farm", "explore",
                         "investigate")}


def holds(s: Situation, nudge: str) -> bool:
    return ((s.state.get("mind") or {}).get("nudges") or {}).get(nudge, 0) >= s.clock["day_number"]


def thought_nudge(s: Situation, name: str) -> float:
    """A pickers nudge: a liked purpose scores more; at night, the work that meets what Mimo is wary of less."""
    points = LIKED if holds(s, f"likes:{name}") else 0.0
    if s.phase in EVENING:
        points -= WARY * sum(1 for kind, work in WARY_OF.items() if name in work and holds(s, f"wary:{kind}"))
    return points


def pack_more(s: Situation) -> float:
    """An expedition's PACK_MORE: more food, while "pack" holds."""
    return PACK_MORE if holds(s, "pack") else 0.0


NUDGES.append(thought_nudge)
PACKING.append(pack_more)
