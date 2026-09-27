"""Risk against reward (L5, "Frontier"): a geared pet goes farther out for riches, and comes home.

- The frontier goal, "Riches farther out": open to a pet with a home it built that is geared for the
  far wilds (rings.gear_short_of: a stone sword or better, or a bow and 8 arrows, and leather armor
  or better) while an old ruin whose chest it never opened stands in a ring it is geared for, past the
  near wilds and within FRONTIER_REACH of home. An ungeared pet never has it. It repeats (goals.Goal
  .repeat): its milestones count from when it was set: reach the far wilds, open an old ruin's chest,
  come home to home ground with the loot; once a chest is open it stays open until Mimo is home.
  go_home advances it only with the loot, and loot_ruin only for a ruin past the near wilds
  (goals.ADVANCES), so a pet working toward another goal meanwhile is not sent home or to a near
  ruin in its name. Rules score: 40 plus a fifth of bravery and a tenth of curiosity (40 to 70).
- The "seek riches farther out" trip (trips.Reason "riches"): wanted only while that is Mimo's goal
  and no chest is opened yet, only when Mimo is ready for the ring (rings.ready_ring: the gear, 70
  health and half a day's food for the far wilds) and only with time to walk out to the farthest a
  trip may go (`reach_limit`) and back before the homeward window (`homeward_from`). Its land: a spot
  near an old ruin in a ring Mimo is ready for is sure ("an old ruin in the far wilds, danger 2");
  other land past home ground 0.2, and up to 0.8 more the nearer such a ruin lies (over RUIN_PULL
  blocks: the pull that sends the trip its way; a first version gave all the far wilds 0.6, and a pet
  whose ruins lay the other way walked four trips without finding one, measured on seed 11); nothing
  at all in a ring deeper than Mimo is ready for, so no trip ever leads a pet past its readiness. The
  ruins within RUIN_SPOTS blocks are its spots. Its reach from home is FRONTIER_REACH (480: the
  frontier's far edge, for a pet ready for it). A ruin in sight after a walk is the find; loot_ruin
  (backend.survival.ruins) follows up.
- No trip of any reason heads into the frontier or deeper while Mimo is not ready for it, nor within
  EDGE (16) blocks of it (trips.FENCES). The L5 final fix wave (I4): nor does any walk. The fence reflex (a
  veto) refuses a walk that would take Mimo past that limit (`reach_limit`), farther from home than it
  stands, so gathering wood, fishing or a camp's walk to its spot plans again or gives up; and out past
  the limit, turn_back walks Mimo back EDGE inside it, on the line home, before anything else (a camp then
  digs in inside). A flight or a fight is the one exception: both are more urgent, and turn_back takes Mimo
  back once they end. A camp dug in for the night is left alone; old ruins (ruins.ruin_targets) and ores
  (work.reachable_ores, since mine_ore remembers no refused spot) past the limit are no targets. On the
  final review's gate gathering wood,
  fishing and wandering took three pets that were not ready for it into the frontier, and one camped there.
- Riches come home (the L5 final fix wave, I2): at an old chest, stacks of blocks Mimo carries make room for
  the riches in it (ruins.room_for_riches), and an opened chest that still holds riches is a target again,
  for the goal and its trip; taking riches from one counts as opening one. On the final review's gate 42 %
  of the far chests' gold and amber was still in them on day 150.
- Heading home before dark: from the far wilds on, the head_home window opens earlier by the walk
  home (purposes.HOMEWARD_LEADS: 0.45 game seconds a block at the normal pace, plus a game minute), and
  "late in the day" with it (purposes.late_day), so go_home scores 70 and more and outdoor work 30 less
  from then on: a head_home walk that a fight cut short is not lost to the next choice (measured: a
  pet 340 blocks out hurried home four times, each walk cut by a thornback and followed by farming),
  and the home Mimo built stays home however far it is (purposes.FAR_HOMES), so go_home and head_home
  find it however far out it is (L4a's follow-up lets them look from any distance too), and so does
  everything else that asks purposes.home_of, past its 128 blocks. A flight far from home runs away from
  the threat rather than all the way home (the refuge is only a home within 128 blocks, as before L5).
- What a model is told: the ring Mimo stands in, how far from home, the deepest ring it is ready for
  and what it lacks for the next (`frontier` in the payload, rings.ring_payload); each riches target
  names its ring and danger, and loot_ruin's facts the ruin's ring.
"""

