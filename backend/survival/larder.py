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
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival import foraging
from backend.survival.carrying import CHEST_STACKS, crafts_fit, room_for
from backend.survival.cooking import made
from backend.survival.foraging import whole_walk
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.life_goals import home_structure, whole
from backend.survival.purposes import Purpose, foods, register
from backend.survival.situation import Situation
from backend.survival.steps import FOOD, REACH
from backend.survival.storage import chest_contents, chest_placed, chest_spot, spare_food
from backend.survival.structures import blueprint_of, clearing

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

GOAL = "full_larder"
LARDER_FOOD = 60.0  # hunger points of food in the chests that make a full larder: a day's worth
LARDER_EXTRA = 40.0  # at most this much more food Mimo wants on hand while it fills the larder
FED = 50.0  # hunger from which Mimo gathers for the larder


def chest_food(s: Situation) -> float:
    """Hunger points of the food in all of Mimo's chests, leaving out food it knows is poisonous. L5
    (pre-flight, carry 5): an old ruin's chest is loot left out there, not Mimo's larder."""
    from backend.survival.ruins import ruin_chest_key  # here: brain imports the larder before the ruins
    return sum(FOOD[item] * chest[item] for key, chest in s.state.get("chests", {}).items()
               if not ruin_chest_key(s.seed, key) for item in foods(chest, s.poisons))


def filling(s: Situation) -> bool:
    goal = active(s)
    return goal is not None and goal.name == GOAL


def more_food(s: Situation) -> float:
    """Food beyond a day's worth Mimo wants on hand while it fills the larder and is not hungry."""
    if not filling(s) or s.vitals["hunger"] < FED:
        return 0.0
    return min(LARDER_EXTRA, max(0.0, LARDER_FOOD - chest_food(s)))


foraging.MORE_FOOD.append(more_food)


def larder_moves(s: Situation) -> list[tuple[str, int]]:
    """(food, amount) stock_larder would store: the spare food, as far as the chest has room."""
    chest = chest_contents(s, chest_spot(s))
    moves = []
    for item, amount in spare_food(s):
        amount = min(amount, room_for(chest, item, CHEST_STACKS))
        if amount > 0:
            chest[item] = chest.get(item, 0) + amount
            moves.append((item, amount))
    return moves


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
    if s.night or not filling(s) or chest_spot(s) is None or chest_food(s) >= LARDER_FOOD:
        return False
    steps = chest_steps(s)
    return steps is not None and (bool(steps) or bool(larder_moves(s)))


def plan_stock(s: Situation, context: ActionContext) -> list[dict]:
    """Walk home, put the chest in when there is none, and put the spare food in it."""
    if s.brain["batches"] > 0 or not stock_valid(s):
        return []
    cell = chest_spot(s)
    home = blueprint_of(home_structure(s))
    steps = [] if s.distance(cell) <= REACH and s.here in home.stands else [whole_walk(home.anchor)]
    return steps + chest_steps(s) + [{"kind": "store", "target": list(cell), "item": item, "amount": amount}
                                     for item, amount in larder_moves(s)]


register(Purpose(
    "stock_larder", "stock the larder",
    "Carry spare food home and keep it in the chest, so a hungry day never turns into starving.",
    valid=stock_valid,
    facts=lambda s: f"{round(chest_food(s))} of {round(LARDER_FOOD)} hunger of food in the chest; "
                    f"{sum(amount for _, amount in larder_moves(s))} spare food carried",
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
