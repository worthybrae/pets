"""Fight or flee: the reflexes that meet hostile creatures (spec L2, "Fight and flee reflexes").

A threat is a living hostile creature that could come after Mimo: within 16 blocks and no more
than THREAT_RISE (2) above or below it, nearest first (`threats`; final fix wave: what lives in a
cave 3 or more blocks under Mimo's feet cannot get at it, so it is no reason to run). Inside its
own shelter (a room or passage cell of a shelter it built) Mimo has none, since nothing gets in
there (creatures.moves.steps); L4b's sealed camp is the same shelter for a night out
(backend.survival.camp: a remembered outpost cell with the roof cell above it solid). A weapon is
a sword, or a bow with arrows.

- flee (30): a threat, and health below 35, or the nearest threat within 6 blocks and no weapon
  (while a flight is on -- it ended a run in the last FLEE_KEEP action seconds -- the flight goes
  on for as long as that nearest threat is still chasing Mimo and within hostiles.GIVE_UP, not a
  fixed distance: followup fix, it used to stop at 8 blocks while a roused hostile keeps coming to
  24, so Mimo often "escaped" only to be walked down again and again). Mimo runs to the home it
  built when that is no nearer the threat than Mimo is and Mimo is not already on it (inside its
  shelter it is safe), else 12 blocks away from the threat: straight away, or, when a run that way
  failed lately (the far end takes its height from the generated ground, so it can be out of
  reach) or would land it in or on water (senses.afloat; followup fix: flights used to run Mimo
  out over open water and strand it there), turned aside by 45 then 90 degrees. A home Mimo only
  found (a sheltered spot) keeps nothing out, so it is no refuge. Mimo walks a block in 0.3 s,
  faster than any hostile, so it gets away; the reflex ends when the run does (within FLEE_REACH
  of its far end), ends the purpose too (a set-aside sleep is not lain down again beside the
  threat) and fires again FLEE_COOLDOWN later, in action time, while the danger lasts. Followup
  fix: sleep and rest never start while Mimo stands in water either (purposes.land_refuge), since a
  flight can still leave it there even when its own target never does.
- fight (40): a weapon, health 50 or more (35 or more while a fight is on, that is when it ended
  a round in the last FIGHT_KEEP seconds, or when a hostile after Mimo has it at bay, within
  ATTACK_REACH), and a threat within 4 blocks, or, with a bow and arrows, one within 12 that is
  after Mimo and in plain sight. Mimo shoots when the target is 5 or more blocks away or it has
  no sword, strikes with its sword in reach, and else steps up to the target and strikes. One
  blow or shot a round; the reflex fires again at once while the fight goes on. Below 35 health
  flee, being more urgent, takes over: Mimo fights, then flees.
Both log their event once per encounter (Reflex.quiet), not every round. What a model picker is
told about danger comes from here too (`threats_payload`).
"""

from __future__ import annotations

import math

from backend.services.blocks import is_solid
from backend.services.worldgen import terrain_height
from backend.survival.actions import ActionContext
from backend.survival.creatures.archery import SHOOT_RANGE
from backend.survival.creatures.combat import ATTACK_REACH, weapon
from backend.survival.creatures.harm import ARMOR, sheltered
from backend.survival.creatures.hostiles import CHASE_SIGHT, GIVE_UP
from backend.survival.creatures.kinds import hostile_kinds, kind_of
from backend.survival.creatures.moves import where
from backend.survival.creatures.table import dead
from backend.survival.grid import Cell, Grid
from backend.survival.memory import BUILT, cell_of
from backend.survival.pathing import route
from backend.survival.purposes import home_of, underground, walk_to
from backend.survival.reflexes import Reflex, register
from backend.survival.senses import afloat, near_failure
from backend.survival.situation import Situation

