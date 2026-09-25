"""Explore trips with a reason (L4, from the owner: "even exploring should be purposeful").

Mimo never explores just to see the least-explored ground. Every trip has a reason, and the
reason comes from its goal or from a need: look for trees when none stands near and it needs
wood, look for food when there is none near, look for iron for its pickaxe, find leather for
armor or a creature seed for a pen, scout for flat ground for a bigger home, map the land.
Reasons are a registry: the module that knows the need registers its Reason
(backend.survival.scouting the needs; backend.survival.life_goals and backend.survival.homes
their goals'). A Reason has:
- `wanted(s)`: why Mimo wants it now, in words ("my pickaxe needs it"), or None;
- `value(s, x, z)`: how likely the land around a column holds it, from 0 to 1, and what is there
  in words ("a cave mouth"). Only the terrain is read (worldgen: biome, height, cave openings,
  rocks, trees and plants), so the same land always scores the same;
- `spots(s)`: columns to head for as they are, (x, z, words): remembered places and landmarks,
  things in sight, or the least-explored ground for the map;
- `look(s, context)`: after each walk of the trip, what Mimo sees where it stands. It remembers
  what it finds as a place or landmark and returns a Find: the words, whether it is what the trip
  was for, and whether the place is new to it;
- `work(s)`: steps to take at each stop before walking on (breaking tall grass for a seed);
- `goals`: the goals it serves; `score(s)`: explore's score with it, in the leisure band;
- `reach`: how far from home its targets may lie, LEASH (60) like every trip. L5's frontier
  hooks in here: its "seek riches farther out" will be a reason with a longer reach, offered only
  to a pet geared for the ring it leads into. L4 does not build it.

Targets (`targets`) are the reason's spots and the dry columns at 16 headings 32, 48 and 64 blocks
away whose land may hold what it needs. Each scores LIKELY times that likelihood (1 for a spot)
plus NEW times how new the land around it is (exploring.area_novelty, 0 to 1), plus exploring's
small bonus for distance and its seeded jitter. The rules that keep explore safe still hold: never
in water, never within 4 blocks of a step that just failed, never in the patch Mimo stands in, never
in one it visited less than a game day ago (spots excepted: they are where it means to go), and
with a home known, never beyond the reason's reach from it unless nearer than Mimo is now.

`offers` are the reasons wanted now that have a target, best first by the rules: a reason that
serves Mimo's goal first, then the higher score; at most OFFERED. explore (purposes.py) is on offer
only while there is one, and scores the first one's score. When explore is chosen the worker stores
the trip in the brain (backend.survival.choosing: the rules' reason, or Jev's pick among the
offers): state["brain"]["trip"] = {"reason", "words", "why", "direction", "since", "picker",
"found", "done"}, kept until the next trip (the viewer and the model see it only while Mimo
explores, `trip_view`). The tick's planner (`next_stop`) keeps to it, or picks by the rules itself
when there is none, it is done, or its reason is no longer wanted when the trip starts. Each batch
does the reason's work at a stop and walks to the best target; the walk goes all the way or not at
all. After each walk (`look_after`, from brain.observe_step) Mimo looks around. A find is logged
("Pip found birch trees.": a "found" event when the place is new to it, else a routine "explore"
one), and a find that is what the trip was for ends it (`done`) and asks for a new choice (a
"discovery"), so the purpose that follows up on it comes next: gather_wood for trees, mine_ore for
ore, hunt for animals, build_pen for a seed, improve_home for a site. A trip also ends when its
reason is no longer wanted or after three walks with nothing found. However it ends, that reason
is not offered again for a while (`cool_down`, fix round 1), the same cooldown a purpose gets after
a step fails twice: a find still needs its follow-up purpose to run before Mimo looks for the same
thing again, and a target that disappointed it needs to stop coming straight back too. A walk step
that fails outright while exploring cools its trip's reason down the same way (brain.report).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from backend.survival import nature
from backend.survival.exploring import (
    DISTANCE_BONUS, DISTANCES, EXPLORE_ROLL, FAR, HEADINGS, JITTER, LEASH, area_novelty, compass, dry_target,
    home_cell, lately, survey_text,
)
from backend.survival.grid import Cell
from backend.survival.memory import patch_of
from backend.survival.once import log_once
from backend.survival.senses import near_failure
from backend.survival.situation import Situation, in_tick
from backend.survival.triggers import ensure_brain, mark_trigger

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

LIKELY = 3.0  # a target scores this much for land sure to hold what the reason needs...
NEW = 1.0  # ...and this much for land Mimo never saw (area novelty over 9)
SPOT_SLACK = 3  # a spot's column may be this far from the dry cell Mimo stands on to see it
SHOWN = 3  # targets kept per offer: the facts and the model payload name them
OFFERED = 4  # reasons offered at a choice
# Fix round 1: a trip whose reason failed to find what it needed (its walk failed, or it used up
# every walk without a find) is not offered again this soon -- the same cooldown pattern purposes
# use after a step fails twice (brain.report, PENALTY_GAME_SECONDS), so a target that keeps
# disappointing does not send Mimo straight back to it.
TRIP_PENALTY_SECONDS = 300.0


@dataclass(frozen=True)
class Find:
    words: str  # "a cave mouth, with iron ore in its walls"
    done: bool  # it is what the trip was for
    new: bool = True  # a place or landmark Mimo did not know yet


def no_spots(s: Situation) -> list[tuple[int, int, str]]:
    return []


def no_look(s: Situation, context: ActionContext) -> Find | None:
    return None


def no_work(s: Situation) -> list[dict]:
    return []


@dataclass(frozen=True)
class Reason:
    name: str
    words: str  # completes "Pip went exploring to ...": "look for iron"
    wanted: Callable[[Situation], str | None]
    value: Callable[[Situation, int, int], tuple[float, str]]
    score: Callable[[Situation], float]
    goals: tuple[str, ...] = ()
    spots: Callable[[Situation], list[tuple[int, int, str]]] = no_spots
    look: Callable[[Situation, "ActionContext"], Find | None] = no_look
    work: Callable[[Situation], list[dict]] = no_work
    reach: float = LEASH


REASONS: dict[str, Reason] = {}
# Functions of the Situation that add to explore's score whatever its reason (L4's curiosity lifts a
# restless pet's trips into the work band).
LIFTS: list = []
# Functions of (state, Find, at) told of every find after it is logged (L4's curiosity: a place new
# to Mimo is a discovery).
FINDS: list = []


def register_reason(reason: Reason) -> Reason:
    """Add a reason, or replace the one with the same name."""
    REASONS[reason.name] = reason
    return reason


def lift(s: Situation) -> float:
    """What LIFTS add to explore's score now; one that crashes adds nothing (logged once)."""
    total = 0.0
    for extra in LIFTS:
        try:
            total += float(extra(s))
        except Exception as error:
            log_once(logger, "explore lift", error)
    return total


