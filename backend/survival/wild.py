"""Wild World W1: a newborn in a wild world (docs/superpowers/specs/2026-09-27-wild-world-design.md).

A life has a difficulty, `state["difficulty"]`: "wild" or "gentle", set at hatch and never changed.
A world with no difficulty key (every world made before W1) reads gentle, and its first tick writes
"gentle". A gentle pet is today's game: every survival lesson is known from its first tick (`settle`,
from the tick: rows in memory_knowledge with fact "lesson" and a second fact BORN_KNOWING, written
quietly, as curiosity's learn_quietly writes an old save's), none of W1's hazards happen to it and no
gate is ever shut for it (`unlocked`). A wild pet hatches knowing instinct only: each survival lesson
(SURVIVAL, a journal lesson of kind "survival" named `wild:<name>`, the colon keeping it out of L4b's
curios) unlocks what the table says for it, and it learns them from its owner (Mind's teaching, its
questions) or alone, by knocks.

Lessons known from birth never count in the tallies that read how many lessons Mimo learned: the
journal's own list and counts, investigate's and tinker's facts and Mind's "I have learned 20 things"
thought read them without BORN_KNOWING (situation.Situation.lessons, journal.learned, insights, replies),
so a gentle pet's choices and words stay as they were.

The wild bookkeeping lives in state["wild"] (`wild_state`): `knocks`, `wonders`, `shun`, `night_cold`,
`floor_nights`, `granted` (the milestone version granted to a gentle pet), each read with a default so
older saves and archives read as empty. This module imports nothing that imports the journal, so any
module may ask it whether a gate is open.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.survival.memory import know, known

if TYPE_CHECKING:
    from backend.survival.situation import Situation

WILD, GENTLE = "wild", "gentle"
DIFFICULTIES = (WILD, GENTLE)
PREFIX = "wild:"
KIND = "survival"  # the journal lessons' kind
BORN_KNOWING = "born_knowing"  # memory_knowledge's second fact for a lesson a gentle pet knew from the start
FIGURED = "figured"  # memory_knowledge's second fact for a lesson Mimo worked out alone (a knock)
LESSON = "lesson"  # journal.FACT
TAUGHT = "taught"  # journal.TAUGHT
GRANTED = 1  # the milestone whose lessons a gentle pet has been granted (W1)


@dataclass(frozen=True)
class Survival:
    name: str  # "fire": the lesson's thing is "wild:fire"
    words: str  # what it is about: "a campfire"
    fact: str  # the one sentence the owner can teach
    unlocks: str  # what it lets a wild pet do
    figured: str  # "Pip worked out that {figured}."
    subjects: tuple[str, ...] = ()  # what the owner's words name when they speak of it (backend.survival.lessons)
    means: tuple[str, ...] = ()  # words it means besides its fact's own ("poison" of the berries: safe or not)
    sides: tuple[str, ...] = ()  # words its fact stands for when opposites are weighed ("warm" of the shelter)


SURVIVAL: tuple[Survival, ...] = (
    Survival("berries", "red berries", "Bright red berries are safe to eat.",
             "eats and forages red berries without asking", "bright red berries are safe to eat",
             ("red berries",), ("safe", "poison", "eat")),
    Survival("nightberries", "nightberries", "Nightberries, the dark purple berries with pale specks, are poison.",
             "tells nightberries from berries and never eats them", "the dark purple berries are poison",
             ("nightberries", "purple berries", "dark berries"), ("safe", "poison", "eat")),
    Survival("red_mushroom", "red mushrooms", "Red mushrooms are poison.", "never picks or eats red mushrooms",
             "red mushrooms are poison", ("red mushrooms",), ("safe", "poison", "eat")),
    Survival("sunleaf", "sunleaf", "Sunleaf, the little yellow herb, cures sickness when eaten and cleans a wound.",
             "carries sunleaf, eats one when sick and dresses a wound with one", "sunleaf cures a sickness",
             ("sunleaf", "yellow herb"), ("safe", "poison", "eat")),
    Survival("bandage", "a wool bandage", "A bandage of wool on a wound stops it festering.",
             "makes wool bandages and dresses a wound", "a wool bandage stops a wound festering",
             ("bandage",), ("wrap", "clean")),
    Survival("fire", "a campfire", "Two logs and three sticks make a campfire, and a fire keeps you warm at night.",
             "makes campfires and lights one to get warm", "a campfire keeps the cold away",
             ("campfire",), ("fire",)),
    Survival("cooking", "cooked meat", "Meat and fish cooked on a fire are safe to eat and fill you up far more.",
             "cooks meat and fish on a fire", "cooking makes meat safe",
             ("meat", "cooked meat", "cooked fish"), ("safe", "poison", "eat", "raw", "cook")),
    Survival("keeping", "food keeping", "Raw food goes bad in a day or two, and food in a chest keeps twice as long.",
             "cooks raw food before it turns, stores spare food and throws out what went bad",
             "food keeps longer in a chest", ("food chest", "spoiled food"), ("fresh", "spoil", "rot")),
    Survival("light", "torches", "Torches keep the dark creatures away, because they only come out where it is dark.",
             "lights torches round home at night", "torches keep the dark creatures away",
             ("dark creatures",), ("bring", "attract")),
    Survival("shelter", "a shelter", "A shelter with walls, a roof and a door keeps out the cold and the dark "
             "creatures at night.", "builds a shelter with a door and makes it a home",
             "a shelter with a door keeps the night out", ("shelter",), ("safe", "warm"), ("warm",)),
    Survival("bed", "a bed", "Six planks make a bed, and sleep in a bed rests you best.",
             "makes a bed and sleeps in it", "a bed rests you best", ("bed",), ("sleep",)),
)
BY_NAME = {lesson.name: lesson for lesson in SURVIVAL}
SOURCES = {TAUGHT: "from_you", BORN_KNOWING: "from_start"}


def thing(name: str) -> str:
    """The journal lesson a survival lesson is: "wild:fire"."""
    return f"{PREFIX}{name}"


def difficulty(state: dict) -> str:
    """"wild" or "gentle"; a world with no key (from before W1) reads gentle."""
    found = state.get("difficulty")
    return found if found in DIFFICULTIES else GENTLE


def is_wild(state: dict) -> bool:
    return state.get("difficulty") == WILD


def knows(s: Situation, name: str) -> bool:
    """Mimo knows the survival lesson `name` (a gentle pet's born-knowing lessons aside)."""
    return thing(name) in s.lessons


def unlocked(s: Situation, name: str) -> bool:
    """What the lesson `name` unlocks is open to Mimo: always for a gentle pet, and for a wild one once it
    knows the lesson."""
    return not is_wild(s.state) or knows(s, name)


def wild_state(state: dict) -> dict:
    """state["wild"], with every field a wild pet's bookkeeping needs."""
    found = state.setdefault("wild", {})
    for key, default in (("knocks", {}), ("wonders", {}), ("shun", {}), ("night_cold", 0.0), ("floor_nights", 0),
                         ("granted", None)):
        found.setdefault(key, default)
    return found


def settle(state: dict, db: sqlite3.Connection | None, at: float) -> None:
    """The tick of a living pet: a world with no difficulty becomes gentle, and a gentle pet not yet granted
    this milestone's lessons is granted them now, quietly (no event, no discovery, no memory, no choice)."""
    if state.get("difficulty") not in DIFFICULTIES:
        state["difficulty"] = GENTLE
    if state["difficulty"] != GENTLE or db is None or (state.get("wild") or {}).get("granted") == GRANTED:
        return
    for lesson in SURVIVAL:
        know(db, thing(lesson.name), LESSON, at)
        know(db, thing(lesson.name), BORN_KNOWING, at)
    state.setdefault("wild", {})["granted"] = GRANTED


def born_knowing(db: sqlite3.Connection) -> set[str]:
    """The lessons Mimo knew from the start (a gentle pet's)."""
    return set(known(db, BORN_KNOWING))


def learned_lessons(db: sqlite3.Connection) -> list[str]:
    """The lessons Mimo learned, first first, leaving out those it knew from the start."""
    start = born_knowing(db)
    return [lesson for lesson in known(db, LESSON) if lesson not in start]


def source_of(facts: set[str]) -> str:
    """Where a lesson Mimo knows came from: the owner ("from_you"), the start ("from_start"), or Mimo
    itself ("figured": worked out, or found out by meeting the thing)."""
    for fact, source in SOURCES.items():
        if fact in facts:
            return source
    return "figured"


def facts_of(db: sqlite3.Connection, subjects: tuple[str, ...]) -> dict[str, set[str]]:
    """{subject: its memory_knowledge facts}, for these subjects. An archive from before memory has none."""
    marks = ",".join("?" * len(subjects))
    try:
        rows = db.execute(f"SELECT subject, fact FROM memory_knowledge WHERE subject IN ({marks})", subjects).fetchall()
    except sqlite3.OperationalError:
        return {}
    found: dict[str, set[str]] = {}
    for subject, fact in rows:
        found.setdefault(subject, set()).add(fact)
    return found


def survival_view(db: sqlite3.Connection) -> list[dict]:
    """Every survival lesson for the viewer's journal, in the table's order: {name, words, fact, known,
    source} (source null while unknown)."""
    facts = facts_of(db, tuple(thing(lesson.name) for lesson in SURVIVAL))
    found = []
    for lesson in SURVIVAL:
        mine = facts.get(thing(lesson.name), set())
        learned = LESSON in mine
        found.append({"name": lesson.name, "words": lesson.words, "fact": lesson.fact, "known": learned,
                      "source": source_of(mine) if learned else None})
    return found
