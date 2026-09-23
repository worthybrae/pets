"""Choosing a purpose: the utility picker, thoughts and what a model is told.

`options(s)` lists the purposes on offer with their facts and utility scores; a purpose that
failed twice in the last 10 game minutes scores 30 lower. The utility picker takes the best score
after a small random nudge (0 to 6), so Mimo does not always do the same thing. Thoughts come
from each purpose's templates. `context_payload(s, events)` is what Jev and Luna see: name,
traits, mood, vitals, phase, day, inventory, known places, the last 8 events and the trigger.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass

from backend.survival.memory import cell_of
from backend.survival.once import log_once
from backend.survival.purposes import PURPOSES, offered
from backend.survival.situation import Situation

logger = logging.getLogger(__name__)

JITTER = 6.0
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
        found.append(Option(purpose.name, purpose.phrase, purpose.description, facts, score))
    return found


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
    }
