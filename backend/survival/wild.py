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

W2 adds seven lessons for the weather and the seasons (winter, cloak, hearth, smoking, rain, storm, fog) and
raises GRANTED to 2: a gentle pet granted W1's lessons is granted W2's on its next tick the same way.

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
GRANTED = 2  # the milestone whose lessons a gentle pet has been granted (W1, then W2)


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
    # W2: the weather and the seasons (backend.survival.sky and what hangs from it).
    Survival("winter", "winter", "Winter comes after autumn, when crops stop and animals hide, so fill a chest with "
             "food in autumn.", "gets ready for winter: fills its chests with food in autumn",
             "winter comes after autumn, so a chest of food must be filled in autumn", ("winter",), ("before",)),
    Survival("cloak", "a wool cloak", "Five wool make a wool cloak that keeps you warm in the snow.",
             "makes a wool cloak and wears it", "a wool cloak keeps the snow's cold out", ("wool cloak", "cloak")),
    Survival("hearth", "a hearth", "A hearth of stone with a fire in it keeps the home warm all winter.",
             "builds a stone hearth in its home", "a stone hearth keeps the home warm", ("hearth",)),
    Survival("smoking", "smoked meat", "Meat smoked over a fire keeps all winter.", "smokes meat over a fire",
             "smoked meat keeps all winter", ("smoked meat",)),
    Survival("rain", "rain on a fire", "Rain puts out a fire under the open sky, so keep your fire under a roof.",
             "keeps its fire under a roof", "rain puts out a fire under the open sky", ("rain",)),
    Survival("storm", "a thunderstorm", "Lightning strikes high ground and tall trees, so in a storm stay low and "
             "inside.", "goes home or down off high ground when a storm starts",
             "lightning strikes high ground, so a storm is for staying low and inside",
             ("storm", "thunderstorm", "lightning"), ("harmless",), ("dangerous",)),
    Survival("fog", "fog", "Fog hides the sun and lets the dark creatures walk by day, so stay close to home in the "
             "fog.", "stays close to home in fog and starts no trips", "fog lets the dark creatures walk by day",
             ("fog",), ("safe",), ("dangerous",)),
)
BY_NAME = {lesson.name: lesson for lesson in SURVIVAL}
SOURCES = {TAUGHT: "from_you", BORN_KNOWING: "from_start"}
# What a wild pet has only once it knows a lesson (the table's "Unlocks" column): the purposes on offer
# (purposes.is_valid), the goals (goals.is_open) and the fittings of a shelter it makes and puts in
# (building.fittings_due, and the warm_up reflex's carried fire). The recipes behind them are gated where
# they are planned: a campfire (cooking, camp, expedition), a bed and a door (building).
PURPOSE_LESSONS = {"build_shelter": "shelter", "improve_home": "shelter", "camp": "shelter", "light_up": "light"}
GOAL_LESSONS = {"first_shelter": "shelter", "safe_yard": "light"}
FITTING_LESSONS = {"bed": "bed", "campfire": "fire", "door": "shelter"}
# What a wild newborn eats by instinct (the familiar foods; raw meat and fish carry a risk until it knows
# cooking), and the foods it has to try first: the red berries (bright red berries and nightberries, one
# group to a pet that does not know nightberries yet) and red mushrooms (backend.survival.meals).
FAMILIAR = ("apple", "carrot", "bread", "brown_mushroom", "raw_fish", "cooked_fish", "raw_beef", "raw_mutton",
            "raw_chicken", "raw_rabbit", "cooked_beef", "cooked_mutton", "cooked_chicken", "cooked_rabbit")
RED_BERRIES = ("berries", "nightberries")
BERRY_BUSHES = ("berry_bush_ripe", "nightberry_bush_ripe")
NIGHTBERRIES = ("nightberries", "nightberry_bush_ripe")
# What Mimo's own words call an item it cannot tell apart (W1 fix round 1): nightberries look like red berries
# to it. The owner's lessons and the journal, which may know better, name them as they are.
LOOKS_LIKE = {"nightberries": "red_berries"}
RED_MUSHROOM = "red_mushroom"  # the item and the block
SAFE = tuple(item for item in FAMILIAR if not item.startswith("raw_"))  # eaten with no risk at all
SHUN = 7200.0  # game seconds (2 game days) a group that made Mimo sick is left alone


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


def purpose_open(name: str, s: Situation) -> bool:
    """The purpose `name` may be offered: it needs no lesson, or Mimo may use what its lesson unlocks."""
    lesson = PURPOSE_LESSONS.get(name)
    return lesson is None or unlocked(s, lesson)


def goal_open(name: str, s: Situation) -> bool:
    """The goal `name` may be offered (a built home needs `wild:shelter`, a safe yard `wild:light`)."""
    lesson = GOAL_LESSONS.get(name)
    return lesson is None or unlocked(s, lesson)


def fitting_open(block: str, s: Situation) -> bool:
    """Mimo may make and put in the fitting `block` (a bed, a campfire, a door)."""
    lesson = FITTING_LESSONS.get(block)
    return lesson is None or unlocked(s, lesson)


def shunned(state: dict, group: str, at: float, scale: float) -> bool:
    """Mimo leaves the food `group` alone now: it made Mimo sick less than SHUN game seconds ago."""
    since = ((state.get("wild") or {}).get("shun") or {}).get(group)
    return since is not None and (at - since) * scale < SHUN


def avoided(state: dict, lessons, at: float, scale: float, shun: bool = True) -> tuple[str, ...]:
    """The foods (items and the blocks they grow on) Mimo never picks or eats now: for a gentle pet the
    nightberries it knows from the start; for a wild one what it knows is poison (nightberries, red
    mushrooms) and (`shun`) a group it shuns (the red berries after they made it sick). W1's final fix wave: a
    shunned food is only left alone, never poison to throw away (situation.Situation.discards)."""
    if not is_wild(state):
        return NIGHTBERRIES
    found: list[str] = []
    if thing("nightberries") in lessons:
        found += NIGHTBERRIES
    if thing("red_mushroom") in lessons:
        found.append(RED_MUSHROOM)
    if shun and shunned(state, "red_berries", at, scale):
        found += (*RED_BERRIES, *BERRY_BUSHES)
    return tuple(dict.fromkeys(found))


def poisons_known(db: sqlite3.Connection, state: dict, at: float, scale: float) -> tuple[str, ...]:
    """What Mimo knows is poisonous (memory's "poisonous", M4) and what it avoids (`avoided`), for code that
    reads memory without a Situation (backend.survival.learning, backend.survival.exploring)."""
    return tuple(dict.fromkeys((*known(db, "poisonous"), *avoided(state, set(known(db, LESSON)), at, scale))))


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
    if state["difficulty"] != GENTLE or db is None or ((state.get("wild") or {}).get("granted") or 0) >= GRANTED:
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
