"""A full larder (L4): the full_larder goal and its stock_larder purpose.

Mimo carries a game day's worth of food (foraging.FOOD_WANTED, 60 hunger), and build_storage puts
away only what is beyond that, and only when its arms fill. While a full larder is its goal and it
is not hungry (hunger FED or more), Mimo wants up to LARDER_EXTRA more food on hand (`more_food`,
added to foraging.food_need), so forage, fish, hunt and farm gather past a day's worth.
stock_larder puts the chest in its corner of the shelter first when there is none (carried, or
made from 8 planks, as build_storage does), then carries the spare food home and stores it. The
larder is full when the chests hold LARDER_FOOD hunger of food Mimo would eat (not what it knows
is poisonous). build_storage still takes food out when Mimo runs short: that is what a larder is
for.

stock_larder is offered only while the full larder is Mimo's goal, by day, at the shelter Mimo
built: to put the chest in, or with spare food carried and room in the chest. Work band: 55 plus
a tenth of thrift. The goal's rules score is 45 plus a tenth of thrift, 15 more when Mimo is
hungry.

W2: another goal may fill the larder its own way (TARGETS: "Ready for winter", backend.survival.winter_prep,
wants WINTER_FOOD of food that will still be good in the winter, and more of it on hand): stock_larder and the
food Mimo wants on hand then follow that goal's target (`target_of`).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from backend.survival import foraging
from backend.survival.carrying import crafts_fit
from backend.survival.cooking import made
from backend.survival.foraging import whole_walk
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.once import log_once
from backend.survival.life_goals import home_structure, whole
from backend.survival.purposes import Purpose, foods, register
from backend.survival.situation import Situation
from backend.survival.steps import FOOD, REACH
from backend.survival.spoilage import SPOILED
from backend.survival.storage import (chest_placed, chest_spot, chests_built, spare_food, spoiled_out, stored_in,
                                      storing_cells, to_clear)
from backend.survival.structures import blueprint_of, clearing

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

GOAL = "full_larder"
LARDER_FOOD = 60.0  # hunger points of food in the chests that make a full larder: a day's worth
LARDER_EXTRA = 40.0  # at most this much more food Mimo wants on hand while it fills the larder
FED = 50.0  # hunger from which Mimo gathers for the larder
# W2: functions (Situation, goal) giving (the food the chests should hold, how the chests' food is measured, the
# most food Mimo wants on hand beyond a day's) while `goal` fills the larder its own way, or None
# (backend.survival.winter_prep). One that crashes counts as None (logged once).
TARGETS: list = []


def chest_food(s: Situation) -> float:
    """Hunger points of the food in all of Mimo's chests, leaving out food it knows is poisonous. L5
    (pre-flight, carry 5): an old ruin's chest is loot left out there, not Mimo's larder."""
    from backend.survival.ruins import ruin_chest_key  # here: brain imports the larder before the ruins
    return sum(FOOD[item] * chest[item] for key, chest in s.state.get("chests", {}).items()
               if not ruin_chest_key(s.seed, key) for item in foods(chest, s.poisons))


def target_of(s: Situation) -> tuple[float, Callable[[Situation], float], float] | None:
    """(the food the chests should hold, how it is measured, the most more Mimo wants on hand) while Mimo's goal
    fills the larder, else None."""
    goal = active(s)
    if goal is None:
        return None
    if goal.name == GOAL:
        return LARDER_FOOD, chest_food, LARDER_EXTRA
    for aim in TARGETS:
        try:
            found = aim(s, goal)
        except Exception as error:
            log_once(logger, "larder target", error)
            continue
        if found is not None:
            return found
    return None


def filling(s: Situation) -> bool:
    return target_of(s) is not None


def more_food(s: Situation) -> float:
    """Food beyond a day's worth Mimo wants on hand while it fills the larder and is not hungry."""
    found = target_of(s)
    if found is None or s.vitals["hunger"] < FED:
        return 0.0
    target, measure, extra = found
    return min(extra, max(0.0, target - measure(s)))


foraging.MORE_FOOD.append(more_food)


def larder_cells(s: Situation) -> list[tuple[int, int, int]]:
    """The chests stock_larder fills: home's own (in its corner, placed or to be put in), then (W2 fix T) every other
    chest Mimo built that it can get to (storage.storing_cells)."""
    home = chest_spot(s)
    return [home] + [cell for cell in storing_cells(s) if cell != home]


