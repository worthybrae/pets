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

A gentle pet never has an ailment: nothing in W1 makes one, and `ailing` gives nothing without one. A
crash in any of this is logged once and counts as nothing (wild.AILMENTS' guard is the tick's `tend`).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from backend.services.crafting import take_items
from backend.survival.nature import roll
from backend.survival.once import log_once
from backend.survival.steps import EATING
from backend.survival.vitals import Ailing
from backend.survival.wild import wild_state

logger = logging.getLogger(__name__)

GAME_MINUTE = 60.0
SICK_MOOD = 15.0
WARM_REST = 60.0  # warmth from which a chill passes twice as fast while Mimo rests or sleeps
HERB = "sunleaf"
HERB_HUNGER = 2.0  # hunger a sunleaf fills
NIBBLE_CHANCE = 0.4  # a sickness in which the instinct nibbles a sunleaf nearby (backend.survival.herbs)
NIBBLE_CHANNEL = 200  # Wild World's roll channels are 200 to 259 (spec resolution 27)


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


def ailing(state: dict) -> Ailing | None:
    """What Mimo's ailments do to a vitals step now; None without any (a gentle pet, always)."""
    found = sickness(state)
    if found is None:
        return None
    ailment = AILMENTS.get(found["kind"])
    if ailment is None:
        return None
    return Ailing(drain=ailment.drain, hunger=ailment.hunger, energy=ailment.energy, heals=False, mood=SICK_MOOD)


def lose(state: dict, health: float) -> None:
    """Count `health` a wild pet lost to its hazards (a sickness's drain, a poison plant) in
    `state["wild"]["lost"]`."""
    if health > 0:
        found = wild_state(state)
        found["lost"] = found.get("lost", 0.0) + health


def tend(state: dict, seconds: float, activity: str, at: float, events: list) -> None:
    """After a vitals step of `seconds` game seconds: what its drain took is counted, and the sickness runs its
    time (a chill twice as fast while Mimo rests or sleeps warm). A crash is logged once and changes nothing."""
    try:
        ill = ailing(state)  # what the vitals step just took
        if ill is not None:
            lose(state, ill.drain * seconds)
        found = sickness(state)
        if found is None:
            return
        rested = activity != "working" and state["vitals"]["warmth"] >= WARM_REST
        found["left"] = max(0.0, found["left"] - seconds * (2.0 if found["kind"] == "chill" and rested else 1.0))
        if found["left"] <= 0:
            state["ailments"]["sick"] = None
            state["last_thought"] = "I feel better now."
    except Exception as error:
        log_once(logger, "ailments", error)


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
    return {"sick": sick_view, "wound": None}
