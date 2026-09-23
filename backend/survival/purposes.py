"""Purposes: the goals Mimo chooses between, as a registry.

A Purpose has a validity check (is it on offer right now?), facts for the chooser, a utility
score and a planner that turns it into the next batch of M2 steps. The planner returns [] when
the purpose is finished or cannot go on; the brain then asks for a new choice. Planners get the
tick's ActionContext and spend its path-search budget through actions.take_search if they search.

Modules register their purposes on import: this one registers rest, sleep, explore, go_home and
eat; backend.survival.work registers gather_wood, gather_stone and mine_ore; and
backend.survival.toolmaking registers craft_tools; M4's backend.survival.foraging registers
forage and fish, backend.survival.farming farm, and backend.survival.cooking cook.
backend.survival.brain imports them all. M5 registers build_* and light_up the same way.

Scores fall in bands, so a new purpose fits in with the others. These are the real ranges before
the utility picker's random nudge (0 to 6) and its 30-point penalty for a purpose that just
failed; "late" is late_penalty, 30 off outdoor work in the last 5 game minutes before dusk and at
dusk:
- survival, 80-100: what keeps Mimo alive right now. sleep 90 at night and 70-100 when tired
  (energy below 30), else 60 (waiting at home for night); go_home 100 at dusk and night, 70-80
  late in the day, else 5 (35 when cold); eat 100 - hunger (30-100, offered below 70 hunger).
- needs, 50-80: food before it turns urgent. cook 55-80; forage 35-88 and fish 25-88, both rising
  with the food Mimo lacks and with hunger, minus late. Forage and fish reaching into the survival
  band when Mimo is starving and carries nothing is intended: then food work is survival.
- work, 40-80: tools, materials and the farm. craft_tools 70-80 (tools unlock everything else);
  gather_wood 40-80 (65 and up while Mimo carries under 3 logs' worth); gather_stone 40-65;
  mine_ore 50-80 (65 and up for iron); farm 40-80 (ripe crops add up to 25 as far as Mimo lacks
  food, capped at 80). Late takes 30 off the outdoor ones, down to 10.
- leisure, 0-65: rest 10-40 and explore 20-65 (45 and up with no tree in sight), explore minus
  late but never below 0.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from backend.services.worldgen import terrain_height
from backend.survival.beds import to_bed
from backend.survival.memory import BUILT, SHELTER_KINDS, cell_of, nearest
from backend.survival.once import log_once
from backend.survival.senses import TREE_SEARCH, trees_near
from backend.survival.situation import DUSK, NIGHTFALL, Situation
from backend.survival.steps import FOOD, FOOD_HEALTH

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

REST_STEP = 10.0  # game seconds per wait, so a trigger ends a rest promptly
REST_LONGEST = 600.0  # game seconds
EXPLORE_WALKS = 3
AT_HOME = 2.0
HOME_RANGE = 64.0
SLEEP_HOME_REACH = 8.0
TIRED_BELOW = 30.0
GO_HOME_BATCHES = 3
EXPLORE_DISTANCE = 48
EXPLORE_REACH = 3.0
HEADINGS = 8
LATE_DAY = DUSK - 300.0  # 5 game minutes before dusk
LATE_PENALTY = 30.0  # outdoor work scores this much lower late in the day
HEAD_HOME_LEAD = 180.0  # the head_home reflex's window opens this many game seconds before dusk
HOMEWARD = DUSK - HEAD_HOME_LEAD
EAT_BELOW = 70.0
FULL = 90.0


@dataclass(frozen=True)
class Purpose:
    name: str
    phrase: str  # completes "Pip chose to ...", for example "gather wood"
    description: str  # what it means, for the model chooser
    valid: Callable[[Situation], bool]
    facts: Callable[[Situation], str]
    score: Callable[[Situation], float]
    plan: Callable[[Situation, "ActionContext"], list[dict]]
    thoughts: tuple[str, ...]


PURPOSES: dict[str, Purpose] = {}


def register(purpose: Purpose) -> Purpose:
    """Add a purpose, or replace the one with the same name."""
    PURPOSES[purpose.name] = purpose
    return purpose


def is_valid(purpose: Purpose, situation: Situation) -> bool:
    """A purpose's validity check. One that crashes counts as not valid (logged once)."""
    try:
        return bool(purpose.valid(situation))
    except Exception as error:
        log_once(logger, f"{purpose.name} validity", error)
        return False


def offered(situation: Situation) -> list[Purpose]:
    """The purposes on offer right now, in registration order."""
    return [purpose for purpose in PURPOSES.values() if is_valid(purpose, situation)]


def walk_to(cell, reach: float = 0.0) -> dict:
    return {"kind": "walk", "target": [int(cell[0]), int(cell[1]), int(cell[2])], "reach": reach}


