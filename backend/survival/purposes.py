"""Purposes: the goals Mimo chooses between, as a registry.

A Purpose has a validity check (is it on offer right now?), facts for the chooser, a utility
score and a planner that turns it into the next batch of M2 steps. The planner returns [] when
the purpose is finished or cannot go on; the brain then asks for a new choice. Planners get the
tick's ActionContext and spend its path-search budget through actions.take_search if they search.

Modules register their purposes on import: this one registers rest, sleep, explore, go_home and
eat; backend.survival.work registers gather_wood, gather_stone and mine_ore; and
backend.survival.toolmaking registers craft_tools; M4's backend.survival.foraging registers
forage and fish, backend.survival.farming farm, and backend.survival.cooking cook.
M5's backend.survival.building registers build_shelter, backend.survival.storage build_storage
and drop_items, backend.survival.lighting light_up and backend.survival.farmstead build_farm.
L1's backend.survival.creatures.hunting registers hunt, and L2's backend.survival.creatures.gear
make_gear. backend.survival.brain imports them all.

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
- leisure, 0-65: rest 10-40, and explore, which L4 offers only for a reason (backend.survival.trips):
  it scores its reason's score, minus late, never below 0 -- 30-65 ordinarily, but looking for food
  scores like food work and can reach 83, into the needs band, when Mimo has none stored and none
  on hand (fix round 1: this used to say 30-65 outright).
- M5's building purposes sit in the same bands. build_shelter 60-80 while Mimo has no shelter of
  its own (70 and up from the afternoon on), 75 to repair one and 45-55 to furnish it; light_up
  72 in the evening at home, so the torches go up before sleep; build_storage 50-70, rising as
  Mimo's arms fill (55 to take food out); drop_items 30-78, from leisure into needs as the arms
  fill; build_farm 45-55, minus late.
- L1's hunt sits in the needs band with forage and fish: 25-88, rising with the food Mimo lacks and
  with hunger, 5 more or less with bravery, minus late.
- L2's make_gear sits in the work band: 55-75, 55 plus a tenth of caution and 10 more when a
  creature hurt Mimo in the last game day.
- L4b: investigate (backend.survival.journal) sits in the work band, 40-65 by curiosity, minus late.
- L4b: an expedition's pack is 60 and come_home 75 (backend.survival.expedition). While Mimo means
  to stay out (`AWAY`), go_home is not on offer.
- L4b: camp is 85 late in the day and 95 at dusk and at night (backend.survival.camp).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from backend.services.worldgen import terrain_height
from backend.survival.beds import to_bed
from backend.survival.home import FARTHEST_TRIP, home_place
from backend.survival.memory import BUILT, SHELTER_KINDS, cell_of, nearest
from backend.survival.once import log_once
from backend.survival.senses import WATER_SIGHT, afloat, shores_near
from backend.survival.situation import DUSK, NIGHTFALL, Situation
from backend.survival.steps import FOOD, FOOD_HEALTH
from backend.survival.trips import best_trip, lift, next_stop, trip_facts

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

REST_STEP = 10.0  # game seconds per wait, so a trigger ends a rest promptly
REST_LONGEST = 120.0  # game seconds (L4: two game minutes, then Mimo looks again for something to do)
EXPLORE_WALKS = 3
AT_HOME = 2.0
HOME_RANGE = 64.0
# L2: a shelter Mimo built, with its door, is the safe place at night, so Mimo goes back to it from
# twice as far as to any other home or shelter it remembers.
BUILT_HOME_RANGE = 2 * HOME_RANGE
# L4a final fix wave, I4: a day trip may end up to home.FARTHEST_TRIP blocks out now, so going home
# (go_home, the head_home reflex) looks that far, and a little farther, for the home Mimo built. A
# flee or a swim for land still looks only BUILT_HOME_RANGE for it. Follow-up fix, item 2: a day
# trip could still end up beyond that, so going home now finds the built home from any distance.
GO_HOME_RANGE = float("inf")
SLEEP_HOME_REACH = 8.0
TIRED_BELOW = 30.0
# L4 fix round 2: shared with curiosity.lift, which returns 0 below it -- hungry enough that eat
# would be offered soon is hungry enough that curiosity should not compete with it either.
HUNGRY_BELOW = 30.0
GO_HOME_BATCHES = 3
EXPLORE_REACH = 3.0
LATE_DAY = DUSK - 300.0  # 5 game minutes before dusk
LATE_PENALTY = 30.0  # outdoor work scores this much lower late in the day
HEAD_HOME_LEAD = 180.0  # the head_home reflex's window opens this many game seconds before dusk
HOMEWARD = DUSK - HEAD_HOME_LEAD
EAT_BELOW = 70.0
FULL = 90.0
# L4 fix round 1: the leisure and work bands' ceiling -- a lift (curiosity's among them) never
# pushes a purpose past here, into the survival band (80 and up): staying alive comes first, the
# same rule goals.boosted's GOAL_TOP already gives a goal's own boost, so the two share it.
SURVIVAL_FLOOR = 80.0


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
    """The purposes on offer right now, in name order. Fix round 1: registration order (the order
    the purpose modules happen to import in) used to leak into `pickers.utility_pick`'s jitter, one
    `rng.uniform` call per option in list order, so a seeded run gave different picks under
    `unittest discover` (every test module imported first) than run alone. Name order is the same
    however the modules import."""
    return [purpose for _, purpose in sorted(PURPOSES.items()) if is_valid(purpose, situation)]


def walk_to(cell, reach: float = 0.0) -> dict:
    return {"kind": "walk", "target": [int(cell[0]), int(cell[1]), int(cell[2])], "reach": reach}


def home_of(s: Situation, reach: float = BUILT_HOME_RANGE) -> dict | None:
    """The home Mimo built, when it is within `reach` blocks (BUILT_HOME_RANGE: M5, doubled in L2;
    going home looks GO_HOME_RANGE, the final fix wave); else the nearest remembered home or shelter
    within HOME_RANGE; else (L5) the home FAR_HOMES name. L4a final fix wave, I1: the built home is
    read through the one home lookup (backend.survival.home), not only from the places in sight."""
    home = home_place(s)
    if home is not None and home["note"] == BUILT and s.distance(cell_of(home)) <= reach:
        return home
    found = nearest(s.places, s.here, SHELTER_KINDS, HOME_RANGE)
    return found if found is not None else far_home(s)  # L5: the home it built, from far out


# L4b: functions of the Situation that say Mimo means to stay out tonight (an expedition,
# backend.survival.expedition): go_home and the head_home reflex leave it be, and it builds no new home.
AWAY: list = []


def away(s: Situation) -> bool:
    """Mimo means to stay away from home (AWAY); one that crashes counts as no (logged once)."""
    for check in AWAY:
        try:
            if check(s):
                return True
        except Exception as error:
            log_once(logger, "away", error)
    return False


def at_home(s: Situation, reach: float = AT_HOME) -> bool:
    home = home_of(s)
    return home is not None and s.distance(cell_of(home)) <= reach


def land_refuge(s: Situation) -> dict | None:
    """A walk out of the water Mimo stands in (senses.afloat), to a known home or shelter first,
    else the nearest natural shore (senses.shores_near); None once Mimo is on dry ground already,
    or none is found nearby. L2 followup fix: sleep and rest never lie Mimo down afloat (plan_sleep,
    plan_rest, backend.survival.brain.waiting) -- a flee run never picks a target on water either
    (creatures.defense.run_away), but Mimo can still wander into it on its own, and asleep there it
    is an easy catch."""
    if not afloat(s.grid, s.here):
        return None
    home = home_of(s)
    if home is not None:
        return walk_to(cell_of(home))
    shores = shores_near(s.grid, s.seed, s.here, WATER_SIGHT)
    return walk_to(shores[0][0]) if shores else None


def late_day(s: Situation) -> bool:
    """Dusk, or the last 5 game minutes of the day before it; L5: far from home, earlier by the walk
    home (`homeward_from`), so going home wins and outdoor work gives way from then on."""
    early = HOMEWARD - homeward_from(s)
    return s.phase == "dusk" or (s.phase == "day" and s.clock["seconds_into_day"] >= LATE_DAY - early)


def late_penalty(s: Situation, outdoors: bool = True) -> float:
    """How much lower outdoor work scores now: 30 late in the day, so sleep (60) and go_home win
    at dusk over work that would take Mimo away from home."""
    return LATE_PENALTY if outdoors and late_day(s) else 0.0


# L5: functions of the Situation naming the home Mimo built when home_of's own reach does not find it
# (backend.survival.frontier: from the far wilds on), and functions giving game seconds the head_home
# window opens early (frontier: the walk home from out there). One that crashes counts for nothing.
FAR_HOMES: list = []
HOMEWARD_LEADS: list = []


def far_home(s: Situation) -> dict | None:
    """The first home FAR_HOMES name (L5), looked up once per Situation."""
    def look() -> dict | None:
        for find in FAR_HOMES:
            try:
                home = find(s)
            except Exception as error:
                log_once(logger, "far home", error)
                continue
            if home is not None:
                return home
        return None
    return s.sensed("far home", look)


def homeward_from(s: Situation) -> float:
    """When the head_home window opens: HOMEWARD, earlier by the largest of HOMEWARD_LEADS (L5), worked
    out once per Situation."""
    def look() -> float:
        lead = 0.0
        for more in HOMEWARD_LEADS:
            try:
                lead = max(lead, float(more(s)))
            except Exception as error:
                log_once(logger, "homeward lead", error)
        return max(0.0, HOMEWARD - lead)
    return s.sensed("homeward from", look)


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
    """Wait in short steps until a trigger other than idle is pending, at most two game minutes (L4).
    Followup fix: swims for land first when Mimo is afloat (land_refuge), instead of waiting there."""
    refuge = land_refuge(s)
    if refuge is not None:
        return [refuge]
    pending = s.brain["pending"]
    if pending is not None and set(pending["reasons"]) - {"idle"}:
        return []
    chosen_at = s.brain["chosen_at"]
    if chosen_at is not None and (s.at - chosen_at) * s.scale >= REST_LONGEST:
        return []
    return [{"kind": "wait", "seconds": max(1.0, REST_STEP / s.scale)}]


register(Purpose(
    "rest", "rest", "Stay put and rest until something happens, at most two game minutes.",
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
    dusk, wait there for nightfall. After a walk there failed, sleep where Mimo stands. Followup
    fix: never lies down afloat (land_refuge) -- it swims for a known home or the nearest shore
    first, even after a failed attempt (`tried`), since that failure was land_refuge's own walk,
    not a walk to bed."""
    refuge = land_refuge(s)
    if refuge is not None:
        return [refuge]
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

