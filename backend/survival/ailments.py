"""W1: a wild pet's sicknesses (docs/superpowers/specs/2026-09-27-wild-world-design.md, "Hazards").

Mimo has at most one sickness at a time, `state["ailments"]["sick"]` = {"kind", "since", "left"} (`left` in
game seconds), and a new one keeps the longer of the two (`fall_sick`). The kinds are AILMENTS:

| Kind | Symptom | Lasts | Drain | Also |
|---|---|---|---|---|
| tummy ache | "My tummy hurts." | 12 game minutes | 1 health per 20 game s | hunger drains 1.5 times as fast |
| chill | "I'm shivery and hot." | 25 game minutes | 1 health per 30 game s | energy drains 1.5 times as fast |

While Mimo is sick no health regenerates and mood's target falls 15 (`ailing`, read by the tick for each
vitals step: vitals.Ailing). A chill's time runs twice as fast while Mimo rests or sleeps with warmth 60 or
more (`tend`, after each vitals step). The sickness can kill: its drain is the cause "sickness" when it is
the largest damage of the killing step (vitals.CAUSE_ORDER). What the drain takes counts in
`state["wild"]["lost"]`, the health a wild pet lost to its hazards (`lose`; the balance gate reads it).

Eating one sunleaf ends any sickness at once: the eat step of a sunleaf (steps.EATING: `eat_herb`) logs
"Pip ate sunleaf and felt better." (a "cured" event). What makes Mimo sick (food, a cold night) and what
makes it eat sunleaf (the take_herb reflex, find_herb and nibble: backend.survival.herbs) live elsewhere.

A wound (`state["ailments"]["wound"]` = {"since", "age", "festering", "dressed_age"}; `age` in game seconds;
backend.survival.wounds opens one): while it is open no health regenerates. Undressed for FESTER_AFTER (10 game
minutes) it festers ("Pip's wound is festering."): 1 health per 40 game s, and mood's target falls 10. It heals
by itself HEALS_AFTER (a game day) after it opened, festering or not; a dressed one stops festering at once and
closes DRESSED_CLOSES (5 game minutes) later (`dress`).

Cold nights (`tend_night`, after each vitals step): each night the game seconds with warmth under CHILL_BELOW
(35) are counted (`state["wild"]["night_cold"]`); at dawn 5 game minutes or more give a chill with chance
CHILL_CHANCE, 15 or more, or any freezing that night, a chill for sure ("Pip caught a chill in the night.", a
"chill" event). A night asleep on the floor of a sheltered spot counts in `floor_nights`. DAWN then hears how
the night went (backend.survival.knocks).

A gentle pet never has an ailment: nothing in W1 makes one, and `ailing` gives nothing without one. A
crash in any of this is logged once and counts as nothing (wild.AILMENTS' guard is the tick's `tend`).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from backend.services.crafting import take_items
from backend.survival.clock import DAY_SECONDS, NIGHT_PHASES
from backend.survival.nature import roll
from backend.survival.once import log_once
from backend.survival.steps import EATING
from backend.survival.vitals import FREEZING_BELOW, Ailing
from backend.survival.wild import is_wild, wild_state

logger = logging.getLogger(__name__)

GAME_MINUTE = 60.0
SICK_MOOD = 15.0
WARM_REST = 60.0  # warmth from which a chill passes twice as fast while Mimo rests or sleeps
HERB = "sunleaf"
HERB_HUNGER = 2.0  # hunger a sunleaf fills
NIBBLE_CHANCE = 0.4  # a sickness in which the instinct nibbles a sunleaf nearby (backend.survival.herbs)
NIBBLE_CHANNEL = 200  # Wild World's roll channels are 200 to 259 (spec resolution 27)
FESTER_AFTER = 10 * GAME_MINUTE
HEALS_AFTER = DAY_SECONDS
DRESSED_CLOSES = 5 * GAME_MINUTE
FESTER_DRAIN = 1 / 40
FESTER_MOOD = 10.0
CHILL_BELOW = 35.0
CHILL_SOME = 5 * GAME_MINUTE  # a chill with CHILL_CHANCE
CHILL_SURE = 15 * GAME_MINUTE  # a chill for sure
CHILL_CHANCE = 0.6
CHILL_CHANNEL = 205
FLOOR_SLEEP = 5 * GAME_MINUTE  # asleep on the floor of a sheltered spot this long: a night on the floor
# W1: functions (state, context, summary, at) run at a wild pet's dawn with how its night went: {"cold" (game
# seconds under CHILL_BELOW), "froze", "chill" (it caught one), "blows" (hostile blows that night), "floor" (a
# night asleep on the floor of a sheltered spot)} (backend.survival.knocks). One that crashes is logged once.
DAWN: list = []


@dataclass(frozen=True)
class Ailment:
    kind: str
    words: str  # the symptom, in Mimo's words
    label: str  # for the HUD: "Tummy ache"
    lasts: float  # game seconds
    drain: float  # health a game second
    hunger: float = 1.0
    energy: float = 1.0


AILMENTS: dict[str, Ailment] = {
    "tummy": Ailment("tummy", "My tummy hurts.", "Tummy ache", 12 * GAME_MINUTE, 1 / 20, hunger=1.5),
    "chill": Ailment("chill", "I'm shivery and hot.", "Chill", 25 * GAME_MINUTE, 1 / 30, energy=1.5),
}


def ailments_of(state: dict) -> dict:
    """state["ailments"], with its fields (a world from before W1 has none)."""
    found = state.setdefault("ailments", {})
    found.setdefault("sick", None)
    found.setdefault("wound", None)
    return found


def pet_cell(state: dict) -> tuple[int, int, int]:
    """The cell Mimo stands in, for a roll."""
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def sickness(state: dict) -> dict | None:
    """Mimo's sickness now, or None (read only)."""
    return (state.get("ailments") or {}).get("sick")


