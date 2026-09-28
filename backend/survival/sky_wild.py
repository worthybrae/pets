"""W2: what a wild pet learns of the weather and the seasons alone (knocks) and by asking (wonders), as W1's
lessons are learned (backend.survival.knocks, backend.survival.wonders, backend.survival.questions).

| Lesson | Knock | First | Step | Sure when |
|---|---|---|---|---|
| winter | a winter day with hunger under 30 | 0.30 | 0.15 | it lives through a winter (the first spring dawn after one) |
| cloak | 2 game minutes freezing while 5 wool are carried or stored | 0.30 | 0.15 | |
| hearth | a chilled or freezing night at home in winter, knowing fire | 0.25 | 0.15 | |
| smoking | food spoils, or a winter day hungry, knowing fire | 0.25 | 0.15 | |
| rain | its fire goes out in the rain | 0.50 | 0.25 | |
| storm | a strike within STRIKE_NEAR blocks | 0.50 | 0.25 | it is struck |
| fog | a hostile's blow in fog by day | 0.35 | 0.15 | |

W1's `wild:fire` is also learned for sure by standing within FIRE_SEEN blocks of a fire Mimo did not make (a fire
in the trees). Each W2 lesson rolls on W1's rule, channel 206 plus its place in wild.SURVIVAL (217 to 223; the
chips' shuffle's 220 rolls on a question's index and never on Mimo's cell).

Wonders (asked with chips like W1's; `fog` is a yes-or-no one): `colder` on autumn day 3 at dusk, `fire_out` when
the rain puts its fire out, `storm` at its first thunderstorm, `fog` in its first fog, `freezing` when it freezes
in winter, `winter_food` on a winter day hunger falls under 50. The tick marks them (`meet_sky`, a sky effect) and
the Talker asks them. A gentle pet meets none and has no knocks.
"""

from __future__ import annotations

import math

from backend.survival import rain, sky, storms
from backend.survival.ailments import DAWN, at_built_home
from backend.survival.creatures.harm import BLOWS
from backend.survival.knocks import KNOCKS, Knock, guarded, knock, knows_lesson, sure
from backend.survival.spoilage import SPOILS
from backend.survival.vitals import FREEZING_BELOW
from backend.survival.wild import is_wild, wild_state
from backend.survival.wonders import Chip, Wonder, met, wonder

STRIKE_NEAR = 16.0
FIRE_SEEN = 8.0
HUNGRY_BELOW = 30.0
WINTER_HUNGRY = 50.0  # the winter_food wonder
CLOAK_COLD = 120.0  # game seconds freezing with the wool for a cloak at hand
CLOAK_WOOL = 5

KNOCKS.update({"winter": Knock(0.30, 0.15), "cloak": Knock(0.30, 0.15), "hearth": Knock(0.25, 0.15),
               "smoking": Knock(0.25, 0.15), "rain": Knock(0.50, 0.25), "storm": Knock(0.50, 0.25),
               "fog": Knock(0.35, 0.15)})

wonder(Wonder("colder", "The nights are getting colder. Is something coming?", ("winter",),
              (Chip("Winter is coming. Fill a chest with food before winter.", ("winter",)),
               Chip("It will warm up again soon.", false=True)),
              "whether something is coming, now the nights are colder"))
wonder(Wonder("fire_out", "The rain put my fire out!", ("rain",),
              (Chip("Keep your fire under a roof.", ("rain",)), Chip("Rain makes a fire burn hotter.", false=True)),
              "what to do when the rain puts out a fire"))
wonder(Wonder("storm", "The sky is booming and flashing! What should I do?", ("storm",),
              (Chip("Go home, and stay low and inside.", ("storm",)), Chip("Climb up high to watch it.", false=True),
               Chip("It's just noise.")),
              "what to do in a thunderstorm"))
wonder(Wonder("fog", "Everything is grey and foggy. Is it safe out here?", ("fog",),
              (Chip("Stay close to home in the fog.", ("fog",)), Chip("Fog is safe.", false=True)),
              "whether it is safe out in the fog", yes="Fog is safe.", no="Stay close to home in the fog."))
wonder(Wonder("freezing", "I'm freezing! How do I keep warm in the snow?", ("cloak", "hearth"),
              (Chip("Five wool make a wool cloak.", ("cloak",)), Chip("A stone hearth keeps the home warm.", ("hearth",)),
               Chip("Roll in the snow to warm up.", false=True)),
              "how to keep warm in the snow"))