def explore_valid(s: Situation) -> bool:
    """By day, while Mimo has a reason to explore and somewhere to go for it (backend.survival.trips)."""
    return not s.night and s.phase != "dusk" and best_trip(s) is not None


def explore_score(s: Situation) -> float:
    """The score of the best reason to explore (trips.best_trip), plus what lifts every trip
    (trips.LIFTS), less the late-day penalty. Fix round 1: the lift never pushes it past
    SURVIVAL_FLOOR -- a settled, maxed-out pet's trip stops short of outranking real survival work
    (eating, sleeping), the same ceiling a goal's own boost respects (goals.boosted)."""
    offer = best_trip(s)
    if offer is None:
        return 0.0
    lifted = max(offer.score, min(offer.score + lift(s), SURVIVAL_FLOOR))
    return max(0.0, lifted - late_penalty(s))


def plan_explore(s: Situation, context: ActionContext) -> list[dict]:
    """Up to three walks per choice, each to the best target for the trip's reason (trips.next_stop),
    after the reason's work where Mimo stands. A walk goes all the way or fails at once, so it
    never ends in a pit or the water."""
    stop = next_stop(s, EXPLORE_WALKS)
    if stop is None:
        return []
    work, target = stop
    return [*work, {**walk_to(target, EXPLORE_REACH), "whole": True}]