def home_of(s: Situation) -> dict | None:
    """The home Mimo built, when it is within HOME_RANGE blocks (M5); else the nearest remembered
    home or shelter within HOME_RANGE."""
    home = nearest(s.places, s.here, ("home",), HOME_RANGE)
    if home is not None and home["note"] == BUILT:
        return home
    return nearest(s.places, s.here, SHELTER_KINDS, HOME_RANGE)


def at_home(s: Situation, reach: float = AT_HOME) -> bool:
    home = home_of(s)
    return home is not None and s.distance(cell_of(home)) <= reach


def late_day(s: Situation) -> bool:
    """Dusk, or the last 5 game minutes of the day before it."""
    return s.phase == "dusk" or (s.phase == "day" and s.clock["seconds_into_day"] >= LATE_DAY)


def late_penalty(s: Situation, outdoors: bool = True) -> float:
    """How much lower outdoor work scores now: 30 late in the day, so sleep (60) and go_home win
    at dusk over work that would take Mimo away from home."""
    return LATE_PENALTY if outdoors and late_day(s) else 0.0


def homeward(s: Situation) -> bool:
    """The head_home window: from 3 game minutes before dusk until nightfall."""
    return not s.night and HOMEWARD <= s.clock["seconds_into_day"] < NIGHTFALL


def underground(s: Situation) -> bool:
    """Mimo stands below the natural surface: in its own staircase, a tunnel or a cave."""
    x, y, z = s.here
    return y <= terrain_height(x, z, s.seed)


def wait_for_nightfall(s: Situation) -> dict:
    return {"kind": "wait", "seconds": max(1.0, min(60.0, s.seconds_to(NIGHTFALL) / s.scale))}


def foods(inventory: dict, avoid=()) -> list[str]:
    """Food Mimo carries, best first, leaving out what it knows is poisonous (`avoid`)."""
    return sorted((item for item in FOOD if inventory.get(item, 0) > 0 and item not in avoid),
                  key=lambda item: -FOOD[item])


def meal(inventory: dict, hunger: float, full: float = FULL, avoid=()) -> list[dict]:
    """Eat steps, best food first, until hunger would reach `full` or the food runs out. Food in
    `avoid` (known to be poisonous) is never eaten. Food that can make Mimo sick (steps.FOOD_HEALTH)
    and is not known to be poisonous yet is only tasted, one per meal: the first bite teaches Mimo
    (backend.survival.learning), so a meal never eats a handful of red mushrooms."""
    steps = []
    for item in foods(inventory, avoid):
        servings = 1 if FOOD_HEALTH.get(item, 0.0) < 0 else inventory[item]
        while servings > 0 and hunger < full:
            steps.append({"kind": "eat", "item": item})
            servings -= 1
            hunger += FOOD[item]
    return steps


# rest ------------------------------------------------------------------------------------------

def rest_score(s: Situation) -> float:
    return 10.0 + s.trait("patience") / 10 + (20.0 if s.vitals["mood"] < 30 else 0.0)


def plan_rest(s: Situation, context: ActionContext) -> list[dict]:
    """Wait in short steps until a trigger other than idle is pending, at most 10 game minutes."""
    pending = s.brain["pending"]
    if pending is not None and set(pending["reasons"]) - {"idle"}:
        return []
    chosen_at = s.brain["chosen_at"]
    if chosen_at is not None and (s.at - chosen_at) * s.scale >= REST_LONGEST:
        return []
    return [{"kind": "wait", "seconds": max(1.0, REST_STEP / s.scale)}]


register(Purpose(
    "rest", "rest", "Stay put and rest until something happens, at most ten game minutes.",
    valid=lambda s: True,
    facts=lambda s: f"mood {round(s.vitals['mood'])}, energy {round(s.vitals['energy'])}",
    score=rest_score, plan=plan_rest,
    thoughts=("I'll sit here for a moment.", "A little rest won't hurt.")))


# sleep -----------------------------------------------------------------------------------------

def sleep_valid(s: Situation) -> bool:
    """At night, when tired, or at home from the head_home window on (to wait there for night)."""
    return s.night or s.vitals["energy"] < TIRED_BELOW or (homeward(s) and at_home(s))


def sleep_facts(s: Situation) -> str:
    home = home_of(s)
    where = f"a shelter {round(s.distance(cell_of(home)))} blocks away" if home else "no shelter known"
    return f"{s.phase}, energy {round(s.vitals['energy'])}, {where}"


def sleep_score(s: Situation) -> float:
    if s.night:
        return 90.0
    if s.vitals["energy"] < TIRED_BELOW:
        return 70.0 + (TIRED_BELOW - s.vitals["energy"])
    return 60.0