def larder_moves(s: Situation) -> list[tuple[tuple[int, int, int], str, int]]:
    """(chest, food, amount) stock_larder would store: the spare food, as far as the chests have room, home's first,
    once the spoiled food a wild pet throws out of them is gone (W2 fix T: storage.spoiled_out; only home's chest
    was ever filled, and on the W2 gate a taught pet's was full of spoiled food, dirt and seeds from its first
    autumn on, while its older chests stood empty)."""
    return stored_in(s, larder_cells(s), larder_clears(s), limit=None, moves=spare_food(s))


def larder_clears(s: Situation) -> list[tuple[tuple[int, int, int], str, int]]:
    """(chest, item, amount) thrown out of the chests before the larder's food goes in (W2 fix T): the spoiled food
    (storage.spoiled_out) and, when the food still does not fit, the rubble and hoarded seeds and wheat of a full
    chest (storage.to_clear, as build_storage throws them out for what it puts away) and what gives way to food."""
    spoiled = spoiled_out(s)
    return spoiled + [entry for entry in to_clear(s, spare_food(s), food=True) if entry[1] != SPOILED]


def chest_steps(s: Situation) -> list[dict] | None:
    """The steps that put a chest in its corner of the shelter: [] when one stands there, None when
    Mimo has none and cannot make one it has room to carry."""
    cell = chest_spot(s)
    if chest_placed(s, cell):
        return []
    crafting = [] if s.count("chest") > 0 else made(dict(s.inventory), "chest")
    if crafting is None or not crafts_fit(s.inventory, crafting):
        return None
    return crafting + clearing(s.grid, cell) + [{"kind": "place", "target": list(cell), "block": "chest"}]


def stock_valid(s: Situation) -> bool:
    found = target_of(s)
    if s.night or found is None or chest_spot(s) is None or found[1](s) >= found[0]:
        return False
    steps = chest_steps(s)
    return steps is not None and (bool(steps) or bool(larder_moves(s)))


def plan_stock(s: Situation, context: ActionContext) -> list[dict]:
    """Walk home, put the chest in when there is none, throw out what went bad (W2 fix T) and put the spare food in
    it, then in the other chests Mimo built (walking into each one's shelter, as build_storage does)."""
    if s.brain["batches"] > 0 or not stock_valid(s):
        return []
    cell = chest_spot(s)
    home = blueprint_of(home_structure(s))
    steps = [] if s.distance(cell) <= REACH and s.here in home.stands else [whole_walk(home.anchor)]
    steps += chest_steps(s)
    stands, at = dict(chests_built(s)), cell
    visits = [(chest, item, amount, "away") for chest, item, amount in larder_clears(s)]
    visits += [(chest, item, amount, "store") for chest, item, amount in larder_moves(s)]
    for chest, item, amount, kind in sorted(visits, key=lambda entry: entry[0] != cell):
        if chest != at:
            if chest not in stands:
                continue
            steps.append(whole_walk(stands[chest]))
            at = chest
        if kind == "away":
            steps.append({"kind": "take", "target": list(chest), "item": item, "amount": amount, "away": True})
        else:
            steps.append({"kind": "store", "target": list(chest), "item": item, "amount": amount})
    return steps


register(Purpose(
    "stock_larder", "stock the larder",
    "Carry spare food home and keep it in the chest, so a hungry day never turns into starving.",
    valid=stock_valid,
    facts=lambda s: f"{round(chest_food(s))} of {round((target_of(s) or (LARDER_FOOD,))[0])} hunger of food in the "
                    f"chest; {sum(amount for _, _, amount in larder_moves(s))} spare food carried",
    score=lambda s: 55.0 + s.trait("thrift") / 10, plan=plan_stock,
    thoughts=("Some for now, some for later.", "A full chest means no hungry nights.")))


def chest_at_home(s: Situation) -> float:
    home = home_structure(s)
    cell = blueprint_of(home).one("chest") if home is not None else None
    return whole(cell is not None and s.grid.material(*cell) == "chest")


register_goal(Goal(
    GOAL, "A full larder",
    "A chest of food at home means a hungry day or a long night never turns into starving.",
    (Milestone("Put a chest at home", chest_at_home, ("build_storage", "stock_larder")),
     Milestone("Store a day's food in it", lambda s: chest_food(s) / LARDER_FOOD,
               ("forage", "fish", "hunt", "farm", "cook", "stock_larder", "explore"))),
    score=lambda s: 45.0 + s.trait("thrift") / 10 + (15.0 if s.vitals["hunger"] < 50 else 0.0),
    thought="A full chest at home. Then no night is a hungry one.", after=("first_shelter",),
    valid=lambda s: home_structure(s) is not None))