@dataclass(frozen=True)
class Target:
    cell: Cell
    score: float
    what: str  # "a cave mouth"
    direction: str  # "north"
    distance: int  # blocks from where Mimo stands


@dataclass(frozen=True)
class Offer:
    reason: str
    words: str
    why: str
    score: float
    targets: tuple[Target, ...]  # best first, at most SHOWN


def guarded(reason: Reason, part: str, call: Callable, fallback):
    """A reason's function; one that crashes counts as `fallback` (logged once)."""
    try:
        return call()
    except Exception as error:
        log_once(logger, f"trip reason {reason.name} {part}", error)
        return fallback


def wanted_now(s: Situation, reason: Reason) -> str | None:
    """Why Mimo wants what the reason looks for, read once per Situation; None when it does not, or
    while a trip for it failed to find what it needed lately (`cool_down`)."""
    def check() -> str | None:
        if s.brain.get("trip_penalties", {}).get(reason.name, -math.inf) > s.at:
            return None
        return guarded(reason, "wanted", lambda: reason.wanted(s), None)
    return s.sensed(f"trip wanted {reason.name}", check)


def cool_down(brain: dict, reason: str, at: float, scale: float) -> None:
    """A trip for `reason` failed to find what it needed: it is not offered again for a while (fix
    round 1; the same pattern purposes use after a step fails twice, brain.report)."""
    brain.setdefault("trip_penalties", {})[reason] = at + TRIP_PENALTY_SECONDS / scale


def beyond(s: Situation, reason: Reason, home: Cell | None, cell: Cell) -> bool:
    """Farther from home than the reason's reach, and no nearer to it than Mimo is now."""
    if home is None:
        return False
    away = math.hypot(cell[0] - home[0], cell[2] - home[2])
    return away > reason.reach and away >= math.hypot(s.here[0] - home[0], s.here[2] - home[2])


