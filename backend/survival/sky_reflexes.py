"""W2: the sky's reflexes (backend.survival.reflexes), and what the storm and fog lessons make Mimo do.

- flee_fire (25): a burning cell within FIRE_FLEE blocks of Mimo (backend.survival.storms): it runs away from
  the nearest, as flee runs from a hostile (creatures.defense.run_away), and chooses again where it stops.
- take_cover (58): once a spell of weather, when a storm starts and Mimo knows `wild:storm` ("in a storm stay
  low and inside"), or fog comes and it knows `wild:fog` ("stay close to home in the fog"), and it is out under
  the open sky farther from the home it built than STORM_HOME (a storm never strikes that close) or FOG_HOME: it
  goes home, and chooses again there. Not on an expedition, and not when it is going home or to sleep already.
- In fog, a pet that knows `wild:fog` starts no trips (trips.HOLD_BACK).
A gentle pet knows both lessons from the start.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.survival import sky, trips
from backend.survival.creatures.defense import run_away
from backend.survival.light import sky_open
from backend.survival.memory import BUILT, cell_of
from backend.survival.purposes import GO_HOME_RANGE, away, home_of, walk_to
from backend.survival.reflexes import AT_HOME_WORK, Reflex, register
from backend.survival.situation import Situation
from backend.survival.storms import HOME_CLEAR, fire_near
from backend.survival.wild import unlocked

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

FIRE_FLEE = 2
STORM_HOME = HOME_CLEAR  # blocks: a storm strikes no nearer home than this
FOG_HOME = 24.0
COVER = {"storm": ("storm", STORM_HOME), "fog": ("fog", FOG_HOME)}  # weather: (its lesson, how near home is near)
SPELL_BACK = 12  # segments looked back for when a spell of weather began


def nearest_fire(s: Situation) -> tuple[int, int, int] | None:
    cells = [(entry["x"], entry["y"], entry["z"]) for entry in (s.state.get("sky") or {}).get("fires", ())]
    return min(cells, key=lambda cell: math.dist(cell, s.here)) if cells else None


def plan_flee_fire(s: Situation, context: ActionContext) -> list[dict]:
    fire = nearest_fire(s)
    return [] if fire is None else [run_away(s, fire)]


register(Reflex("flee_fire", 25, trigger=lambda s: fire_near(s.state, FIRE_FLEE), plan=plan_flee_fire,
                thought="Fire! I have to get away!", event="{name} ran from the fire.", cooldown=3.0,
                ends_purpose=True, paced=True))


def spell(s: Situation) -> int:
    """The segment the present spell of weather began in (sky.weather_at, looked back SPELL_BACK at most)."""
    offset, seed = sky.offset_of(s.state), s.seed
    segment = sky.segment_of(s.state, s.at, s.scale)
    weather = sky.weather_at(seed, offset, segment)
    start = segment
    while start > 0 and segment - start < SPELL_BACK and sky.weather_at(seed, offset, start - 1) == weather:
        start -= 1
    return start


def cover_home(s: Situation) -> dict | None:
    """The home Mimo built, when the weather's lesson sends it there now (see the module docstring)."""
    weather = sky.weather_now(s.state)
    if weather not in COVER or "born_at" not in s.state:
        return None
    lesson, near = COVER[weather]
    if not unlocked(s, lesson) or away(s) or s.brain["purpose"] in ("go_home", "sleep", *AT_HOME_WORK):
        return None
    if s.brain.get("covered") == [weather, spell(s)]:
        return None
    home = home_of(s, GO_HOME_RANGE)
    if home is None or home["note"] != BUILT or s.distance(cell_of(home)) <= near:
        return None
    return home if sky_open(s.grid, s.seed, s.here) else None


def plan_cover(s: Situation, context) -> list[dict]:
    home = cover_home(s)
    if home is None:
        return []
    s.brain["covered"] = [sky.weather_now(s.state), spell(s)]
    return [walk_to(cell_of(home))]


def fog_holds(s: Situation) -> bool:
    """trips.HOLD_BACK: no trip starts in fog for a pet that knows `wild:fog`."""
    return sky.foggy(s.state) and unlocked(s, "fog")


register(Reflex("take_cover", 58, trigger=lambda s: cover_home(s) is not None, plan=plan_cover,
                thought="The weather's turning. Home, where it's safe.", event="{name} headed home out of the weather.",
                cooldown=60.0, ends_purpose=True))
trips.HOLD_BACK.append(fog_holds)