FLEE_BELOW = 35.0
FLEE_NEAR = 6.0
# Followup fix: while a flight is on (it ended a run in the last FLEE_KEEP action seconds), it
# goes on for as long as the nearest threat is still chasing Mimo and within hostiles.GIVE_UP
# (`chasing_near`), not a fixed distance -- the final fix wave stopped it at FLEE_CLEAR (8) blocks
# while a roused hostile keeps coming to 24, so Mimo often stopped only to be walked down again.
# FLEE_KEEP is action seconds, paced by MIMO_ACTION_SCALE like the cooldown below (Situation.
# action_scale), not the game clock, so the hysteresis means the same span of real running whether
# or not time_scale and action_scale agree.
FLEE_KEEP = 3.0
FLEE_RUN = 12  # blocks away from the threat when home is no refuge
# The run may end this close to where it heads: 10.5 of the 12 blocks at least, so each run
# widens the gap to a skitter (0.4 s a block against Mimo's 0.3) by at least 2.6 blocks. Not 0,
# since the far end itself can be a tree trunk or a boulder; 1.5 takes any cell around it.
FLEE_REACH = 1.5
# Seconds of action time (divided by MIMO_ACTION_SCALE: the reflex is paced) before the next run:
# a skitter closes 1.25 blocks meanwhile, well under what the last run gained.
FLEE_COOLDOWN = 0.5
FLEE_TURNS = (0.0, 45.0, -45.0, 90.0, -90.0)  # degrees off straight away, when a run that way failed lately
FIGHT_FROM = 50.0
FIGHT_REACH = 4.0
SHOOT_FROM = 5.0  # blocks from which Mimo shoots rather than strikes
BOW_SIGHT = 12.0  # blocks within which Mimo shoots at a hostile coming after it
CLOSE_IN = 2.0  # a step up to the target ends this close to it
STEP_UP_LIMIT = 2 * FIGHT_REACH  # cells a step-up route may cover; farther is left for the bow or another round
# Cells the step-up's look ahead may expand: every cell within STEP_UP_LIMIT moves on flat ground
# is under 150, and a route it cannot find within this is too long a way round anyway.
STEP_UP_NODES = 256
FIGHT_KEEP = 3.0  # server seconds after a round in which the fight is still on
QUIET = 30.0  # server seconds after the reflex ended during which a new round logs no event
THREATS_SHOWN = 4
# Final fix wave: blocks above or below Mimo a threat may be. A hostile chases from up to 4
# (hostiles.CHASE_RISE) and the tick keeps its short steps for one that close, but one 3 or more
# below is in a cave under Mimo's feet, not on its way; it counts once it has climbed to 2.
# Followup fix: the HUD's DANGER_RISE (frontend/src/survival/hud.ts) mirrors this value, so its
# on-screen warning agrees with what actually raises a threat here.
THREAT_RISE = 2


def sealed_camp(s: Situation) -> bool:
    """Mimo stands in a camp it dug in and roofed over (backend.survival.camp): a remembered
    outpost cell with the roof cell above it solid. Fix round 1, Minor 1: without this, an unarmed
    pet sleeping in a sealed camp re-fired flee at every hostile within CHASE_SIGHT, its walk out
    always failing (six solid walls), breaking sleep every few seconds."""
    x, y, z = s.here
    return (is_solid(s.grid.material(x, y + 1, z))
            and any(place["kind"] == "outpost" and cell_of(place) == s.here for place in s.places))


def indoors(s: Situation) -> bool:
    """Mimo stands in a room or passage cell of a shelter it built, or in a sealed camp it dug in
    for the night (Fix round 1, Minor 1: sealed_camp)."""
    return (s.db is not None and s.grid.claimed(s.here) and sheltered(s.db, s.here)) or sealed_camp(s)


def threats(s: Situation) -> list[dict]:
    """Living hostiles that could come after Mimo, nearest first; none while it is indoors."""
    def look() -> list[dict]:
        herd = s.grid.herd
        if herd is None or indoors(s):
            return []
        x, y, z = s.here
        found = []
        for creature in herd.near(x, z, CHASE_SIGHT, kinds=hostile_kinds()):
            kind = kind_of(creature["kind"])
            if kind is not None and kind.hostile and not dead(creature) \
                    and abs(where(creature, s.at)[1] - y) <= THREAT_RISE:
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

def fleeing(s: Situation) -> bool:
    """A flight is on: Mimo ended a run in the last FLEE_KEEP action seconds -- paced by
    MIMO_ACTION_SCALE like the cooldown (reflexes.reflex_hook), not multiplied by the game clock's
    time_scale, so the two agree on what "a moment ago" means even when the scales differ."""
    return s.at - s.brain["reflex_ends"].get("flee", -math.inf) <= FLEE_KEEP / s.action_scale


def chasing_near(s: Situation, radius: float) -> dict | None:
    """The nearest living hostile within `radius` blocks (and THREAT_RISE up or down) that is still
    after Mimo (its own "chasing" state), or None. Followup fix: `threats` only looks CHASE_SIGHT
    (16) blocks out, but a roused hostile keeps coming to hostiles.GIVE_UP (24); this is how
    `flee_due` keeps a flight going that far instead of stopping at CHASE_SIGHT and leaving Mimo to
    be walked down again by a hostile that never gave up."""
    herd = s.grid.herd
    if herd is None or indoors(s):
        return None
    x, y, z = s.here
    found = [creature for creature in herd.near(x, z, radius, kinds=hostile_kinds())
             if _still_chasing(creature, s, y)]
    return min(found, key=lambda creature: s.distance(where(creature, s.at))) if found else None


def _still_chasing(creature: dict, s: Situation, y: int) -> bool:
    kind = kind_of(creature["kind"])
    return (kind is not None and kind.hostile and not dead(creature) and bool(creature["state"].get("chasing"))
            and abs(where(creature, s.at)[1] - y) <= THREAT_RISE)


def flee_threat(s: Situation, found: list[dict]) -> dict | None:
    """The hostile flee is about: the nearest of `found` (threats' CHASE_SIGHT sight and THREAT_RISE
    height), or, once a flight is already on and it has fallen out of that sight, the nearest still
    chasing Mimo out to hostiles.GIVE_UP (`chasing_near`) -- the one a flight already under way keeps
    running from instead of stopping the moment `threats` loses sight of it. None once nothing is
    close enough (or still coming) to run from."""
    if found:
        return found[0]
    return chasing_near(s, GIVE_UP) if fleeing(s) else None