def stand_near(s: Situation, x: int, z: int) -> Cell | None:
    """A dry cell to stand on at the column, or the nearest one within SPOT_SLACK of it."""
    for dx, dz in sorted(((dx, dz) for dx in range(-SPOT_SLACK, SPOT_SLACK + 1)
                          for dz in range(-SPOT_SLACK, SPOT_SLACK + 1)), key=lambda d: (math.hypot(*d), d)):
        cell = dry_target(s.grid, s.seed, x + dx, z + dz)
        if cell is not None:
            return cell
    return None


def targets(s: Situation, reason: Reason) -> list[Target]:
    """Where the trip may head for this reason, best first (see the module docstring)."""
    def look() -> list[Target]:
        x, _, z = s.here
        here, home, turn = patch_of(x, z), home_cell(s), s.brain["explored"]
        found: dict[Cell, Target] = {}

        def add(cell: Cell, likely: float, what: str) -> None:
            distance = round(math.hypot(cell[0] - x, cell[2] - z))
            new = area_novelty(s, patch_of(cell[0], cell[2])) / 9
            jitter = JITTER * nature.roll(s.seed, (cell[0], 0, cell[2]), EXPLORE_ROLL, turn)
            score = LIKELY * min(1.0, likely) + NEW * new + DISTANCE_BONUS * distance / FAR + jitter
            if cell not in found or found[cell].score < score:
                found[cell] = Target(cell, score, what, compass(cell[0] - x, cell[2] - z), distance)

        for sx, sz, what in guarded(reason, "spots", lambda: reason.spots(s), []):
            cell = stand_near(s, sx, sz)
            if (cell is not None and patch_of(cell[0], cell[2]) != here and not near_failure(s.state, cell)
                    and not beyond(s, reason, home, cell)):
                add(cell, 1.0, what)
        for distance in (*DISTANCES, FAR):
            for heading in range(HEADINGS):
                angle = heading * 2 * math.pi / HEADINGS
                tx, tz = x + round(math.cos(angle) * distance), z + round(math.sin(angle) * distance)
                patch = patch_of(tx, tz)
                if patch == here or lately(s, patch):
                    continue
                likely, what = guarded(reason, "value", lambda: reason.value(s, tx, tz), (0.0, ""))
                if likely <= 0:
                    continue
                cell = dry_target(s.grid, s.seed, tx, tz)
                if cell is None or near_failure(s.state, cell) or beyond(s, reason, home, cell):
                    continue
                add(cell, likely, what)
        return sorted(found.values(), key=lambda target: (-target.score, target.cell))
    return s.sensed(f"trip targets {reason.name}", look)


def serves(reason: Reason, goal: str | None) -> bool:
    return goal is not None and goal in reason.goals


def offers(s: Situation) -> list[Offer]:
    """The reasons Mimo could explore for now, with their best targets, best first: one that serves
    its goal first, then the higher score."""
    def look() -> list[Offer]:
        goal = (s.brain.get("goal") or {}).get("name")
        found = []
        for reason in REASONS.values():
            why = wanted_now(s, reason)
            if why is None:
                continue
            aims = targets(s, reason)
            if aims:
                score = float(guarded(reason, "score", lambda: reason.score(s), 0.0))
                found.append(Offer(reason.name, reason.words, why, score, tuple(aims[:SHOWN])))
        found.sort(key=lambda offer: (not serves(REASONS[offer.reason], goal), -offer.score, offer.reason))
        return found[:OFFERED]
    return s.sensed("trip offers", look)


def best_trip(s: Situation) -> Offer | None:
    """The rules' reason to explore now, or None when Mimo has none (explore is not on offer)."""
    found = offers(s)
    return found[0] if found else None


def serving(s: Situation, goal: str) -> bool:
    """A trip on offer now would work toward `goal` (the goals' hook for explore: goals.ADVANCES)."""
    return any(serves(REASONS[offer.reason], goal) for offer in offers(s))


# The trip --------------------------------------------------------------------------------------

def sentence(words: str) -> str:
    return f"{words[:1].upper()}{words[1:]}."


def trip_thought(offer: Offer) -> str:
    """"Heading north to look for iron. My pickaxe needs it.\""""
    return f"Heading {offer.targets[0].direction} to {offer.words}. {sentence(offer.why)}"