from __future__ import annotations

import math

from backend.survival.actions import as_started, fail
from backend.survival.creatures.hostiles import enclosed
from backend.survival.goals import ADVANCES, Goal, Milestone, register_goal
from backend.survival.home import built_home, home_place
from backend.survival.life_goals import whole
from backend.survival.memory import places
from backend.survival.pathing import WALK_SECONDS
from backend.survival.purposes import FAR_HOMES, HOMEWARD_LEADS, homeward_from, late_day, walk_to
from backend.survival.reflexes import Reflex, register as register_reflex
from backend.survival.rings import (
    ANNOUNCED_FROM, DEEPEST, OPEN_RINGS, RINGS, center, distance_home, gear_short_of, ready_ring, ring_at, ring_here,
    ring_name,
)
from backend.survival.ruins import RUIN, RUIN_SIGHT, holds_riches, opened, ruin_targets, ruins_near
from backend.survival.situation import Situation
from backend.survival.steps import as_cell
from backend.survival.trips import FENCES, Find, Reason, register_reason, stand_near

FRONTIER_REACH = 480.0  # blocks from home a riches trip may go: the frontier's far edge
RUIN_SPOTS = 80.0  # ruins this close to Mimo are spots of the riches trip (a whole walk reaches them)
RUIN_NEAR = 16.0  # a column this close to an unopened ruin is sure to hold riches
DETOUR = 1.5  # a walk home is this many times the straight line
LEAD_SLACK = 60.0  # game seconds more, to be home before the window closes
EDGE = 16.0  # blocks inside the outer edge of the deepest ring Mimo may go into that every trip keeps to
RUIN_PULL = 240.0  # an unopened ruin draws a riches trip from this far: its pull falls from 1 beside it to 0 here


def since(s: Situation) -> float | None:
    goal = s.brain.get("goal") or {}
    return goal.get("since") if goal.get("name") == "frontier" else None


def geared_ring(s: Situation) -> int:
    """The deepest ring Mimo's weapons and armor alone are fit for (health and food aside)."""
    ring = OPEN_RINGS
    for deeper in range(OPEN_RINGS + 1, DEEPEST + 1):
        if gear_short_of(s, deeper):
            break
        ring = deeper
    return ring


def ring_limit(ring: int) -> float:
    """How far from home a trip may head for a pet ready for `ring`: EDGE short of that ring's outer edge
    (the far wilds' at least: 240 blocks), so a winding walk to a target stays inside it."""
    ready = max(ring, ANNOUNCED_FROM)
    return RINGS[ready + 1][2] - EDGE if ready < DEEPEST else math.inf


def unopened_ruins(s: Situation, deepest: int) -> list[tuple[int, int, int]]:
    """Ruins past the near wilds and no deeper than `deepest`, whose chest Mimo never opened (or, the L5 final fix
    wave, I2: opened, but it still holds riches), inside `ring_limit(deepest)` (the L5 final fix wave, I4: no walk
    goes past it; they used to count out to RUIN_NEAR past it, as far as Mimo could see from inside) and within
    FRONTIER_REACH of home. On the final review's gate 42 % of the far chests' gold and amber was left in them:
    once a chest was open, no riches trip went back to it."""
    def look() -> list[tuple[int, int, int]]:
        middle = center(s.state)
        if middle is None:
            return []
        reach = min(FRONTIER_REACH, ring_limit(deepest))  # the L5 final fix wave, I4: no walk goes past it
        return [chest for chest in ruins_near(s.seed, middle[0], middle[1], reach)
                if ANNOUNCED_FROM <= ring_at(s.state, chest[0], chest[2]) <= deepest
                and (not opened(s, chest) or holds_riches(s, chest))]
    return s.sensed(f"unopened ruins {deepest}", look)


