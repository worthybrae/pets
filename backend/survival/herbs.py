"""W1: sunleaf, the little yellow herb that ends a sickness (backend.survival.ailments).

- `take_herb`, a reflex (priority 45, between eat_now and warm_up): a sick pet that knows `wild:sunleaf` and
  carries one eats it.
- `find_herb`, in the needs band (75): a sick pet that knows sunleaf but carries none walks to the nearest
  sunleaf within HERB_RANGE blocks, picks it and eats it.
- `gather_herbs` (52, a need: goals.URGES): by day, a pet that knows sunleaf picks one it sees within sight
  until it carries HERBS_CARRIED.
- `nibble`, the instinct of a pet that does not know sunleaf (70): sick, with a sunleaf within NIBBLE_RANGE
  blocks, it walks over and eats it, once in NIBBLE_CHANCE sicknesses (a seeded roll when the sickness
  begins: ailments.fall_sick). Eating one while sick is what teaches the lesson alone (backend.survival.knocks).
A gentle pet is never sick, so none of these is ever on offer to it.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.survival.ailments import HERB, sickness
from backend.survival.foraging import STAND, whole_walk
from backend.survival.goals import add_urge
from backend.survival.grid import Cell
from backend.survival.purposes import Purpose, register
from backend.survival.reflexes import Reflex, register as register_reflex
from backend.survival.senses import FOOD_SIGHT, by_distance, natural_plants, near_failure
from backend.survival.situation import Situation
from backend.survival.wild import is_wild, knows

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

HERB_RANGE = 64.0
NIBBLE_RANGE = 16.0
HERBS_CARRIED = 2


def herbs_near(s: Situation, radius: float) -> list[Cell]:
    """Sunleaf standing within `radius` blocks, nearest first, away from a step that just failed: the wild
    ones worldgen grew and the ones that came back."""
    def look() -> list[Cell]:
        x, _, z = s.here
        cells = set(natural_plants(s.seed, x, z, radius, (HERB,)))
        cells.update(cell for cell, _ in s.grid.placed_cells(x, z, radius, (HERB,)))
        return [cell for cell in by_distance(cells, s.here)
                if s.grid.material(*cell) == HERB and not near_failure(s.state, cell)]
    return s.sensed(f"herbs {radius}", look)


def pick_and_eat(s: Situation, cell: Cell) -> list[dict]:
    walk = [whole_walk(cell, STAND)] if math.dist(s.here, cell) > STAND else []
    return [*walk, {"kind": "pick", "target": list(cell)}, {"kind": "eat", "item": HERB}]


# take_herb -------------------------------------------------------------------------------------

def take_herb_due(s: Situation) -> bool:
    return sickness(s.state) is not None and s.inventory.get(HERB, 0) > 0 and knows(s, "sunleaf")


register_reflex(Reflex("take_herb", 45, trigger=take_herb_due, plan=lambda s, context: [{"kind": "eat", "item": HERB}],
                       thought="Sunleaf. That will help.", event="{name} ate some sunleaf to feel better.",
                       cooldown=5.0))


# find_herb -------------------------------------------------------------------------------------

def find_herb_valid(s: Situation) -> bool:
    return (sickness(s.state) is not None and s.inventory.get(HERB, 0) < 1 and knows(s, "sunleaf")
            and bool(herbs_near(s, HERB_RANGE)))


def plan_find_herb(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0 or not find_herb_valid(s):
        return []
    return pick_and_eat(s, herbs_near(s, HERB_RANGE)[0])


register(Purpose(
    "find_herb", "find sunleaf", "Sick: go and eat the sunleaf nearby, which ends a sickness.",
    valid=find_herb_valid,
    facts=lambda s: f"sick; sunleaf {round(s.distance(herbs_near(s, HERB_RANGE)[0]))} blocks away",
    score=lambda s: 75.0, plan=plan_find_herb,
    thoughts=("Sunleaf will make me feel better.", "I know what helps: sunleaf.")))


# gather_herbs ----------------------------------------------------------------------------------

def gather_valid(s: Situation) -> bool:
    return (not s.night and is_wild(s.state) and s.inventory.get(HERB, 0) < HERBS_CARRIED and knows(s, "sunleaf")
            and bool(herbs_near(s, FOOD_SIGHT)))


def plan_gather(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0 or not gather_valid(s):
        return []
    steps: list[dict] = []
    where = s.here
    for cell in herbs_near(s, FOOD_SIGHT)[:HERBS_CARRIED - s.inventory.get(HERB, 0)]:
        if math.dist(where, cell) > STAND:
            steps.append(whole_walk(cell, STAND))
            where = cell
        steps.append({"kind": "pick", "target": list(cell)})
    return steps


add_urge("gather_herbs", gather_valid)
register(Purpose(
    "gather_herbs", "gather sunleaf", "Pick a little sunleaf to carry, for when sickness comes.",
    valid=gather_valid, facts=lambda s: f"carrying {s.count(HERB)} sunleaf; some grows nearby",
    score=lambda s: 52.0, plan=plan_gather,
    thoughts=("A little sunleaf, just in case.", "Sunleaf is good to have on hand.")))


# nibble ----------------------------------------------------------------------------------------

def nibble_valid(s: Situation) -> bool:
    found = sickness(s.state)
    return (found is not None and bool(found.get("nibble")) and not knows(s, "sunleaf")
            and bool(herbs_near(s, NIBBLE_RANGE)))


def plan_nibble(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0 or not nibble_valid(s):
        return []
    return pick_and_eat(s, herbs_near(s, NIBBLE_RANGE)[0])


register(Purpose(
    "nibble", "nibble a plant", "Sick, and something green nearby smells right: go and nibble it.",
    valid=nibble_valid, facts=lambda s: "sick; a little yellow plant nearby smells right",
    score=lambda s: 70.0, plan=plan_nibble,
    thoughts=("That little yellow plant smells good somehow.", "Maybe a nibble of that will help.")))