def plan_sleep(s: Situation, context: ActionContext) -> list[dict]:
    """Walk onto a bed within 8 blocks (M5), else to a shelter within 8 blocks, then sleep; at
    dusk, wait there for nightfall. After a walk there failed, sleep where Mimo stands."""
    steps = []
    home = nearest(s.places, s.here, SHELTER_KINDS, SLEEP_HOME_REACH)
    tried = (s.state.get("last_failure") or {}).get("purpose") == "sleep"
    x, y, z = s.here
    if not tried and s.grid.material(x, y - 1, z) != "bed":
        steps.extend(to_bed(s))
        if not steps and home is not None and s.distance(cell_of(home)) > 1.0:
            steps.append(walk_to(cell_of(home)))
    steps.append({"kind": "sleep"} if s.night or s.vitals["energy"] < TIRED_BELOW else wait_for_nightfall(s))
    return steps


register(Purpose(
    "sleep", "sleep", "Sleep until rested and it is day, in a shelter if one is close.",
    valid=sleep_valid, facts=sleep_facts, score=sleep_score, plan=plan_sleep,
    thoughts=("Time to curl up and sleep.", "My eyes are so heavy.")))


# explore ---------------------------------------------------------------------------------------

def explore_score(s: Situation) -> float:
    x, _, z = s.here
    score = 20.0 + s.trait("curiosity") / 5
    if not trees_near(s.seed, x, z, TREE_SEARCH):
        score += 25.0
    return max(0.0, score - late_penalty(s))


def explore_facts(s: Situation) -> str:
    x, _, z = s.here
    trees = len(trees_near(s.seed, x, z, TREE_SEARCH))
    return f"{trees} trees within {TREE_SEARCH} blocks, {s.brain['explored']} trips so far"


def plan_explore(s: Situation, context: ActionContext) -> list[dict]:
    """Up to three walks per choice, each 48 blocks out in a heading that changes with every trip
    and every day (the turns zigzag, so Mimo ends up near where it started)."""
    if s.brain["batches"] >= EXPLORE_WALKS:
        return []
    x, _, z = s.here
    turn = s.brain["explored"]
    s.brain["explored"] = turn + 1
    angle = ((turn * 3 + s.clock["day_number"]) % HEADINGS) * 2 * math.pi / HEADINGS
    tx, tz = x + round(math.cos(angle) * EXPLORE_DISTANCE), z + round(math.sin(angle) * EXPLORE_DISTANCE)
    return [walk_to((tx, terrain_height(tx, tz, s.seed) + 1, tz), EXPLORE_REACH)]


register(Purpose(
    "explore", "explore", "Walk out 48 blocks three times, in new directions, to see new land, trees and places.",
    valid=lambda s: not s.night and s.phase != "dusk",
    facts=explore_facts, score=explore_score, plan=plan_explore,
    thoughts=("I wonder what's over there.", "Let's see what lies beyond those hills.")))


# go_home ---------------------------------------------------------------------------------------

def go_home_valid(s: Situation) -> bool:
    home = home_of(s)
    return home is not None and s.distance(cell_of(home)) > AT_HOME


def go_home_score(s: Situation) -> float:
    if s.night or s.phase == "dusk":
        return 100.0  # beats sleep (90) by more than the utility picker's random nudge (6)
    if late_day(s):
        return 70.0 + s.trait("caution") / 10
    return 5.0 + (30.0 if s.vitals["warmth"] < 40 else 0.0)


def plan_go_home(s: Situation, context: ActionContext) -> list[dict]:
    home = home_of(s)
    if home is None or s.distance(cell_of(home)) <= AT_HOME or s.brain["batches"] >= GO_HOME_BATCHES:
        return []
    return [walk_to(cell_of(home))]


register(Purpose(
    "go_home", "go home", "Walk back to the nearest known shelter.",
    valid=go_home_valid,
    facts=lambda s: f"a shelter {round(s.distance(cell_of(home_of(s))))} blocks away",
    score=go_home_score, plan=plan_go_home,
    thoughts=("I should head back to my shelter.", "Home is the safest place to be.")))


# eat -------------------------------------------------------------------------------------------

def plan_eat(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return meal(s.inventory, s.vitals["hunger"], avoid=s.poisons)


register(Purpose(
    "eat", "eat", "Eat carried food, the best first.",
    valid=lambda s: bool(foods(s.inventory, s.poisons)) and s.vitals["hunger"] < EAT_BELOW,
    facts=lambda s: f"hunger {round(s.vitals['hunger'])}, carrying {s.count(*FOOD)} food",
    score=lambda s: 100.0 - s.vitals["hunger"], plan=plan_eat,
    thoughts=("Time for a snack.", "Food first, then everything else.")))