def frontier_valid(s: Situation) -> bool:
    """Geared for the far wilds or deeper, with a home it built, and an unopened ruin out there -- or,
    while riches are its goal, a chest opened already: the goal stays open until Mimo is home with the
    loot (a first version closed it the moment the last chest out there was opened, and the goal was
    set aside before Mimo came home)."""
    ring = geared_ring(s)
    return built_home(s) and ring > OPEN_RINGS and (opened_since(s) or bool(unopened_ruins(s, ring)))


def reached_far(s: Situation) -> bool:
    at = since(s)
    far_at = (s.state.get("frontier") or {}).get("far_at")
    return at is not None and far_at is not None and far_at >= at


def opened_since(s: Situation) -> bool:
    """Mimo opened the chest of a ruin past the near wilds since riches became its goal, or (the L5 final fix wave,
    I2) took riches out of one opened before (ruins.note_opened notes it "looted")."""
    at = since(s)
    return at is not None and any(max((place["data"] or {}).get("opened", -math.inf),
                                      (place["data"] or {}).get("looted", -math.inf)) >= at
                                  and ring_at(s.state, place["x"], place["z"]) >= ANNOUNCED_FROM
                                  for place in ruin_places(s))


def ruin_places(s: Situation) -> list[dict]:
    """Every ruin Mimo remembers, however far (Situation.places reads only those within 256 blocks on
    each axis, and a frontier ruin lies farther from home), read once per Situation."""
    return s.sensed("ruin places", lambda: places(s.db, (RUIN,)) if s.db is not None else [])


def home_with_loot(s: Situation) -> bool:
    return opened_since(s) and ring_here(s.state) == 0


def pull(s: Situation) -> float:
    return 40.0 + s.trait("bravery") / 5 + s.trait("curiosity") / 10


def homeward_with_loot(s: Situation, goal: Goal) -> bool:
    """go_home advances the frontier goal only with the loot (goals.ADVANCES): before that, going home
    is no step toward riches, and a pet working on another goal meanwhile is not sent home for it."""
    return goal.name != "frontier" or opened_since(s)


def looting_far(s: Situation, goal: Goal) -> bool:
    """loot_ruin advances the frontier goal only for a ruin past the near wilds (goals.ADVANCES)."""
    if goal.name != "frontier":
        return True
    targets = ruin_targets(s)
    return bool(targets) and ring_at(s.state, targets[0][0], targets[0][2]) >= ANNOUNCED_FROM


ADVANCES["go_home"] = homeward_with_loot
ADVANCES["loot_ruin"] = looting_far

register_goal(Goal(
    "frontier", "Riches farther out",
    "Past the near wilds old ruins stand with chests nobody opened, and what lives out there drops gold and amber.",
    (Milestone("Reach the far wilds", lambda s: whole(reached_far(s)), ("explore",)),
     Milestone("Open an old ruin's chest", lambda s: whole(opened_since(s)), ("loot_ruin", "explore")),
     Milestone("Come home from an old ruin", lambda s: whole(home_with_loot(s)), ("go_home",))),
    score=pull, thought="Old ruins stand out in the far wilds. I'm armed and ready for them.",
    after=("first_shelter",), valid=frontier_valid, repeat=True))


# The riches trip -------------------------------------------------------------------------------

def walk_seconds(s: Situation, blocks: float) -> float:
    """Game seconds Mimo takes to walk `blocks`, the way round included, at the pace the clock and the steps
    share (MIMO_TIME_SCALE and MIMO_ACTION_SCALE are set alike: 1 and 1, or 60 and 60 for the demo). Pre-flight:
    this was scaled by s.scale / s.action_scale, but the Chooser's Situations (situation.from_db) do not know the
    action scale and read it as 1, so at 60x the Chooser thought every walk home 60 times longer."""
    return blocks * WALK_SECONDS * DETOUR


