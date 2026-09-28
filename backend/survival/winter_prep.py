"""W2: "Ready for winter" (the Wild World spec's "Recipes, blocks and the winter goal").

The goal `winter_ready` repeats: it is offered from autumn day 1 until winter day 1 to a pet with a built home
that knows `wild:winter` (a gentle pet always does). Its rules score is 70 plus a tenth of caution (70 to 80),
above iron tools and never past the survival floor, and while it is open the season pulls it WINTER_PULL higher
(goals.PULLS), so at the first autumn dawn's goal choice it wins over a goal the rules would otherwise keep.
Its milestones, each only for a lesson Mimo knows (one it does not know is whole: nothing to do for it):
- the chests hold WINTER_FOOD hunger points (six winter days) of food Mimo would eat that will still be good on
  winter day 5 at chest rates (`winter_food`; a gentle pet's food never spoils), which stock_larder serves with
  that target (larder.TARGETS), Mimo wanting up to WINTER_EXTRA more food on hand while it gathers;
- a wool cloak, a hearth in home and SMOKED_WANTED smoked meat (the cloak, the hearth and the smoke step come
  with their purposes and recipes: a milestone is skipped until then, goals.counted).
Reached, it is a notable "goal" event, as goals are.

In winter a pet that knows winter keeps near the home it built (`keeps_near`): a winter night out, or a winter day
in the mountains (vitals.ALPINE_DAY: 45 less 60), freezes. It takes up no expedition and no riches trip (FAR_GOALS,
goals.HELD_OFF: one already under way is given up at the next goal check, "it cannot be done now", and Mimo comes
home), and no trip heads for a target farther than WINTER_REACH from home or in the mountains (trips.FENCES).
Measured on the gate's gentle lives before this rule: every freezing minute of the first winters was 150 to 240
blocks out, on an expedition, a riches trip or the far hills, and one pet lost 88 health in a winter night dug in
on a mountain with no fire.
"""

from __future__ import annotations

import math

from backend.services.worldgen import biome_at
from backend.survival import larder, sky
from backend.survival.clock import DAY_SECONDS
from backend.survival.goals import HELD_OFF, PULLS, Goal, Milestone, register_goal
from backend.survival.home import built_home, home_cell, home_structure
from backend.survival.purposes import foods
from backend.survival.situation import Situation
from backend.survival.spoilage import CHEST_RATE, PERISHABLE, WINTER_RATE
from backend.survival.steps import FOOD
from backend.survival.trips import FENCES
from backend.survival.wild import is_wild, unlocked

GOAL = "winter_ready"
WINTER_FOOD = 360.0  # hunger points: six winter days
WINTER_EXTRA = 120.0  # the most food beyond a day's Mimo wants on hand while it fills the chests for winter
GOOD_UNTIL = 4  # winter days the food must keep: it is still good on winter day 5
SMOKED_WANTED = 8
WINTER_PULL = 100.0  # the season's pull on the goal while it is open (as much as goals.STICK)
WINTER_REACH = 96.0  # blocks from the home it built that a pet that knows winter goes in winter
FAR_GOALS = ("expedition", "frontier")  # goals held off in winter: an expedition and riches farther out
AUTUMN = sky.SEASONS.index("autumn") * sky.SEASON_DAYS  # the season day autumn starts on (20)
WINTER_START = sky.SEASONS.index("winter") * sky.SEASON_DAYS  # and winter (30)


def season_day(s: Situation) -> int:
    """The season day (0 to 39) now; spring day 1 for a state with no birth time (a test's bare state)."""
    return sky.season_at(s.state, s.at, s.scale)[1] if "born_at" in s.state else 0


def preparing(s: Situation) -> bool:
    """Autumn: from autumn day 1 until winter day 1."""
    return AUTUMN <= season_day(s) < WINTER_START


def days_to_winter(s: Situation) -> float:
    return max(0.0, WINTER_START - season_day(s) - s.clock["seconds_into_day"] / DAY_SECONDS)


