"""hunt: chase an animal down for its meat (spec L1, "Hunting").

hunt picks the nearest huntable animal within 32 blocks (a passive land animal, not one within 4
blocks of where a step just failed, and (L3 final fix wave) not one more than 2 blocks below the top
of its column's natural ground: a cave animal, which led the seed-11 pet down its own stairs into a
pocket it could not climb out of) and keeps after that one: each batch either attacks it, when
it is within the attack's 2.5 blocks, or walks (all the way or not at all) to where it is now
(the same cell the cave check used, follow-up fix, the minors: a moving animal's current move can
already end in a cave it has not reached by then, and walking to that end drew Mimo down after
it), at most 40 batches. It is done when the animal is dead or has fled out of range. A hit
animal runs off (backend.survival.creatures.combat), and animals near a hunting Mimo flee now and
then (backend.survival.creatures.acts), so a hunt is a chase: hit, run after it, hit again.

It is day work, offered while an animal is in range and Mimo lacks food (foraging.food_need), or
has not killed anything for a game day (`state["hunted_at"]`), so a well-fed pet still hunts now
and then for hides, wool and feathers but never empties the land. It scores like the other food
work (foraging.hunger_score: higher the less food Mimo carries and the hungrier it is, minus the
late-day penalty) from a base of 30, and bold pets hunt a little more: bravery above 50 adds up to
5, below 50 takes up to 5 off. There is no kindness or gentleness trait, so nothing makes a pet
hunt less for being kind. L4a final fix wave, C1: only while the meat would be kept or eaten
(foraging.room_for_food), never left behind by full arms.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.services.worldgen import terrain_height
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.combat import ATTACK_REACH
from backend.survival.creatures.kinds import huntable, kind_of
from backend.survival.creatures.moves import where
from backend.survival.creatures.table import dead
from backend.survival.foraging import food_need, food_points, hunger_score, room_for_food, whole_walk
from backend.survival.once import log_once
from backend.survival.purposes import Purpose, register
from backend.survival.senses import near_failure
from backend.survival.situation import Situation
from backend.survival.steps import label

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

HUNT_SIGHT = 32.0
CAVE_DEPTH = 2  # an animal more than this far below its column's natural surface is in a cave: not prey
CHASE_REACH = 2.0  # a chase walk ends this close to where the animal's move ends
HUNT_BATCHES = 40
BASE = 30.0


def in_a_cave(cell, seed: str) -> bool:
    """More than CAVE_DEPTH blocks below the top of the column's natural ground."""
    x, y, z = (round(value) for value in cell)
    return y < terrain_height(x, z, seed) - CAVE_DEPTH


def prey(s: Situation) -> list[dict]:
    """Huntable animals within 32 blocks, nearest first, leaving out any near a failed step and any
    in a cave (in_a_cave)."""
    def look() -> list[dict]:
        herd = s.grid.herd
        if herd is None:
            return []
        x, _, z = s.here
        found = [creature for creature in herd.near(x, z, HUNT_SIGHT) if not dead(creature)
                 and huntable(kind_of(creature["kind"])) and not creature["state"].get("tame")
                 and not near_failure(s.state, where(creature, s.at)) and not in_a_cave(where(creature, s.at), s.seed)]
        return sorted(found, key=lambda creature: (s.distance(where(creature, s.at)), creature["id"]))
    return s.sensed("prey", look)


# Making (the final fix wave, I3): functions of the Situation giving the kinds a hunt goes after first
# while Mimo lacks no food (the cozy home's sheep and cows, backend.survival.cozy).
PREY_WANTED: list = []


def wanted_prey(s: Situation) -> set[str]:
    """The kinds PREY_WANTED name now; one that crashes names none (logged once)."""
    found: set[str] = set()
    for wants in PREY_WANTED:
        try:
            found.update(wants(s))
        except Exception as error:
            log_once(logger, "prey wanted", error)
    return found


def quarry(s: Situation) -> dict | None:
    """The animal this hunt is after: the nearest prey when the hunt starts (Making: the nearest of a
    kind PREY_WANTED names, when one is in range and Mimo lacks no food), then the same one while it
    lives and stays in range."""
    found = prey(s)
    if s.brain["batches"] == 0 and s.brain["replans"] == 0:
        kinds = wanted_prey(s) if found and food_need(s) <= 0 else set()
        return next((creature for creature in found if creature["kind"] in kinds), found[0] if found else None)
    chased = s.brain.get("prey")
    return next((creature for creature in found if creature["id"] == chased), None)


def hunted_lately(s: Situation) -> bool:
    """Mimo killed an animal less than a game day ago."""
    hunted_at = s.state.get("hunted_at")
    return hunted_at is not None and (s.at - hunted_at) * s.scale < DAY_SECONDS


# L4: what else makes Mimo hunt though it lacks no food, as functions of the Situation
# (backend.survival.life_goals adds hides and leather while armor is its goal).
HUNT_FOR: list = []


def hunt_for(s: Situation) -> bool:
    """One of HUNT_FOR wants a hunt now; one that crashes counts as no (logged once; the final fix
    wave guards it like harm.ARMOR_WANTED and work.EAGER)."""
    for wants in HUNT_FOR:
        try:
            if wants(s):
                return True
        except Exception as error:
            log_once(logger, "hunt for", error)
    return False


def hunt_valid(s: Situation) -> bool:
    """L4a final fix wave, C1: only while the meat would be kept or eaten (foraging.room_for_food)."""
    wanted = food_need(s) > 0 or not hunted_lately(s) or hunt_for(s)
    return not s.night and wanted and room_for_food(s, raw=True) and bool(prey(s))


def hunt_facts(s: Situation) -> str:
    nearest = prey(s)[0]
    return (f"{len(prey(s))} animals within {round(HUNT_SIGHT)} blocks, the nearest a {label(nearest['kind'])} "
            f"{round(s.distance(where(nearest, s.at)))} blocks away; carrying {round(food_points(s))} hunger of food")


def hunt_score(s: Situation) -> float:
    return hunger_score(s, BASE) + (s.trait("bravery") - 50.0) / 10


def plan_hunt(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= HUNT_BATCHES or not room_for_food(s, raw=True):
        return []
    target = quarry(s)
    s.brain["prey"] = None if target is None else target["id"]
    if target is None:
        return []
    there = where(target, s.at)
    if s.distance(there) <= ATTACK_REACH:
        return [{"kind": "attack", "creature": target["id"], "target": list(there)}]
    return [whole_walk(there, CHASE_REACH)]


register(Purpose(
    "hunt", "hunt", "Chase down an animal nearby for its meat, and hides, wool or feathers.",
    valid=hunt_valid, facts=hunt_facts, score=hunt_score, plan=plan_hunt,
    thoughts=("I could catch something to eat.", "Meat would fill me up.")))
