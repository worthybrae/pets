"""Fight or flee: the reflexes that meet hostile creatures (spec L2, "Fight and flee reflexes").

A threat is a living hostile creature that could come after Mimo: within 16 blocks and no more
than 4 above or below it, nearest first (`threats`). Inside its own shelter (a room or passage
cell of a shelter it built) Mimo has none, since nothing gets in there
(creatures.moves.steps). A weapon is a sword, or a bow with arrows.

- flee (30): a threat, and health below 35, or the nearest threat within 6 blocks and no weapon.
  Mimo runs home when the threat is no nearer its home than Mimo is (inside its shelter it is
  safe), else 12 blocks straight away from the threat. Mimo walks a block in 0.3 s, faster than
  any hostile, so it gets away; the reflex ends when the run does and fires again (2 s later)
  while the danger lasts.
- fight (40): a weapon, health 50 or more (35 or more while a fight is on, that is when it ended
  a round in the last FIGHT_KEEP seconds), and a threat within 4 blocks, or, with a bow and
  arrows, one within 12 that is after Mimo and in plain sight. Mimo shoots when the target is 5 or
  more blocks away or it has no sword, strikes with its sword in reach, and else steps up to the
  target and strikes. One blow or shot a round; the reflex fires again at once while the fight
  goes on. Below 35 health flee, being more urgent, takes over: Mimo fights, then flees.
Both log their event once per encounter (Reflex.quiet), not every round. What a model picker is
told about danger comes from here too (`threats_payload`).
"""

from __future__ import annotations

import math

from backend.services.worldgen import terrain_height
from backend.survival.actions import ActionContext, take_search
from backend.survival.creatures.archery import SHOOT_RANGE
from backend.survival.creatures.combat import ATTACK_REACH, weapon
from backend.survival.creatures.harm import ARMOR, sheltered
from backend.survival.creatures.hostiles import CHASE_RISE, CHASE_SIGHT
from backend.survival.creatures.kinds import kind_of
from backend.survival.creatures.moves import where
from backend.survival.creatures.table import dead
from backend.survival.grid import Cell, Grid
from backend.survival.memory import cell_of
from backend.survival.pathing import route
from backend.survival.purposes import home_of, underground, walk_to
from backend.survival.reflexes import Reflex, register
from backend.survival.situation import Situation

FLEE_BELOW = 35.0
FLEE_NEAR = 6.0
FLEE_RUN = 12  # blocks straight away from the threat when home is no refuge
FLEE_REACH = 4.0  # the run may end this close to where it heads
FIGHT_FROM = 50.0
FIGHT_REACH = 4.0
SHOOT_FROM = 5.0  # blocks from which Mimo shoots rather than strikes
BOW_SIGHT = 12.0  # blocks within which Mimo shoots at a hostile coming after it
CLOSE_IN = 2.0  # a step up to the target ends this close to it
STEP_UP_LIMIT = 2 * FIGHT_REACH  # cells a step-up route may cover; farther is left for the bow or another round
FIGHT_KEEP = 3.0  # server seconds after a round in which the fight is still on
QUIET = 30.0  # server seconds after the reflex ended during which a new round logs no event
THREATS_SHOWN = 4


def indoors(s: Situation) -> bool:
    """Mimo stands in a room or passage cell of a shelter it built."""
    return s.db is not None and s.grid.claimed(s.here) and sheltered(s.db, s.here)


def threats(s: Situation) -> list[dict]:
    """Living hostiles that could come after Mimo, nearest first; none while it is indoors."""
    def look() -> list[dict]:
        herd = s.grid.herd
        if herd is None or indoors(s):
            return []
        x, y, z = s.here
        found = []
        for creature in herd.near(x, z, CHASE_SIGHT):
            kind = kind_of(creature["kind"])
            if kind is not None and kind.hostile and not dead(creature) \
                    and abs(where(creature, s.at)[1] - y) <= CHASE_RISE:
                found.append(creature)
        return sorted(found, key=lambda creature: (s.distance(where(creature, s.at)), creature["id"]))
    return s.sensed("threats", look)


def threats_payload(s: Situation) -> dict:
    """What a model is told about danger (L2): `threats`, the hostiles that could come after Mimo
    (nearest first, at most THREATS_SHOWN, and whether each is after it), and `defense`: whether
    Mimo is safe indoors, its best sword, its arrows (with a bow), the armor it wears and the kind
    of creature that hurt it last."""
    shown = [{"kind": creature["kind"], "distance": round(s.distance(where(creature, s.at))),
              "after_mimo": bool(creature["state"].get("chasing"))} for creature in threats(s)[:THREATS_SHOWN]]
    defense = {"indoors": indoors(s), "sword": weapon(s.inventory),
               "arrows": s.count("arrow") if s.count("bow") else 0,
               "armor": [piece for piece in ARMOR if s.count(piece)], "last_hurt_by": s.state.get("hurt_by")}
    return {"threats": shown, "defense": defense}


