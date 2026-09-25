"""Expeditions (L4b, the owner's day-17 note: "I want it to be more curious and constantly exploring").

When Mimo is curious enough (CURIOUS_ENOUGH or more: curiosity.GROUND_FLOOR, pre-flight 2), its
needs are met (`ready`: all but hunger will do when it
carries READY_FOOD of food, as at dawn) and it has rested REST_DAYS game days since the last one,
the expedition goal is on offer (after first_shelter; it repeats). Its rules score is 40 plus 0.8
of curiosity, RESTLESS_PULL more once restless, so a restless pet with its needs met sets out rather
than settle into its routine. An expedition goes:
1. Pack food and torches: PACK_FOOD hunger of food (foraging.MORE_FOOD asks the food purposes for
   the rest), PACK_TORCHES torches (none when there is no coal to be had: none carried and no coal
   ore mine_ore could go back for) and a campfire, or the logs and sticks for one (made at camp when
   Mimo's arms have no room for it now). The `pack` purpose makes the torches and the campfire from
   what Mimo carries (60, work band); mine_ore fetches coal and gather_wood logs. From packing until
   it is home again, build_storage and drop_items leave the torches and the food be
   (storage.KEEPS_MORE).
2. Travel past the lands it knows. Packed, by day, Mimo sets out (a notable "expedition" event):
   the explored range is the distance from home within which nine in ten of the patches it visited
   lie (RANGE_MIN to RANGE_MAX), the target that plus PAST (at most REACH_MAX from home), and the
   heading the compass way with the most dry land it never visited just past the range. The
   "expedition" trip (explore) heads out that way and beyond the range, up to REACH_MAX from home;
   once past the target it roams the land beyond the range every way, mapping and studying what it
   finds until it is time to camp (explore and investigate work toward the camp until the night).
3. Camp out for the night. On the way out, and on the way back when dusk finds it farther than
   FAR_FROM_HOME from home, Mimo stays out (`away`, in purposes.AWAY): go_home and the head_home
   reflex leave it be, and build_shelter starts no new home out there. It digs in for the night
   (backend.survival.camp). A night slept farther than FAR_FROM_HOME from home counts, camp or not,
   and Mimo wakes up knowing whether it turns home.
4. Map new ground: MAP_WALKS walks onto ground it never walked (the journal's investigate is on
   offer as ever, and works toward the expedition too).
5. Come home with its finds. By day, after a night out once it reached the target and mapped its
   walks, or after NIGHTS_OUT nights, or at once when short of food (under LOW_FOOD carried and
   hungry) or health (under LOW_HEALTH), it turns home; `come_home` (75) walks it back, and it
   camps again should dusk catch it far out. Home, it logs what it found (an "expedition" event:
   how far out, the nights camped, the new things learned) and the goal is reached.
The expedition is kept in state["brain"]["expedition"]: {"since" (the goal's), "phase" ("packing",
"out", "homeward", "home"), "home", "range", "target", "heading", "direction", "far", "nights",
"walks", "lessons", "left_at", "camp", "slept"}; it ends when the goal is reached or set aside
(brain["expedition_at"] then says when). `tend_expedition` (brain.notice_step) moves it on and
`observe_expedition` (brain.observe_step) counts its walks and nights; a crash in either is logged
once and the tick goes on.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, terrain_height
from backend.survival import foraging, purposes, storage
from backend.survival.clock import DAY_SECONDS
from backend.survival.carrying import GIVES_WAY_TO_FOOD, crafts_fit, full
from backend.survival.curiosity import GROUND_FLOOR, RESTLESS, needs_met, value_of
from backend.survival.exploring import COMPASS
from backend.survival.goals import Goal, Milestone, active, register_goal
from backend.survival.grid import Cell
from backend.survival.home import built_home, home_cell
from backend.survival.memory import PATCH, explored, known, patch_of
from backend.survival.once import log_once
from backend.survival.purposes import (
    AT_HOME, Purpose, late_day, register, walk_to,
)
from backend.survival.situation import Situation, in_tick
from backend.survival.steps import as_cell
from backend.survival.toolmaking import Short, make
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.trips import WANDER_PENALTY_SECONDS, Reason, register_reason
from backend.survival.work import ore_targets

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

GOAL = "expedition"
REST_DAYS = 2.0  # game days between the end of one expedition and the offer of the next
RESTLESS_PULL = 110.0
PACK_FOOD = 90.0  # hunger points of food packed: a day and a half
PACK_TORCHES = 4
RANGE_MIN, RANGE_MAX = 48.0, 144.0
PAST = 48.0
REACH_MAX = 200.0
FAR_FROM_HOME = 48.0  # farther than this from home, dusk finds Mimo camping, not heading home
NIGHTS_OUT = 2
MAP_WALKS = 8
LOW_FOOD = 20.0
LOW_HEALTH = 40.0
HOME_REACH = 6.0
COME_HOME_BATCHES = 6
READY_FOOD = 30.0  # hunger of food carried that counts as fed enough to set out
# Pre-flight 2 (the pacing ruling): the curiosity from which an expedition is on offer. New ground
# alone never takes curiosity below curiosity.GROUND_FLOOR, so a pet at the floor or above is one
# nothing new has sated lately. Measured over hatch and chooser seeds 2, 3, 5, 7, 8, 9, 11, 13 and 21
# for 8 game days: from 60 (CURIOUS) 4 of the 9 set out and the days tests' pet (seed 8) never did,
# from 50 6 did (not seed 8), from 40 all 9 did.
CURIOUS_ENOUGH = GROUND_FLOOR


# The expedition --------------------------------------------------------------------------------

def home_built(s: Situation) -> Cell | None:
    """The home Mimo built, from the one home lookup (backend.survival.home), or None."""
    return home_cell(s) if built_home(s) else None


def trek(s: Situation) -> dict | None:
    """The expedition under way: the brain's, while the expedition is Mimo's goal."""
    goal, found = s.brain.get("goal"), s.brain.get("expedition")
    if not goal or goal["name"] != GOAL or not found or found.get("since") != goal["since"]:
        return None
    return found


def phase_of(s: Situation) -> str | None:
    found = trek(s)
    return None if found is None else found["phase"]


def from_home(s: Situation, cell: Cell | None = None) -> float:
    found = trek(s)
    home = found["home"] if found else home_built(s)
    if home is None:
        return 0.0
    x, _, z = cell or s.here
    return math.hypot(x - home[0], z - home[2])


def camp_time(s: Situation) -> bool:
    return s.night or late_day(s)


def away(s: Situation) -> bool:
    """Mimo means to stay out: on the way out, or caught far from home by dusk on the way back."""
    phase = phase_of(s)
    if phase == "out":
        return True
    return phase == "homeward" and camp_time(s) and from_home(s) > FAR_FROM_HOME


purposes.AWAY.append(away)


def explored_range(db, home: Cell) -> float:
    """The distance from home within which nine in ten of the patches Mimo visited lie."""
    found = explored(db, home, REACH_MAX)
    distances = sorted(math.hypot(rx * PATCH + PATCH / 2 - home[0], rz * PATCH + PATCH / 2 - home[2])
                       for rx, rz in found)
    if not distances:
        return RANGE_MIN
    return min(RANGE_MAX, max(RANGE_MIN, distances[int(0.9 * (len(distances) - 1))]))


def heading_of(db, seed: str, home: Cell, reach: float) -> int:
    """The compass way (an index into exploring.COMPASS) with the most dry land Mimo never visited
    just past `reach` from home."""
    found = explored(db, home, reach + PAST + PATCH)
    best = (-1, 0)
    for index in range(len(COMPASS)):
        new = 0
        for spread in (-0.35, 0.0, 0.35):
            angle = index * math.pi / 4 + spread
            for distance in (reach + 16, reach + 32, reach + PAST):
                x, z = home[0] + round(math.cos(angle) * distance), home[2] + round(math.sin(angle) * distance)
                new += patch_of(x, z) not in found and terrain_height(x, z, seed) >= SEA_LEVEL
        if new > best[0]:
            best = (new, index)
    return best[1]


def start_trek(s: Situation) -> dict:
    goal = s.brain["goal"]
    found = {"since": goal["since"], "phase": "packing", "home": None, "range": None, "target": None,
             "heading": None, "direction": None, "far": 0.0, "nights": 0, "walks": 0, "lessons": 0,
             "left_at": None, "camp": None, "slept": None}
    s.brain["expedition"] = found
    return found


def packed_food(s: Situation) -> float:
    return foraging.food_points(s)


def coal_known(s: Situation) -> bool:
    """Mimo carries coal, or remembers coal ore mine_ore could go back for: it can have torches."""
    return s.count("coal") > 0 or any(place["note"] == "coal_ore" for place in ore_targets(s))


def no_room_for_torches(s: Situation) -> bool:
    """Mimo cannot make its torches for want of room (the craft would not fit in its arms, or its
    arms are full and it is short of what makes them) and build_storage has nothing to put away to
    make room (no chest yet, say): it goes without them, as with no coal to be had, rather than pack
    for good (the pre-flight's seed 7 packed for a game day with 17 stacks and no chest)."""
    if s.count("torch") >= PACK_TORCHES or storage.storage_valid(s):
        return False
    trial, steps = dict(s.inventory), []
    try:
        make(trial, "torch", PACK_TORCHES, steps)
    except Short:
        return full(s.inventory)
    return not crafts_fit(s.inventory, steps)


def torches_packed(s: Situation) -> float:
    """How far along the torches are: PACK_TORCHES of them, or none at all when there is no coal to be
    had or no room for them (`no_room_for_torches`)."""
    if not coal_known(s) or no_room_for_torches(s):
        return 1.0
    return min(1.0, s.count("torch") / PACK_TORCHES)


def campfire_ready(s: Situation) -> bool:
    """A campfire carried, or what makes one (2 logs and 3 sticks, of any wood): Mimo makes it at camp
    when its arms have no room for it now."""
    if s.count("campfire") >= 1:
        return True
    try:
        make(dict(s.inventory), "campfire", 1, [])
    except Short:
        return False
    return True


def packed(s: Situation) -> bool:
    return packed_food(s) >= PACK_FOOD and torches_packed(s) >= 1.0 and campfire_ready(s)


def set_out(state: dict, s: Situation, found: dict, context: ActionContext, at: float) -> None:
    home = home_built(s)
    reach = explored_range(s.db, home)
    heading = heading_of(s.db, s.seed, home, reach)
    found.update(phase="out", home=list(home), range=round(reach), target=round(min(REACH_MAX, reach + PAST)),
                 heading=heading, direction=COMPASS[heading], left_at=at, lessons=len(known(s.db, "lesson")))
    context.events.append((at, "expedition", f"{state['name']} set out on an expedition to the {COMPASS[heading]}."))
    state["last_thought"] = f"Off to the {COMPASS[heading]}, past everything I know!"
    mark_trigger(state, "goal", at)


def homeward(state: dict, found: dict, at: float) -> None:
    found["phase"] = "homeward"
    state["last_thought"] = "Time to head home and tell... well, to remember it all."
    mark_trigger(state, "goal", at)


def come_home(state: dict, s: Situation, found: dict, context: ActionContext, at: float) -> None:
    found["phase"] = "home"
    learned = len(known(s.db, "lesson")) - found["lessons"]
    context.events.append((at, "expedition", f"{state['name']} came home from its expedition: {round(found['far'])} "
                           f"blocks out, {found['nights']} night{'s' if found['nights'] != 1 else ''} camped, "
                           f"{learned} new thing{'s' if learned != 1 else ''} learned."))
    ensure_brain(state)["expedition_at"] = at
    mark_trigger(state, "goal", at)


def tend_expedition(state: dict, context: ActionContext, at: float) -> None:
    """After a vitals step (brain.notice_step): start, move on or end the expedition."""
    if context.db is None or state.get("died_at") is not None:
        return
    try:
        s = in_tick(state, context, at)
        brain = s.brain
        goal = brain.get("goal")
        if not goal or goal["name"] != GOAL:
            if brain.get("expedition"):
                if brain["expedition"].get("phase") != "home":
                    brain["expedition_at"] = at
                brain.pop("expedition")
            return
        found = trek(s) or start_trek(s)
        phase = found["phase"]
        if phase == "packing" and packed(s) and not camp_time(s) and home_built(s) is not None:
            set_out(state, s, found, context, at)
        elif phase in ("out", "homeward"):
            found["far"] = max(found["far"], from_home(s))
            if phase == "out" and should_turn(s, found):
                homeward(state, found, at)
            elif phase == "homeward" and from_home(s) <= HOME_REACH:
                come_home(state, s, found, context, at)
    except Exception as error:
        log_once(logger, "expedition", error)


def should_turn(s: Situation, found: dict) -> bool:
    if packed_food(s) < LOW_FOOD and s.vitals["hunger"] < 50 or s.vitals["health"] < LOW_HEALTH:
        return True
    if camp_time(s):
        return False
    return found["nights"] >= NIGHTS_OUT or (found["nights"] >= 1 and found["far"] >= found["target"]
                                              and found["walks"] >= MAP_WALKS)


def observe_expedition(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After a finished step (brain.observe_step): walks onto new ground, nights slept out, and the
    camp's roof going on."""
    brain = ensure_brain(state)
    found = brain.get("expedition")
    goal = brain.get("goal")
    if not found or not goal or goal["name"] != GOAL or found.get("phase") not in ("out", "homeward"):
        return
    try:
        kind = step["kind"]
        if kind in ("walk", "swim") and brain.get("new_ground_at") == at:
            found["walks"] += 1
        elif kind == "sleep":
            home = found["home"]
            x, _, z = as_cell(state["position"])
            if math.hypot(x - home[0], z - home[2]) > FAR_FROM_HOME:
                found["nights"] += 1
                found["slept"] = at
                if found["phase"] == "out" and should_turn(in_tick(state, context, at), found):
                    homeward(state, found, at)  # at once, so the morning's first choice heads home
    except Exception as error:
        log_once(logger, "expedition steps", error)


# The goal --------------------------------------------------------------------------------------

def rested(s: Situation) -> bool:
    last = s.brain.get("expedition_at")
    return last is None or (s.at - last) * s.scale >= REST_DAYS * DAY_SECONDS


def expedition_valid(s: Situation) -> bool:
    if home_built(s) is None:
        return False
    current = active(s)
    if current is not None and current.name == GOAL:
        return True
    return value_of(s.brain) >= CURIOUS_ENOUGH and ready(s) and rested(s)


def ready(s: Situation) -> bool:
    """Its needs are met (curiosity.needs_met), or would be but for hunger while it carries a meal's
    worth of food (READY_FOOD): at dawn a pet is often hungry with its breakfast in its pack."""
    if needs_met(s.state, s.db):
        return True
    fed = s.state["vitals"]["hunger"]
    return (packed_food(s) >= READY_FOOD and fed >= 25.0
            and needs_met({**s.state, "vitals": {**s.state["vitals"], "hunger": 100.0}}, s.db))


def expedition_score(s: Situation) -> float:
    curiosity = value_of(s.brain)
    return 40.0 + 0.8 * curiosity + (RESTLESS_PULL if curiosity >= RESTLESS else 0.0)


def pack_share(s: Situation) -> float:
    if phase_of(s) in ("out", "homeward", "home"):
        return 1.0
    return (min(1.0, packed_food(s) / PACK_FOOD) + torches_packed(s) + float(campfire_ready(s))) / 3


def travel_share(s: Situation) -> float:
    found = trek(s)
    if not found or not found["target"]:
        return 0.0
    return min(1.0, found["far"] / found["target"])


def camp_share(s: Situation) -> float:
    found = trek(s)
    return 1.0 if found and found["nights"] >= 1 else 0.0


def map_share(s: Situation) -> float:
    found = trek(s)
    return min(1.0, found["walks"] / MAP_WALKS) if found else 0.0


def home_share(s: Situation) -> float:
    return 1.0 if phase_of(s) == "home" else 0.0


register_goal(Goal(
    GOAL, "An expedition",
    "Pack food and torches, travel past the lands it knows, camp out and come home with what it found.",
    (Milestone("Pack food and torches", pack_share,
               ("pack", "forage", "fish", "hunt", "cook", "gather_wood", "mine_ore")),
     Milestone("Travel past the lands it knows", travel_share, ("explore",)),
     Milestone("Camp out for the night", camp_share, ("camp", "explore", "investigate")),
     Milestone("Map new ground", map_share, ("explore", "investigate")),
     Milestone("Come home with its finds", home_share, ("come_home",))),
    score=expedition_score, thought="I want to see what lies past the lands I know. Pack up, let's go!",
    after=("first_shelter",), valid=expedition_valid, reward=20.0, repeat=True))


def more_food(s: Situation) -> float:
    """While packing, Mimo wants PACK_FOOD of food on hand, not just a day's worth."""
    return max(0.0, PACK_FOOD - foraging.FOOD_WANTED) if phase_of(s) == "packing" else 0.0


foraging.MORE_FOOD.append(more_food)


def packed_kept(s: Situation, item: str) -> float:
    """What an expedition keeps on Mimo (storage.KEEPS_MORE): its torches and its food, from packing
    until it is home again. While it packs it keeps none of what gives way to food
    (carrying.GIVES_WAY_TO_FOOD: plants, gloom dust, wool, string, feathers, flint, hides, leather,
    copper and gold), so build_storage puts that in the chest at home and the pack has room: the
    pre-flight found arms full on 97-100 % of the packing ticks of three of five packing pets."""
    phase = phase_of(s)
    if phase not in ("packing", "out", "homeward"):
        return 0.0
    if phase == "packing" and item in GIVES_WAY_TO_FOOD:
        return -float(storage.KEEP.get(item, 0))
    return {"torch": PACK_TORCHES, "food": PACK_FOOD - foraging.FOOD_WANTED}.get(item, 0.0)


storage.KEEPS_MORE.append(packed_kept)


# pack ------------------------------------------------------------------------------------------

def pack_steps(s: Situation) -> list[dict]:
    """Craft steps for the torches and the campfire an expedition takes, as far as Mimo can make them
    and has room to carry them (carrying.crafts_fit)."""
    trial, steps = dict(s.inventory), []
    wanted = [("torch", count) for count in range(s.count("torch") + 1, PACK_TORCHES + 1)]
    for item, count in wanted + ([("campfire", 1)] if s.count("campfire") < 1 else []):
        attempt, more = dict(trial), []
        if attempt.get(item, 0) >= count:
            continue
        try:
            make(attempt, item, count, more)
        except Short:
            continue
        if crafts_fit(s.inventory, steps + more):
            trial, steps = attempt, steps + more
    return steps


def pack_valid(s: Situation) -> bool:
    return phase_of(s) == "packing" and not s.night and bool(pack_steps(s))


register(Purpose(
    "pack", "pack for the expedition", "Make the torches and the campfire an expedition takes.",
    valid=pack_valid, facts=lambda s: (f"carrying {s.count('torch')} of {PACK_TORCHES} torches, "
                                       f"{s.count('campfire')} campfire, {round(packed_food(s))} of "
                                       f"{round(PACK_FOOD)} hunger of food"),
    score=lambda s: 60.0, plan=lambda s, context: [] if s.brain["batches"] > 0 else pack_steps(s),
    thoughts=("Torches, a campfire, food... what else?", "Packing up for the trip!")))


# The expedition trip ---------------------------------------------------------------------------

def heading_off(found: dict, x: int, z: int) -> float:
    """How far (radians) the column lies from the expedition's heading, seen from home."""
    home = found["home"]
    angle = math.atan2(z - home[2], x - home[0])
    return abs((angle - found["heading"] * math.pi / 4 + math.pi) % (2 * math.pi) - math.pi)


def trek_wanted(s: Situation) -> str | None:
    return "I want to see what lies past the lands I know" if phase_of(s) == "out" else None


def trek_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    found = trek(s)
    if found is None:
        return 0.0, ""
    away_now, there = from_home(s), from_home(s, (x, 0, z))
    off = heading_off(found, x, z)
    if there > found["range"] and (off <= 0.55 * math.pi or found["far"] >= found["target"]):
        return (1.0 if off <= math.pi / 3 or found["far"] >= found["target"] else 0.5), "land past what it knows"
    if there > away_now and off <= math.pi / 3:
        return 0.4, "the way out"
    return 0.0, ""


# The expedition trip ends with nothing "found" after its walks, like wander, so it has wander's short
# cooldown (L4a's per-reason cooldown), and out past RANGE_MIN from home, the least an explored range
# can be, that cooldown does not hold (`roams_from`, as wander's), so it never holds past the range.
register_reason(Reason(
    "expedition", "travel past the lands it knows", trek_wanted, trek_value, lambda s: 65.0,
    goals=(GOAL,), reach=REACH_MAX, cooldown=WANDER_PENALTY_SECONDS, roams_from=RANGE_MIN))


# come_home -------------------------------------------------------------------------------------

def come_home_valid(s: Situation) -> bool:
    return phase_of(s) == "homeward" and not away(s) and from_home(s) > HOME_REACH


def plan_come_home(s: Situation, context: ActionContext) -> list[dict]:
    found = trek(s)
    if found is None or s.brain["batches"] >= COME_HOME_BATCHES or from_home(s) <= HOME_REACH:
        return []
    return [walk_to(tuple(found["home"]), AT_HOME)]


register(Purpose(
    "come_home", "come home from its expedition", "Walk back home from an expedition with what it found.",
    valid=come_home_valid, facts=lambda s: f"{round(from_home(s))} blocks from home",
    score=lambda s: 75.0, plan=plan_come_home,
    thoughts=("Home, with so much to remember.", "I can't wait to be home again.")))


# What the viewer and the model are told --------------------------------------------------------

def expedition_view(brain: dict | None) -> dict | None:
    """The expedition for /api/mimo while one is under way: {phase, direction, far, target, nights}."""
    brain = brain or {}
    found, goal = brain.get("expedition"), brain.get("goal")
    if not found or not goal or goal.get("name") != GOAL or found.get("since") != goal.get("since"):
        return None
    return {"phase": found["phase"], "direction": found.get("direction"), "far": round(found.get("far") or 0.0),
            "target": found.get("target"), "nights": found.get("nights", 0),
            "camping": brain.get("purpose") == "camp"}