def winter_food(s: Situation, good_until: int = GOOD_UNTIL) -> float:
    """Hunger points of the food in Mimo's chests (not an old ruin's) it would eat and that will still be good
    `good_until` winter days in (GOOD_UNTIL: on winter day 5, the goal's measure; 0: on winter day 1, the W2 gate's,
    the controller's ruling on the W2 dry run): for a wild pet, the lots whose wear by then (half as fast in a
    chest, and a third of that in winter) stays under 1; a gentle pet's food never spoils."""
    from backend.survival.ruins import ruin_chest_key  # here: brain imports the larder before the ruins
    wild, autumn = is_wild(s.state), days_to_winter(s)
    lots = s.state.get("chest_lots", {})
    total = 0.0
    for key, chest in s.state.get("chests", {}).items():
        if ruin_chest_key(s.seed, key):
            continue
        for item in foods(chest, s.poisons):
            count = chest[item]
            if wild and item in PERISHABLE:
                later = (autumn * CHEST_RATE + good_until * CHEST_RATE * WINTER_RATE) / PERISHABLE[item]
                count = min(count, sum(number for number, wear in lots.get(key, {}).get(item, []) if wear + later < 1.0))
            total += FOOD[item] * count
    return total


def target(s: Situation, goal) -> tuple | None:
    """larder.TARGETS: the winter's food while "Ready for winter" is Mimo's goal."""
    return (WINTER_FOOD, winter_food, WINTER_EXTRA) if goal.name == GOAL else None


def held(s: Situation, item: str) -> int:
    """How many of `item` Mimo carries and its chests hold."""
    return s.count(item) + sum(chest.get(item, 0) for chest in s.state.get("chests", {}).values())


def food_share(s: Situation) -> float:
    return 1.0 if not unlocked(s, "winter") else winter_food(s) / WINTER_FOOD


def cloak_share(s: Situation) -> float:
    return 1.0 if not unlocked(s, "cloak") or held(s, "wool_cloak") > 0 else 0.0


def hearth_home(s: Situation) -> bool:
    """A hearth stands in a room cell of the shelter Mimo lives in."""
    from backend.survival.structures import blueprint_of  # here: structures imports the building purposes
    structure = home_structure(s)
    if structure is None:
        return False
    return any(s.grid.material(*planned.cell) == "hearth" for planned in blueprint_of(structure).parts("room"))


def hearth_share(s: Situation) -> float:
    return 1.0 if not unlocked(s, "hearth") or hearth_home(s) else 0.0


def smoked_share(s: Situation) -> float:
    return 1.0 if not unlocked(s, "smoking") else held(s, "smoked_meat") / SMOKED_WANTED


def goal_valid(s: Situation) -> bool:
    return preparing(s) and unlocked(s, "winter") and home_structure(s) is not None


def winter_pull(s: Situation, goal) -> tuple[float, str]:
    """goals.PULLS: winter is coming."""
    if goal.name != GOAL or not preparing(s):
        return 0.0, ""
    return WINTER_PULL, f"winter comes in {max(1, round(days_to_winter(s)))} days"


def keeps_near(s: Situation) -> bool:
    """In winter a pet that knows winter keeps near the home it built."""
    return season_day(s) >= WINTER_START and unlocked(s, "winter") and built_home(s)


def far_goal(s: Situation, goal) -> bool:
    """goals.HELD_OFF: no expedition and no riches trip in winter."""
    return goal.name in FAR_GOALS and keeps_near(s)


def winter_fence(s: Situation, cell) -> bool:
    """trips.FENCES: in winter no trip heads for a target farther than WINTER_REACH from home or in the mountains."""
    if not keeps_near(s):
        return False
    home = home_cell(s)
    far = math.hypot(cell[0] - home[0], cell[2] - home[2]) > WINTER_REACH
    return far or biome_at(cell[0], cell[2], s.seed) == "alpine"


register_goal(Goal(
    GOAL, "Ready for winter",
    "Winter is coming: crops stop and animals hide, so the chests need food, and a cloak, a hearth and smoked "
    "meat will see it through.",
    (Milestone("Fill the chests with food for the winter", food_share,
               ("stock_larder", "forage", "fish", "hunt", "farm", "cook", "smoke_meat")),
     Milestone("Make a wool cloak", cloak_share, ("make_cloak",), items=("wool_cloak",)),
     Milestone("Build a hearth at home", hearth_share, ("build_hearth",), items=("hearth",)),
     Milestone("Smoke meat for the winter", smoked_share, ("smoke_meat",))),
    score=lambda s: 70.0 + s.trait("caution") / 10, thought="Winter is coming. Better get ready.",
    after=("first_shelter",), valid=goal_valid, repeat=True))
larder.TARGETS.append(target)
PULLS.append(winter_pull)
HELD_OFF.append(far_goal)
FENCES.append(winter_fence)