def start_trip(brain: dict, offer: Offer, at: float, picker: str) -> dict:
    # Fix round 1: an explore choice that picks a fresh reason while Mimo is already exploring
    # (explore -> explore) does not change `purpose`, so apply_choice never resets `batches` --
    # without this, a fresh trip inherited the old trip's batch count and could see it already at
    # or past EXPLORE_WALKS, ending at once with nothing tried ("fails at once").
    brain["batches"] = 0
    brain["trip"] = {"reason": offer.reason, "words": offer.words, "why": offer.why,
                     "direction": offer.targets[0].direction, "since": at, "picker": picker, "found": None,
                     "done": False}
    return brain["trip"]


def next_stop(s: Situation, walks: int) -> tuple[list[dict], Cell] | None:
    """The trip's next batch: the reason's work where Mimo stands (after the first walk) and the
    target to walk to; None when the trip is over (see the module docstring)."""
    brain = s.brain
    trip = brain.get("trip")
    reason = REASONS.get(trip["reason"]) if trip else None
    if brain["batches"] == 0 and (reason is None or trip.get("done") or wanted_now(s, reason) is None):
        offer = best_trip(s)
        if offer is None:
            return None
        trip, reason = start_trip(brain, offer, s.at, "rules"), REASONS[offer.reason]
    if reason is None or trip.get("done") or brain["batches"] >= walks or wanted_now(s, reason) is None:
        if reason is not None and not trip.get("done") and brain["batches"] >= walks:
            cool_down(brain, trip["reason"], s.at, s.scale)  # every walk spent, nothing found
        return None
    aims = targets(s, reason)
    if not aims:
        return None
    work = guarded(reason, "work", lambda: reason.work(s), []) if brain["batches"] > 0 else []
    brain["explored"] += 1
    trip["direction"] = aims[0].direction
    return work, aims[0].cell


def look_after(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After a walk of an explore trip: what Mimo sees there for the trip's reason (brain.observe_step)."""
    if step.get("purpose") != "explore" or step["kind"] not in ("walk", "swim") or context.db is None:
        return
    brain = ensure_brain(state)
    trip = brain.get("trip")
    reason = REASONS.get(trip["reason"]) if trip else None
    if reason is None or trip.get("done"):
        return
    find = guarded(reason, "look", lambda: reason.look(in_tick(state, context, at), context), None)
    if find is None:
        return
    trip["found"] = find.words
    context.events.append((at, "found" if find.new else "explore", f"{state['name']} found {find.words}."))
    for hook in FINDS:
        guarded(reason, "find hook", lambda: hook(state, find, at), None)
    if find.done:
        trip["done"] = True
        mark_trigger(state, "discovery", at)
        # Fix round 1: a find that ends the trip cools its reason down too, not only a trip that
        # comes up empty -- the follow-up purpose it asks for (gather_wood for trees, and so on)
        # needs room to run once before Mimo can be sent straight back to look for the same thing
        # again, or a picker that does not always take that follow-up (a random one, or a rules
        # score it loses to something else) sends it right back on the very next choice.
        cool_down(brain, trip["reason"], at, context.clock_at(at)["time_scale"])


# What the chooser, the model and the viewer are told ---------------------------------------------

def target_words(target: Target) -> str:
    return f"{target.direction} {target.distance} blocks, {target.what}"


def trip_facts(s: Situation) -> str:
    """explore's facts: each reason with why and its best targets, the trips so far and the survey."""
    reasons = "; or ".join(f"to {offer.words} ({offer.why}): {', then '.join(target_words(t) for t in offer.targets)}"
                           for offer in offers(s))
    return f"{reasons}; {s.brain['explored']} trips so far; {survey_text(s)}"


def reasons_payload(s: Situation) -> list[dict]:
    """The reasons to explore for a model: each with why and the directions it could head, with what
    lies there."""
    return [{"reason": offer.words, "why": offer.why,
             "directions": [{"direction": target.direction, "blocks": target.distance, "toward": target.what}
                            for target in offer.targets]} for offer in offers(s)]


def trip_view(brain: dict | None) -> dict | None:
    """The trip for /api/mimo while Mimo explores: reason, words, why, direction, what it found."""
    brain = brain or {}
    trip = brain.get("trip")
    if brain.get("purpose") != "explore" or not trip:
        return None
    return {"reason": trip.get("reason"), "words": trip.get("words"), "why": trip.get("why"),
            "direction": trip.get("direction"), "found": trip.get("found")}
