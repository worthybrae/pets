"""Choosing a purpose: the utility picker, thoughts and what a model is told.

`options(s)` lists the purposes on offer with their facts and utility scores; a purpose that
failed twice in the last 10 game minutes scores 30 lower. The utility picker takes the best score
after a small random nudge (0 to 6), so Mimo does not always do the same thing. Thoughts come
from each purpose's templates. `context_payload(s, events)` is what Jev and Luna see: name,
traits, mood, vitals, phase, day, inventory, known places, the last 8 events, the trigger, what
Mimo built or could build (M5), how much of the land around it it has explored, and (L2) the
hostile creatures near it and what it can meet them with. L4: the options follow Mimo's goal
(`steer`, with the rules in backend.survival.goals), and the payload carries the goal.
Explore's option carries its reasons to explore, the rules' pick first (backend.survival.trips);
the payload says what a trip would look for and where, the trip Mimo is on, and how curious it is.
L4b: it also carries the journal (how many lessons Mimo learned, the newest, what it could study
near it) and the expedition under way.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, replace

from backend.survival.building import building_payload
from backend.survival.creatures.defense import threats_payload
from backend.survival.curiosity import curiosity_view
from backend.survival.expedition import expedition_view
from backend.survival.exploring import exploration_payload
from backend.survival.goals import active, boosted, goal_payload, meets_need, toward
from backend.survival.journal import journal_payload
from backend.survival.memory import cell_of
from backend.survival.once import log_once
from backend.survival.purposes import PURPOSES, offered
from backend.survival.rings import ring_payload
from backend.survival.situation import Situation
from backend.survival.trips import offers, reasons_payload, trip_view

logger = logging.getLogger(__name__)

JITTER = 6.0
NUDGE_TOP = 15.0  # Mind M2: points the nudges move one purpose's score, either way, at most
PENALTY = 30.0
PLACES_SHOWN = 12
EVENTS_SHOWN = 8


@dataclass(frozen=True)
class Option:
    name: str
    phrase: str
    description: str
    facts: str
    score: float
    goal: str = ""  # L4: the title of the goal it works toward, if any
    reasons: tuple = ()  # L4: explore's reasons (trips.Offer), the rules' pick first


def options(s: Situation) -> list[Option]:
    """Every purpose on offer with its facts and score. One whose facts or score crash is left out."""
    found = []
    for purpose in offered(s):
        try:
            facts, score = purpose.facts(s), float(purpose.score(s))
        except Exception as error:
            log_once(logger, f"{purpose.name} facts", error)
            continue
        if s.brain["penalties"].get(purpose.name, -math.inf) > s.at:
            score -= PENALTY
        score += nudged(s, purpose.name)
        reasons = tuple(offers(s)) if purpose.name == "explore" else ()
        found.append(Option(purpose.name, purpose.phrase, purpose.description, facts, score, reasons=reasons))
    return steer(s, found)


# [nudge(s, purpose name) -> points]: small, bounded pulls on a purpose's score (Mind M2's thoughts:
# backend.survival.nudges), NUDGE_TOP either way in all.
NUDGES: list = []


def nudged(s: Situation, name: str) -> float:
    """The nudges' points for a purpose, within NUDGE_TOP either way. One that crashes counts nothing."""
    points = 0.0
    for nudge in NUDGES:
        try:
            points += float(nudge(s, name))
        except Exception as error:
            log_once(logger, "nudge", error)
    return max(-NUDGE_TOP, min(NUDGE_TOP, points))


def steer(s: Situation, found: list[Option]) -> list[Option]:
    """L4: the options with Mimo's goal in mind (backend.survival.goals). The ones that advance the goal
    (or, while it waits, another open goal: goals.toward) are marked with its title and score more
    (goals.boosted). While any option advances a goal or meets a need, only those are offered: the
    others, rest and explore among them, would be capped in the leisure band anyway, and leaving them
    out keeps a model's pick on the goal too. Otherwise every option keeps its own score. Without a
    goal, the options are as found."""
    if active(s) is None:
        return found
    aim = toward(s, {option.name for option in found})
    title, advancing = (aim[0].title, aim[1]) if aim else ("", frozenset())
    steered = [replace(option, score=boosted(s, option.score), goal=title) if option.name in advancing else option
               for option in found]
    focused = [option for option in steered if option.goal or meets_need(s, option.name, option.score)]
    return focused or steered


def utility_pick(choices: list[Option], rng: random.Random) -> str:
    """The best score after a random nudge of up to JITTER."""
    return max(choices, key=lambda option: option.score + rng.uniform(0, JITTER)).name


def thought_for(name: str, rng: random.Random) -> str:
    purpose = PURPOSES.get(name)
    if purpose is None or not purpose.thoughts:
        return f"Time to {name.replace('_', ' ')}."
    return rng.choice(purpose.thoughts)


def context_payload(s: Situation, events: list[dict]) -> dict:
    """What a model is told about Mimo when it chooses. `events` are newest first."""
    known = sorted(s.places, key=lambda place: math.dist(cell_of(place), s.here))[:PLACES_SHOWN]
    pending = s.brain["pending"]
    return {
        "name": s.state["name"],
        "traits": dict(s.state.get("traits", {})),
        "mood": round(s.vitals["mood"]),
        "vitals": {name: round(value) for name, value in s.vitals.items()},
        "phase": s.phase,
        "day": s.clock["day_number"],
        "inventory": dict(s.inventory),
        "known_places": [{"kind": place["kind"], "note": place["note"],
                          "distance": round(math.dist(cell_of(place), s.here))} for place in known],
        "recent_events": [event["text"] for event in events[:EVENTS_SHOWN]],
        "trigger": list(pending["reasons"]) if pending else [],
        # M5: home, what Mimo built and what it could build now, with the blocks it is short of.
        "building": building_payload(s),
        # How much of the land near Mimo it has seen, which way the new land lies, what it found
        # and how long since it last set foot on new ground (backend.survival.exploring).
        "exploration": exploration_payload(s),
        # L2: the hostile creatures that could come after Mimo, and how it can meet them.
        **threats_payload(s),
        # L5: the danger ring Mimo stands in, how far from home, the deepest ring it is ready for and
        # what it lacks for the next one.
        "frontier": ring_payload(s),
        # L4: the goal Mimo works toward, how far along it is and what comes next (or None).
        "goal": goal_payload(s),
        # L4: what an explore trip would go looking for, why, and which ways it could head (with what
        # lies there); and the trip Mimo is on, if it is exploring.
        "explore_reasons": reasons_payload(s),
        "trip": trip_view(s.brain),
        # L4: how curious Mimo is and how it feels about it ("restless; nothing new for 2 game days").
        "curiosity": curiosity_view(s.brain, s.at, s.scale),
        # L4b: what Mimo learned and could study near it, and the expedition it is on (or None).
        "journal": journal_payload(s),
        "expedition": expedition_view(s.brain),
    }
