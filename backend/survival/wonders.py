"""W1: wonders, what a wild pet meets and does not understand ("Mimo asks the owner" of the Wild World spec).

A wonder (WONDERS) has an id, Mimo's words (a template filled from what it met: `{where}`, `{food}`,
`{creature}`), the lessons that answer it, two or three answer chips (each teaching lessons, or "false", or
nothing), for a yes-or-no wonder its yes-claim and no-claim (sentences for the chat), the words of the
"asked" event and what a liar says of it (its false chip, or else a false claim for the chat). The tick marks
a wonder as met in `state["wild"]["wonders"]` ({id: {"met_at", "asked_at", "item", "closed", "fill"}}) and never
posts anything itself: the Talker's chore asks (backend.survival.questions).

Met when (`meet`, after each vitals step; `sighted`, after each walk: steps.OBSERVERS):
- red_berries, red_mushroom, sunleaf: a ripe berry or nightberry bush, a red mushroom, a sunleaf within
  SIGHT (8) blocks after a walk, the first time;
- tummy: the first tummy ache; raw_meat: the first raw meat or fish carried; wound: the first wound;
- cold_night: the first night with 2 game minutes under warmth 35; hard_floor: the third night asleep on the
  floor; spoiled: the first food gone bad; dark_creature: the first hostile that comes after Mimo (a flight,
  a fight or a blow).

Hesitating (meals.HOLDS: `hesitates`): an untried food whose wonder was asked waits HESITATE (8 game minutes)
before Mimo risks a taste; one met and not yet asked waits too, unless OPEN_MOST questions are open already
and it could not be posted. A gentle pet meets no wonder.

W1 fix round 1: Mimo's words name what it met as it sees it (wild.LOOKS_LIKE: nightberries are red berries to
it, "My red berries went bad!", and a sickness from them is from "those berries": backend.survival.meals), and
the open questions are read through one helper (bond_tables.open_question_rows).
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass

from backend.survival.ailments import sickness, wound_of
from backend.survival.bond_tables import open_question_rows
from backend.survival.meals import HOLDS, RAW_RISK
from backend.survival.once import log_once
from backend.survival.senses import natural_plants
from backend.survival.spoilage import SPOILED
from backend.survival.steps import OBSERVERS, label
from backend.survival.wild import LOOKS_LIKE, RED_BERRIES, RED_MUSHROOM, is_wild, wild_state

logger = logging.getLogger(__name__)

SIGHT = 8.0
HESITATE = 480.0  # game seconds a question makes Mimo wait before it risks what it asked about
OPEN_MOST = 3
COLD_NIGHT = 120.0  # game seconds under warmth 35 in one night
FLOORS = 3  # nights asleep on the floor


@dataclass(frozen=True)
class Chip:
    words: str
    teaches: tuple[str, ...] = ()  # the survival lessons it teaches
    false: bool = False  # a wrong answer: doubted, never learned


@dataclass(frozen=True)
class Wonder:
    id: str
    words: str  # what Mimo asks, filled from what it met
    lessons: tuple[str, ...]  # the lessons that answer it
    chips: tuple[Chip, ...]
    asked: str  # "{name} asked you {asked}."
    fill: str = ""  # the default filling
    items: tuple[str, ...] = ()  # untried foods it holds back while Mimo waits for an answer
    yes: str = ""  # a yes-or-no wonder's claims for the chat
    no: str = ""
    lie: str = ""  # a false claim for the chat, for a wonder with no false chip


WONDERS: dict[str, Wonder] = {}


def wonder(found: Wonder) -> Wonder:
    WONDERS[found.id] = found
    return found


wonder(Wonder("red_berries", "I found red berries{where}. Are they safe to eat?", ("berries", "nightberries"),
              (Chip("Yes, bright red berries are safe.", ("berries",)),
               Chip("The dark purple ones are nightberries, and they're poison.", ("nightberries", "berries")),
               Chip("They're all poison.", false=True)),
              "whether red berries are safe to eat", items=RED_BERRIES,
              yes="Red berries are safe to eat.", no="Red berries are poison."))
wonder(Wonder("red_mushroom", "There are red mushrooms here. Can I eat them?", ("red_mushroom",),
              (Chip("Red mushrooms are poison.", ("red_mushroom",)), Chip("Sure, they're tasty.", false=True)),
              "whether red mushrooms are safe to eat", items=(RED_MUSHROOM,),
              yes="Red mushrooms are safe to eat.", no="Red mushrooms are poison."))
wonder(Wonder("sunleaf", "There's a little yellow herb here. What is it for?", ("sunleaf",),
              (Chip("That's sunleaf. It cures sickness and cleans wounds.", ("sunleaf",)), Chip("It's just a weed.")),
              "what the little yellow herb is for", lie="Sunleaf is poison."))
wonder(Wonder("tummy", "My tummy hurts after eating {food}. What helps?", ("sunleaf",),
              (Chip("Eat sunleaf, the little yellow herb.", ("sunleaf",)), Chip("Rest. It will pass.")),
              "what helps a tummy ache", fill="something", lie="Sunleaf is poison."))
wonder(Wonder("raw_meat", "Can I eat this {food}?", ("fire", "cooking"),
              (Chip("Cook it on a campfire first.", ("fire", "cooking")), Chip("Raw is fine.", false=True)),
              "whether raw meat is safe to eat", fill="raw meat",
              yes="Raw meat is safe to eat.", no="Cooked meat and fish are safe to eat."))
wonder(Wonder("cold_night", "It's so cold tonight. How do I stay warm?", ("fire", "shelter"),
              (Chip("Two logs and three sticks make a campfire.", ("fire",)),
               Chip("Build a shelter with a roof and a door.", ("shelter",)), Chip("Just keep moving.")),
              "how to stay warm at night", lie="Five logs make a campfire."))
wonder(Wonder("dark_creature", "Something with glowing eyes came at me in the dark! How do I keep them away?",
              ("light", "shelter"),
              (Chip("Torches keep them away.", ("light",)), Chip("Sleep in a shelter with a door.", ("shelter",)),
               Chip("They just want to play.")),
              "how to keep the dark creatures away", lie="Torches bring the dark creatures."))
wonder(Wonder("wound", "{creature} cut me and it won't stop hurting. What should I do?", ("bandage", "sunleaf"),
              (Chip("Wrap it in a wool bandage.", ("bandage",)), Chip("Press sunleaf on it.", ("sunleaf",)),
               Chip("Leave it alone.")),
              "what to do about a wound", fill="Something", lie="Sunleaf is poison."))
wonder(Wonder("spoiled", "My {food} went bad! How do I keep food fresh?", ("keeping",),
              (Chip("Food in a chest keeps twice as long.", ("keeping",)),
               Chip("Cook it before it turns.", ("cooking", "keeping"))),
              "how to keep food fresh", fill="food", lie="Spoiled food is safe to eat."))
wonder(Wonder("hard_floor", "The floor is so hard to sleep on.", ("bed",),
              (Chip("Six planks make a bed.", ("bed",)), Chip("You'll get used to it.")),
              "how to sleep better", lie="Two planks make a bed."))


def wonders_of(state: dict) -> dict:
    return wild_state(state)["wonders"]


def met(state: dict, wonder_id: str, at: float, fill: str = "") -> bool:
    """Mark a wonder met, the first time. True when it was new."""
    found = wonders_of(state)
    if wonder_id in found:
        return False
    found[wonder_id] = {"met_at": at, "asked_at": None, "item": None, "closed": None, "fill": fill}
    return True


def where_words(state: dict, db: sqlite3.Connection | None, cell) -> str:
    """" north of home" for a cell away from the home Mimo knows (8 blocks or more), else ""."""
    if db is None:
        return ""
    from backend.survival.exploring import compass  # local: exploring imports the brain's world readers
    from backend.survival.memory import places
    home = places(db, ("home",))
    if not home:
        return ""
    dx, dz = cell[0] - home[0]["x"], cell[2] - home[0]["z"]
    return f" {compass(dx, dz)} of home" if math.hypot(dx, dz) >= 8 else ""


def sighted(state: dict, step: dict, context, at: float) -> None:
    """steps.OBSERVERS: after a walk, the red berries, red mushrooms and sunleaf within SIGHT, the first time."""
    if step["kind"] not in ("walk", "swim") or not is_wild(state):
        return
    try:
        found = wonders_of(state)
        wanted = {"red_berries": ("berry_bush_ripe", "nightberry_bush_ripe"), "red_mushroom": (RED_MUSHROOM,),
                  "sunleaf": ("sunleaf",)}
        missing = {wonder_id: blocks for wonder_id, blocks in wanted.items() if wonder_id not in found}
        if not missing:
            return
        position = state["position"]
        x, z = round(position["x"]), round(position["z"])
        seed = state.get("world_seed", "0")
        for wonder_id, blocks in missing.items():
            cells = natural_plants(seed, x, z, SIGHT, blocks)
            cells += [cell for cell, _ in context.grid.placed_cells(x, z, SIGHT, blocks)]
            seen = next((cell for cell in cells if context.grid.material(*cell) in blocks), None)
            if seen is not None:
                met(state, wonder_id, at, where_words(state, context.db, seen) if wonder_id == "red_berries" else "")
    except Exception as error:
        log_once(logger, "wonders", error)


OBSERVERS.append(sighted)


def meet(state: dict, context, at: float) -> None:
    """After a vitals step: the wonders a wild pet's body and its nights bring (see the module docstring)."""
    if not is_wild(state):
        return
    try:
        found, night = wonders_of(state), wild_state(state)
        ill = sickness(state)
        if "tummy" not in found and ill is not None and ill["kind"] == "tummy":
            met(state, "tummy", at, night.get("sick_from") or "something")
        raw = next((item for item in RAW_RISK if state["inventory"].get(item, 0) > 0), None)
        if "raw_meat" not in found and raw is not None:
            met(state, "raw_meat", at, label(raw))
        wound = wound_of(state)
        if "wound" not in found and wound is not None:
            met(state, "wound", at, f"A {label(state.get('hurt_by') or 'creature')}")
        if "cold_night" not in found and night["night_cold"] >= COLD_NIGHT:
            met(state, "cold_night", at)
        if "hard_floor" not in found and night["floor_nights"] >= FLOORS:
            met(state, "hard_floor", at)
        spoiled = state["inventory"].get(SPOILED, 0) > 0 or any(chest.get(SPOILED) for chest in state.get("chests", {}).values())
        if "spoiled" not in found and spoiled:
            item = night.get("last_spoiled") or "food"
            met(state, "spoiled", at, label(LOOKS_LIKE.get(item, item)))  # as Mimo sees it: "My red berries went bad!"
        chased = (state.get("brain") or {}).get("reflex") in ("flee", "fight") or state.get("hurt_at") is not None
        if "dark_creature" not in found and chased:
            met(state, "dark_creature", at)
    except Exception as error:
        log_once(logger, "wonders", error)


def open_questions(db: sqlite3.Connection | None) -> int:
    """How many of Mimo's questions are open (asked, not closed). A world without an inbox has none; any other
    error is raised (bond_tables.open_question_rows, W1 fix round 1)."""
    return 0 if db is None else len(open_question_rows(db))


def hesitates(s, item: str) -> bool:
    """meals.HOLDS: Mimo waits before it tastes `item`: the wonder about it was asked less than HESITATE game
    seconds ago, or it was met and will be asked (fewer than OPEN_MOST questions are open)."""
    for wonder_id, found in wonders_of(s.state).items():
        if wonder_id not in WONDERS or item not in WONDERS[wonder_id].items:
            continue
        asked = found.get("asked_at")
        if asked is not None:
            return (s.at - asked) * s.scale < HESITATE
        return open_questions(s.db) < OPEN_MOST
    return False


HOLDS.append(hesitates)