def flee_due(s: Situation) -> bool:
    found = threats(s)
    if s.vitals["health"] < FLEE_BELOW:
        return flee_threat(s, found) is not None
    if armed(s):
        return False
    if not fleeing(s):
        return bool(found) and s.distance(where(found[0], s.at)) <= FLEE_NEAR
    chaser = next((creature for creature in found if creature["state"].get("chasing")), None)
    return (chaser if chaser is not None else chasing_near(s, GIVE_UP)) is not None


def run_away(s: Situation, danger: Cell) -> dict:
    """A walk FLEE_RUN blocks away from `danger`: straight away, or the first of FLEE_TURNS whose
    far end is not where a step failed lately (senses.near_failure) and would not land Mimo in or
    on water (senses.afloat; followup fix: a flight used to run out over open water and strand Mimo
    there). Straight away again when every one fails both; a dry one that failed lately still beats
    a wet one that has not."""
    x, y, z = s.here
    away = math.atan2(z - danger[2], x - danger[0])  # +x when the threat is right above or below
    walks = []
    for turn in FLEE_TURNS:
        heading = away + math.radians(turn)
        tx, tz = round(x + math.cos(heading) * FLEE_RUN), round(z + math.sin(heading) * FLEE_RUN)
        ty = y if underground(s) else terrain_height(tx, tz, s.seed) + 1
        walk = {"kind": "walk", "target": [tx, ty, tz], "reach": FLEE_REACH}
        walks.append(walk)
        if not near_failure(s.state, (tx, ty, tz)) and not afloat(s.grid, (tx, ty, tz)):
            return walk
    dry = next((walk for walk in walks if not afloat(s.grid, tuple(walk["target"]))), None)
    return dry if dry is not None else walks[0]


def plan_flee(s: Situation, context: ActionContext) -> list[dict]:
    """Home when Mimo built it, is not already on it or safe inside, and the threat is no nearer it
    than Mimo; else a run away (run_away). A found home (a sheltered spot Mimo made home) keeps
    nothing out, and a walk to the cell Mimo stands on ends at once, so neither is a refuge (final
    fix wave: flee kept "running" to Mimo's own cell while it was struck). `not indoors(s)` holds
    whenever this runs at all (a threat was found, and threats() finds none while indoors); it is
    what keeps a doorway (claimed but not itself a room or passage, and so AT_HOME blocks from a
    shelter built on the small tier) from being skipped. Followup fix: the threat can be one
    `threats()` no longer sees (flee_threat, once a flight already on has run it out past
    CHASE_SIGHT); [] on the rare tick where even that finds nothing (the hook re-triggers next tick
    from a fresh Situation, so this never wedges flee_due and plan_flee apart for long)."""
    threat = flee_threat(s, threats(s))
    if threat is None:
        return []
    danger = where(threat, s.at)
    home = home_of(s)
    if home is not None and home["note"] == BUILT and not indoors(s):
        refuge = cell_of(home)
        if s.distance(refuge) > 0.5 and math.dist(danger, refuge) >= s.distance(refuge):
            return [walk_to(refuge)]
    return [run_away(s, danger)]


register(Reflex("flee", 30, trigger=flee_due, plan=plan_flee, thought="Run! Get away from it!",
                event="{name} ran from a creature.", cooldown=FLEE_COOLDOWN, ends_purpose=True, quiet=QUIET,
                paced=True))


# fight -----------------------------------------------------------------------------------------

def fight_target(s: Situation) -> dict | None:
    """The hostile Mimo fights now, or None (see the module docstring). Final fix wave: at 35 to
    49 health a hostile after Mimo that has it at bay (within ATTACK_REACH) is fought too, since
    neither reflex fired there and a skitter, faster than Mimo's short runs could shake, struck it
    down to the flee line unanswered."""
    health = s.vitals["health"]
    if not armed(s) or health < FLEE_BELOW:
        return None
    fighting = s.at - s.brain["reflex_ends"].get("fight", -math.inf) <= FIGHT_KEEP
    for creature in threats(s):
        there = where(creature, s.at)
        distance = s.distance(there)
        at_bay = distance <= ATTACK_REACH and bool(creature["state"].get("chasing"))
        if health < FIGHT_FROM and not (fighting or at_bay):
            continue
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
    # rather than marched to across the map. Final fix wave: this look ahead is bounded to
    # STEP_UP_NODES cells (a few ms at most) and no longer spends one of the tick's searches, which
    # the walk itself spends: it used to cost a fight step's walks two searches a step up.
    cells, reached = route(s.grid, s.here, there, CLOSE_IN, max_nodes=STEP_UP_NODES)
    if not reached or len(cells) > STEP_UP_LIMIT:
        return []
    return [{"kind": "walk", "target": list(there), "reach": CLOSE_IN}, {"kind": "attack", **blow}]


register(Reflex("fight", 40, trigger=lambda s: fight_target(s) is not None, plan=plan_fight,
                thought="Stay back! I'm not afraid of you.", event="{name} stood its ground against a creature.",
                cooldown=0.0, quiet=QUIET))