def sick(state: dict) -> bool:
    return sickness(state) is not None


def fall_sick(state: dict, kind: str, at: float, events: list | None = None, text: str | None = None) -> bool:
    """Mimo falls sick with `kind`; with a sickness already, the longer of the two stays. Logs `text` as a
    "sick" event when given. True when this is a new sickness (none before)."""
    ailment = AILMENTS[kind]
    found = ailments_of(state)
    now = found["sick"]
    fresh = now is None
    if now is None:
        nibble = roll(state.get("world_seed", "0"), pet_cell(state), NIBBLE_CHANNEL, int(at)) < NIBBLE_CHANCE
        found["sick"] = {"kind": kind, "since": at, "left": ailment.lasts, "nibble": nibble}
    elif ailment.lasts > now["left"]:
        found["sick"] = {**now, "kind": kind, "left": ailment.lasts}
    state["last_thought"] = ailment.words
    if events is not None and text:
        events.append((at, "sick", text))
    return fresh


def cure(state: dict) -> bool:
    """Any sickness ends. True when there was one."""
    found = state.get("ailments") or {}
    if found.get("sick") is None:
        return False
    found["sick"] = None
    return True


def wound_of(state: dict) -> dict | None:
    """Mimo's wound now, or None (read only)."""
    return (state.get("ailments") or {}).get("wound")


def ailing(state: dict) -> Ailing | None:
    """What Mimo's ailments do to a vitals step now; None without any (a gentle pet, always)."""
    found, wound = sickness(state), wound_of(state)
    ailment = AILMENTS.get(found["kind"]) if found is not None else None
    if ailment is None and wound is None:
        return None
    festering = wound is not None and wound["festering"]
    return Ailing(drain=(ailment.drain if ailment else 0.0) + (FESTER_DRAIN if festering else 0.0),
                  hunger=ailment.hunger if ailment else 1.0, energy=ailment.energy if ailment else 1.0, heals=False,
                  mood=(SICK_MOOD if ailment else 0.0) + (FESTER_MOOD if festering else 0.0))


def lose(state: dict, health: float) -> None:
    """Count `health` a wild pet lost to its hazards (a sickness's or a festering wound's drain, a poison plant) in
    `state["wild"]["lost"]`."""
    if health > 0:
        found = wild_state(state)
        found["lost"] = found.get("lost", 0.0) + health


def open_wound(state: dict, at: float) -> bool:
    """A creature's blow opens a wound, unless Mimo has one already. True when it did."""
    found = ailments_of(state)
    if found["wound"] is not None:
        return False
    found["wound"] = {"since": at, "age": 0.0, "festering": False, "dressed_age": None}
    state["last_thought"] = "Ow, it's bleeding. That will need looking after."
    return True


def dress(state: dict) -> bool:
    """The wound is dressed: it stops festering at once and closes DRESSED_CLOSES later. True when there was an
    open wound not dressed yet."""
    found = wound_of(state)
    if found is None or found["dressed_age"] is not None:
        return False
    found.update(festering=False, dressed_age=found["age"])
    state["last_thought"] = "There. All wrapped up."
    return True


def heard(hooks: list, *args) -> None:
    for hears in hooks:
        try:
            hears(*args)
        except Exception as error:
            log_once(logger, "ailments hook", error)