register(Purpose(
    "explore", "explore", "Go looking for something it needs, where the land likely holds it: up to three walks, "
    "never into water.",
    valid=explore_valid, facts=trip_facts, score=explore_score, plan=plan_explore,
    thoughts=("I wonder what's over there.", "Let's see what lies beyond those hills.")))


# go_home ---------------------------------------------------------------------------------------

def go_home_valid(s: Situation) -> bool:
    """Home is known and Mimo is not there, nor means to stay away (L4b: AWAY)."""
    home = home_of(s, GO_HOME_RANGE)
    return home is not None and s.distance(cell_of(home)) > AT_HOME and not away(s)


def go_home_score(s: Situation) -> float:
    if s.night or s.phase == "dusk":
        return 100.0  # beats sleep (90) by more than the utility picker's random nudge (6)
    if late_day(s):
        return 70.0 + s.trait("caution") / 10
    return 5.0 + (30.0 if s.vitals["warmth"] < 40 else 0.0)


def plan_go_home(s: Situation, context: ActionContext) -> list[dict]:
    home = home_of(s, GO_HOME_RANGE)
    if home is None or s.distance(cell_of(home)) <= AT_HOME or s.brain["batches"] >= GO_HOME_BATCHES:
        return []
    return [walk_to(cell_of(home))]


register(Purpose(
    "go_home", "go home", "Walk back to the nearest known shelter.",
    valid=go_home_valid,
    facts=lambda s: f"a shelter {round(s.distance(cell_of(home_of(s, GO_HOME_RANGE))))} blocks away",
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