def riches_wanted(s: Situation) -> str | None:
    """While riches are Mimo's goal and no chest is open yet, ready for the ring and with the daylight
    to walk out and back."""
    ready = ready_ring(s)
    if since(s) is None or opened_since(s) or ready <= OPEN_RINGS or s.night or late_day(s):
        return None
    out_and_back = 2 * min(reach_limit(s), FRONTIER_REACH)  # blocks, at the farthest the trip may go
    if s.clock["seconds_into_day"] + walk_seconds(s, out_and_back) + LEAD_SLACK > homeward_from(s):
        return None
    return f"old ruins stand out there, and I'm ready for the {ring_name(ready).lower()}"


def danger_words(ring: int) -> str:
    return f"the {ring_name(ring).lower()}, danger {ring}"


def riches_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    """Sure beside an unopened ruin in a ring Mimo is ready for; elsewhere past home ground, 0.2 and up to
    0.8 more the nearer such a ruin (its pull, over RUIN_PULL blocks), so the trip heads its way; nothing
    in a ring deeper than Mimo is ready for, or on home ground."""
    ready, ring = ready_ring(s), ring_at(s.state, x, z)
    if ring > ready or ring < OPEN_RINGS:
        return 0.0, ""  # never past what Mimo is ready for
    near = min((math.hypot(chest[0] - x, chest[2] - z) for chest in unopened_ruins(s, ready)), default=math.inf)
    if near <= RUIN_NEAR:
        return 1.0, f"an old ruin in {danger_words(ring)}"
    pull = max(0.0, 1.0 - near / RUIN_PULL)
    where = danger_words(ring) if ring > OPEN_RINGS else "the near wilds, the way out"
    return 0.2 + 0.8 * pull, (f"toward an old ruin, {where}" if pull > 0 else where)


def riches_spots(s: Situation) -> list[tuple[int, int, str]]:
    x, _, z = s.here
    return [(chest[0], chest[2], f"an old ruin in {danger_words(ring_at(s.state, chest[0], chest[2]))}")
            for chest in unopened_ruins(s, ready_ring(s)) if math.hypot(chest[0] - x, chest[2] - z) <= RUIN_SPOTS]


def riches_look(s: Situation, context) -> Find | None:
    x, _, z = s.here
    ready = ready_ring(s)
    for chest in ruins_near(s.seed, x, z, RUIN_SIGHT):
        ring = ring_at(s.state, chest[0], chest[2])
        if (ANNOUNCED_FROM <= ring <= ready and (not opened(s, chest) or holds_riches(s, chest))
                and s.grid.material(*chest) == "chest"):
            return Find(f"an old ruin in {danger_words(ring)}", True, new=False)
    return None


register_reason(Reason(
    "riches", "seek riches farther out", riches_wanted, riches_value, lambda s: 50.0 + s.trait("bravery") / 10,
    goals=("frontier",), spots=riches_spots, look=riches_look, reach=FRONTIER_REACH))


# Home before dark ------------------------------------------------------------------------------

def far_lead(s: Situation) -> float:
    """Game seconds the head_home window opens early from the far wilds on: the walk home and a minute."""
    if ring_here(s.state) < ANNOUNCED_FROM:
        return 0.0
    return walk_seconds(s, distance_home(s.state)) + LEAD_SLACK


def far_home(s: Situation) -> dict | None:
    """The home Mimo built, from the far wilds on, past purposes.home_of's own reach (128 blocks; going
    home looks from any distance since L4a's follow-up)."""
    if ring_here(s.state) < ANNOUNCED_FROM or not built_home(s):
        return None
    return home_place(s)


HOMEWARD_LEADS.append(far_lead)
FAR_HOMES.append(far_home)


def reach_limit(s: Situation) -> float:
    """How far from home any trip may head: `ring_limit` of the deepest ring Mimo is ready for."""
    return ring_limit(ready_ring(s))