def bow_ready(s: Situation) -> bool:
    return s.count("bow") > 0 and s.count("arrow") > 0


def armed(s: Situation) -> bool:
    return weapon(s.inventory) is not None or bow_ready(s)


def clear_line(grid: Grid, start: Cell, end: Cell) -> bool:
    """Nothing solid between two cells: points every half block along the line are checked."""
    samples = max(1, int(math.dist(start, end) * 2))
    for index in range(1, samples):
        share = index / samples
        cell = tuple(round(a + (b - a) * share) for a, b in zip(start, end))
        if cell not in (start, end) and grid.solid(cell):
            return False
    return True


# flee ------------------------------------------------------------------------------------------

def flee_due(s: Situation) -> bool:
    found = threats(s)
    if not found:
        return False
    close = s.distance(where(found[0], s.at)) <= FLEE_NEAR
    return s.vitals["health"] < FLEE_BELOW or (close and not armed(s))


def plan_flee(s: Situation, context: ActionContext) -> list[dict]:
    """Home when Mimo is not already safe there and the threat is no nearer it than Mimo, else
    FLEE_RUN blocks straight away. `not indoors(s)` holds whenever this runs at all (a threat was
    found, and threats() finds none while indoors), so this only turns away a home whose refuge
    cell Mimo already occupies; it is what keeps a doorway (claimed but not itself a room or
    passage, and so AT_HOME blocks from a shelter built on the small tier) from being skipped."""
    danger = where(threats(s)[0], s.at)
    home = home_of(s)
    if home is not None and not indoors(s):
        refuge = cell_of(home)
        if math.dist(danger, refuge) >= s.distance(refuge):
            return [walk_to(refuge)]
    x, y, z = s.here
    dx, dz = x - danger[0], z - danger[2]
    length = math.hypot(dx, dz) or 1.0
    tx, tz = round(x + dx / length * FLEE_RUN), round(z + dz / length * FLEE_RUN)
    ty = y if underground(s) else terrain_height(tx, tz, s.seed) + 1
    return [{"kind": "walk", "target": [tx, ty, tz], "reach": FLEE_REACH}]


register(Reflex("flee", 30, trigger=flee_due, plan=plan_flee, thought="Run! Get away from it!",
                event="{name} ran from a creature.", cooldown=2.0, quiet=QUIET))


# fight -----------------------------------------------------------------------------------------

def fight_target(s: Situation) -> dict | None:
    """The hostile Mimo fights now, or None (see the module docstring)."""
    if not armed(s):
        return None
    fighting = s.at - s.brain["reflex_ends"].get("fight", -math.inf) <= FIGHT_KEEP
    if s.vitals["health"] < (FLEE_BELOW if fighting else FIGHT_FROM):
        return None
    for creature in threats(s):
        there = where(creature, s.at)
        distance = s.distance(there)
        if distance <= FIGHT_REACH and clear_line(s.grid, s.here, there):
            return creature
        if (bow_ready(s) and distance <= BOW_SIGHT and creature["state"].get("chasing")
                and clear_line(s.grid, s.here, there)):
            return creature
    return None


def plan_fight(s: Situation, context: ActionContext) -> list[dict]:
    target = fight_target(s)
    if target is None:
        return []
    there = where(target, s.at)
    distance = s.distance(there)
    blow = {"creature": target["id"], "target": list(there)}
    sword = weapon(s.inventory)
    if bow_ready(s) and (distance >= SHOOT_FROM or sword is None) and distance <= SHOOT_RANGE:
        return [{"kind": "shoot", **blow}]
    if sword is None:
        return []
    if distance <= ATTACK_REACH:
        return [{"kind": "attack", **blow}]
    # fight_target already checked line of sight; still bound the walk itself, so a target the
    # straight line clears but the ground does not (a pit, a long way round) is left for later
    # rather than marched to across the map (take_search: this shares the tick's search budget).
    if not take_search(context):
        return []
    cells, reached = route(s.grid, s.here, there, CLOSE_IN)
    if not reached or len(cells) > STEP_UP_LIMIT:
        return []
    return [{"kind": "walk", "target": list(there), "reach": CLOSE_IN}, {"kind": "attack", **blow}]


register(Reflex("fight", 40, trigger=lambda s: fight_target(s) is not None, plan=plan_fight,
                thought="Stay back! I'm not afraid of you.", event="{name} stood its ground against a creature.",
                cooldown=0.0, quiet=QUIET))