def tend(state: dict, context, seconds: float, activity: str, at: float) -> None:
    """After a vitals step of `seconds` game seconds: what its drain took is counted, the sickness runs its time
    (a chill twice as fast while Mimo rests or sleeps warm), and a wound festers, closes or heals. A crash is
    logged once and changes nothing."""
    try:
        ill = ailing(state)  # what the vitals step just took
        if ill is not None:
            lose(state, ill.drain * seconds)
        found = sickness(state)
        if found is not None:
            rested = activity != "working" and state["vitals"]["warmth"] >= WARM_REST
            found["left"] = max(0.0, found["left"] - seconds * (2.0 if found["kind"] == "chill" and rested else 1.0))
            if found["left"] <= 0:
                state["ailments"]["sick"] = None
                state["last_thought"] = "I feel better now."
        wound = wound_of(state)
        if wound is not None:
            wound["age"] += seconds
            dressed = wound["dressed_age"]
            if wound["age"] >= HEALS_AFTER or (dressed is not None and wound["age"] - dressed >= DRESSED_CLOSES):
                state["ailments"]["wound"] = None
                state["last_thought"] = "My wound has healed."
            elif dressed is None and not wound["festering"] and wound["age"] >= FESTER_AFTER:
                wound["festering"] = True
                state["last_thought"] = "My wound hurts more and more."
                context.events.append((at, "festering", f"{state['name']}'s wound is festering."))
    except Exception as error:
        log_once(logger, "ailments", error)


def tend_night(state: dict, context, seconds: float, phases: tuple[str, str], activity: str, sheltered: bool,
               at: float) -> None:
    """After a vitals step (see the module docstring): a wild pet's cold and floor at night, and at dawn its
    chill, its floor night and DAWN. A crash is logged once and changes nothing."""
    if not is_wild(state):
        return
    try:
        night = wild_state(state)
        before, after = phases
        if before in NIGHT_PHASES:
            warmth = state["vitals"]["warmth"]
            if warmth < CHILL_BELOW:
                night["night_cold"] += seconds
            if warmth < FREEZING_BELOW:
                night["froze"] = True
            if activity == "sleeping" and sheltered:
                night["floor_sleep"] = night.get("floor_sleep", 0.0) + seconds
        if before in NIGHT_PHASES and after not in NIGHT_PHASES:
            dawn(state, context, at)
    except Exception as error:
        log_once(logger, "cold night", error)


def dawn(state: dict, context, at: float) -> None:
    """The night is over: a chill for a cold one, a floor night counted, and DAWN told how it went."""
    night = wild_state(state)
    cold, froze = night["night_cold"], bool(night.get("froze"))
    chance = 1.0 if cold >= CHILL_SURE or froze else CHILL_CHANCE if cold >= CHILL_SOME else 0.0
    chill = chance > 0 and roll(state.get("world_seed", "0"), pet_cell(state), CHILL_CHANNEL, int(at)) < chance
    if chill:
        fall_sick(state, "chill", at)
        context.events.append((at, "chill", f"{state['name']} caught a chill in the night."))
    floor = night.get("floor_sleep", 0.0) >= FLOOR_SLEEP
    if floor:
        night["floor_nights"] += 1
    summary = {"cold": cold, "froze": froze, "chill": chill, "blows": night.get("night_blows", 0), "floor": floor}
    night.update(night_cold=0.0, froze=False, floor_sleep=0.0, night_blows=0)
    heard(DAWN, state, context, summary, at)


def eat_herb(step: dict, state: dict, at: float) -> tuple[str, str] | None:
    """steps.EATING: a sunleaf eaten ends any sickness ("cured"); None for any other food."""
    if step["item"] != HERB:
        return None
    state["inventory"] = take_items(state["inventory"], {HERB: 1})
    state["vitals"]["hunger"] = min(100.0, state["vitals"]["hunger"] + HERB_HUNGER)
    name = state["name"]
    if cure(state):
        state["last_thought"] = "That's better. I feel well again."
        return "cured", f"{name} ate sunleaf and felt better."
    return "ate", f"{name} ate sunleaf."


EATING.append(eat_herb)


def ailments_view(state: dict) -> dict:
    """For /api/mimo: {"sick": {"kind", "label", "words", "minutes"} or null, "wound": ... or null}."""
    found = sickness(state)
    sick_view = None
    if found is not None and found["kind"] in AILMENTS:
        ailment = AILMENTS[found["kind"]]
        sick_view = {"kind": ailment.kind, "label": ailment.label, "words": ailment.words,
                     "minutes": math.ceil(found["left"] / GAME_MINUTE)}
    wound = wound_of(state)
    wound_view = None if wound is None else {"festering": wound["festering"], "dressed": wound["dressed_age"] is not None,
                                             "minutes": math.ceil(max(0.0, HEALS_AFTER - wound["age"]) / GAME_MINUTE)}
    return {"sick": sick_view, "wound": wound_view}