wonder(Wonder("winter_food", "The lake is frozen and nothing grows. What do I eat?", ("winter", "smoking"),
              (Chip("Fill a chest with food before winter, and smoke your meat.", ("winter", "smoking")),
               Chip("Smoked meat keeps all winter.", ("smoking",)), Chip("Eat snow.", false=True)),
              "what to eat in the winter"))


def held(state: dict, item: str) -> int:
    return state["inventory"].get(item, 0) + sum(chest.get(item, 0) for chest in state.get("chests", {}).values())


def meet_sky(state: dict, context, at: float) -> None:
    """sky.EFFECTS: a wild pet's knocks and wonders of the weather and the seasons (see the module docstring)."""
    if not is_wild(state):
        return
    found, night = sky.sky_state(state), wild_state(state)
    db, events = context.db, context.events
    clock = context.clock_at(at)
    day, season, weather = clock["day_number"], found["season"], found["weather"]
    vitals = state["vitals"]
    since = night.get("sky_at")
    seconds = 0.0 if since is None else max(0.0, (at - since) * clock["time_scale"])
    night["sky_at"] = at
    if found["told"].get("colder") == day:
        met(state, "colder", at)
    if weather == "storm":
        met(state, "storm", at)
    if weather == "fog":
        met(state, "fog", at)
    if season == sky.WINTER:
        night["wintered"] = True
        if vitals["warmth"] < FREEZING_BELOW:
            met(state, "freezing", at)
        if vitals["hunger"] < WINTER_HUNGRY:
            met(state, "winter_food", at)
        if vitals["hunger"] < HUNGRY_BELOW and night.get("hungry_day") != day:
            night["hungry_day"] = day
            guarded(lambda: knock(state, db, events, at, "winter"))
            if db is not None and knows_lesson(db, "fire"):
                guarded(lambda: knock(state, db, events, at, "smoking"))
    elif night.pop("wintered", False) and season == "spring":
        guarded(lambda: sure(state, db, events, at, "winter"))  # it lived through a winter
    if vitals["warmth"] < FREEZING_BELOW and held(state, "wool") >= CLOAK_WOOL:
        night["cloak_cold"] = night.get("cloak_cold", 0.0) + seconds
        if night["cloak_cold"] >= CLOAK_COLD:
            night["cloak_cold"] = 0.0
            guarded(lambda: knock(state, db, events, at, "cloak"))
    position = state["position"]
    if any(math.dist((entry["x"], entry["y"], entry["z"]), (position["x"], position["y"], position["z"])) <= FIRE_SEEN
           for entry in found["fires"]):
        guarded(lambda: sure(state, db, events, at, "fire"))  # a fire it did not make


def doused(state: dict, context, cell, at: float) -> None:
    """rain.DOUSED: its fire went out in the rain."""
    if is_wild(state):
        met(state, "fire_out", at)
        guarded(lambda: knock(state, context.db, context.events, at, "rain"))


def struck(state: dict, context, cell, hit: bool, at: float) -> None:
    """storms.STRIKES: struck for sure; a strike within STRIKE_NEAR blocks a knock."""
    position = state["position"]
    if hit:
        guarded(lambda: sure(state, context.db, context.events, at, "storm"))
    elif math.hypot(cell[0] - position["x"], cell[2] - position["z"]) <= STRIKE_NEAR:
        guarded(lambda: knock(state, context.db, context.events, at, "storm"))


def at_dawn(state: dict, context, summary: dict, at: float) -> None:
    """ailments.DAWN: a chilled or freezing night at home in winter, knowing fire."""
    if (sky.winter(state) and (summary["chill"] or summary["froze"]) and context.db is not None
            and knows_lesson(context.db, "fire") and at_built_home(state, context)):
        guarded(lambda: knock(state, context.db, context.events, at, "hearth"))


def spoils(state: dict, context, item: str, count: int, where: str, at: float) -> None:
    """spoilage.SPOILS: food went bad, knowing fire."""
    if context.db is not None and knows_lesson(context.db, "fire"):
        guarded(lambda: knock(state, context.db, context.events, at, "smoking"))


def blown(scene, lost: float, source: str) -> None:
    """harm.BLOWS: a hostile's blow in fog by day."""
    if not scene.night and sky.foggy(scene.state):
        guarded(lambda: knock(scene.state, scene.herd.db, scene.events, scene.at, "fog"))


sky.EFFECTS.append(meet_sky)
rain.DOUSED.append(doused)
storms.STRIKES.append(struck)
DAWN.append(at_dawn)
SPOILS.append(spoils)
BLOWS.append(blown)