def past_readiness(s: Situation, cell) -> bool:
    """No trip, whatever its reason, heads into the frontier or deeper while Mimo is not ready for that
    ring, nor within EDGE of it (trips.FENCES). Out near the far wilds' edge, L4a's reasons may head
    anywhere no farther from home than Mimo stands, and a walk winds round what is in its way: a geared
    pet drifted past 256 blocks on a wander and on a riches trip to a ruin at the edge (measured, seeds
    11 and 8). The far wilds stay open to the riches trip's own rule and to L4b's expeditions."""
    middle = center(s.state)
    return middle is not None and math.hypot(cell[0] - middle[0], cell[2] - middle[1]) > reach_limit(s)


FENCES.append(past_readiness)


# One fence for every walk (the L5 final fix wave, I4) ------------------------------------------------------

TURN_BACK_EVERY = 10.0  # game seconds (the cooldown is paced) before turn_back may take over again
TURN_BACK_REACH = 2.0


def from_centre(s: Situation, cell) -> float:
    middle = center(s.state)
    return math.inf if middle is None else math.hypot(cell[0] - middle[0], cell[2] - middle[1])


def next_walk(s: Situation) -> dict | None:
    """The walk running now, or the walk about to start (nothing running, first in the queue)."""
    action = s.state.get("action")
    if action is not None:
        return action if action["kind"] == "walk" else None
    queue = s.state.get("queue") or []
    return queue[0] if queue and queue[0].get("kind") == "walk" else None


def heading_out(s: Situation) -> bool:
    """From inside its limit, a walk would take Mimo past it (`past_readiness`), farther from home than it stands:
    gathering wood, fishing, a camp's walk to its spot, any walk but an escape's (and a flight's or a fight's,
    which this reflex never cuts into: they are more urgent). Past the limit already, turn_back takes it back."""
    walk = next_walk(s)
    if walk is None or walk.get("keep") == "escape" or past_readiness(s, s.here):
        return False
    target = as_cell(walk["target"])
    return past_readiness(s, target) and from_centre(s, target) > from_centre(s, s.here)


def plan_fence(s: Situation, context) -> list[dict]:
    """Refuse the walk: it fails, blocked, so the purpose plans again (the failed spot is left alone a while:
    senses.near_failure) or, failing twice, gives up and scores lower for a while (brain.report)."""
    action = s.state.get("action")
    reason = "that is farther out than it is ready to go"
    if action is not None:
        fail(s.state, action, s.at, reason, "blocked")
    else:
        fail(s.state, as_started(s.state["queue"].pop(0), s.at), s.at, reason, "blocked")
    return list(s.state["queue"])  # the plan's cleanup steps, which fail() kept


def past_limit(s: Situation) -> bool:
    """Mimo stands past its limit, not dug in for the night (a camp's first walk in the morning takes it back),
    and no walk under way or next takes it back inside."""
    if not past_readiness(s, s.here) or enclosed(s.grid, s.here):
        return False
    walk = next_walk(s)
    return walk is None or past_readiness(s, as_cell(walk["target"]))


def plan_turn_back(s: Situation, context) -> list[dict]:
    """Walk back to EDGE inside the limit, on the line home (a dry cell there to stand on, when there is one)."""
    middle = center(s.state)
    x, y, z = s.here
    share = max(0.0, reach_limit(s) - EDGE) / max(from_centre(s, s.here), 1.0)
    column = (round(middle[0] + (x - middle[0]) * share), round(middle[1] + (z - middle[1]) * share))
    cell = stand_near(s, *column) or (column[0], y, column[1])
    return [walk_to(cell, TURN_BACK_REACH)]


register_reflex(Reflex(
    "fence", 45, trigger=heading_out, plan=plan_fence, thought="That's farther out than I'm ready for.",
    event="{name} turned back at the edge of where it is ready to go.", cooldown=0.0, veto=True))
register_reflex(Reflex(
    "turn_back", 55, trigger=past_limit, plan=plan_turn_back, thought="Too far out for me. Back a little.",
    event="{name} turned back toward home: it is not ready to go that far.", cooldown=TURN_BACK_EVERY,
    ends_purpose=True, quiet=30.0, paced=True))
