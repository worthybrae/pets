"""W1: learning alone, by knocks ("Learning alone: knocks" of the Wild World spec).

A knock is a painful experience. On each one the lesson it can teach is rolled for (a seeded roll,
nature.roll) against a chance that grows with every knock of that lesson: `first + step x knocks so far`,
times `0.8 + curiosity / 250` (0.8 to 1.2). Some experiences teach for sure. A lesson learned this way is
learned as the journal learns (backend.survival.journal), with a notable "figured" event instead ("Pip worked
out that cooking makes meat safe."), memory_knowledge's second fact wild.FIGURED, a discovery for curiosity,
and the journal line "I worked it out myself: ...". The counts live in `state["wild"]["knocks"]`.

| Lesson | Knock | First | Step | Sure when |
|---|---|---|---|---|
| berries | | | | it eats from the red berries and is not sick |
| nightberries | sick from a nightberry | 0.25 | 0.15 | |
| red_mushroom | | | | sick from a red mushroom |
| fire | a chilled night | 0.15 | 0.15 | it smelts at a furnace for the first time |
| cooking | sick from a raw meal, knowing fire | 0.25 | 0.15 | |
| keeping | sick from spoiled food, or food spoils in its arms or chest | 0.20 | 0.15 | |
| light | a hostile's blow at night | 0.10 | 0.10 | |
| shelter | a bad night: a chill at dawn, or a hostile's blow that night | 0.25 | 0.20 | |
| bed | a night asleep on the floor of a sheltered spot | 0.10 | 0.10 | |

The chances are as unlikely as the gate's "not hopeless" criteria allow (spec resolution 29, the controller's
ruling on the W1 dry run): each first chance is one step (0.05) lower than first planned, and a second step left
pets that knew only 6 or 7 lessons alone by day 60. Two lessons are never learned alone (OWNER_ONLY, the same
ruling): sunleaf and bandage. A pet cannot guess that an herb cures a sickness, or that wool on a wound stops it
festering. A sunleaf the instinct nibbles while sick (backend.survival.herbs) makes Mimo better that once and
teaches nothing; Mimo still asks about the herb and its wounds, and the owner's answer or teaching is the only
way in.

The knocks are heard where they happen: finished steps (steps.OBSERVERS: eating, smelting), blows
(harm.BLOWS), dawn (ailments.DAWN) and spoiled food (spoilage.SPOILS). Learning the difference between the red
berries lifts their shun at once. Only a wild pet has knocks; a gentle pet knows every lesson already.
LEARNED hears of each lesson worked out (the questions Mimo asked close as "figured out":
backend.survival.questions). A crash is logged once and teaches nothing.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from backend.survival.ailments import DAWN
from backend.survival.creatures.harm import BLOWS
from backend.survival.curiosity import GROUND_FLOOR, discovered, value_of
from backend.survival.journal import FACT, NEW_LESSON, journal_state
from backend.survival.memory import know
from backend.survival.nature import roll
from backend.survival.once import log_once
from backend.survival.spoilage import SPOILED, SPOILS
from backend.survival.steps import OBSERVERS
from backend.survival.triggers import mark_trigger
from backend.survival.wild import BY_NAME, FIGURED, RED_BERRIES, RED_MUSHROOM, SURVIVAL, is_wild, thing, wild_state

logger = logging.getLogger(__name__)

KNOCK_CHANNEL = 206  # and one more for each lesson, in the table's order (206 to 216)
OWNER_ONLY = ("sunleaf", "bandage")  # never learned alone: only the owner teaches them
# W1: functions (db, state, name, at) run when Mimo works a survival lesson out alone. One that crashes is logged once.
LEARNED: list = []


@dataclass(frozen=True)
class Knock:
    first: float
    step: float


KNOCKS: dict[str, Knock] = {
    "nightberries": Knock(0.25, 0.15), "fire": Knock(0.15, 0.15),
    "cooking": Knock(0.25, 0.15), "keeping": Knock(0.20, 0.15), "light": Knock(0.10, 0.10),
    "shelter": Knock(0.25, 0.20), "bed": Knock(0.10, 0.10),
}


def known(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact=?", (thing(name), FACT)).fetchone() is not None


def pet_cell(state: dict) -> tuple[int, int, int]:
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def figure(state: dict, db: sqlite3.Connection, events: list, at: float, name: str) -> bool:
    """Mimo works the lesson `name` out alone. True the first time; never for an OWNER_ONLY lesson."""
    lesson = BY_NAME[name]
    if name in OWNER_ONLY or not know(db, thing(name), FACT, at):
        return False
    know(db, thing(name), FIGURED, at)
    events.append((at, "figured", f"{state['name']} worked out that {lesson.figured}."))
    journal = journal_state(state)
    journal["words"] = {**journal["words"], thing(name): f"I worked it out myself: {lesson.fact[:1].lower()}{lesson.fact[1:]}"}
    discovered(state, at, min(NEW_LESSON, max(0.0, value_of(state.get("brain")) - GROUND_FLOOR)))
    mark_trigger(state, "discovery", at)
    state["last_thought"] = f"I worked it out: {lesson.figured}!"
    if name == "nightberries":
        wild_state(state)["shun"].pop("red_berries", None)  # it knows the difference now
    for learned in LEARNED:
        try:
            learned(db, state, name, at)
        except Exception as error:
            log_once(logger, "learned alone", error)
    return True


def knock(state: dict, db: sqlite3.Connection | None, events: list, at: float, name: str) -> bool:
    """A knock for the lesson `name`: rolled for at its growing chance. True when it taught the lesson."""
    if not is_wild(state) or db is None or name not in KNOCKS or known(db, name):
        return False
    rule = KNOCKS[name]
    counts = wild_state(state)["knocks"]
    so_far = counts.get(name, 0)
    counts[name] = so_far + 1
    curiosity = float(state.get("traits", {}).get("curiosity", 50))
    chance = (rule.first + rule.step * so_far) * (0.8 + curiosity / 250)
    channel = KNOCK_CHANNEL + [lesson.name for lesson in SURVIVAL].index(name)
    if roll(state.get("world_seed", "0"), pet_cell(state), channel, int(at)) >= chance:
        return False
    return figure(state, db, events, at, name)


def sure(state: dict, db: sqlite3.Connection | None, events: list, at: float, name: str) -> bool:
    """An experience that teaches `name` for sure."""
    if not is_wild(state) or db is None:
        return False
    return figure(state, db, events, at, name)


def guarded(teach) -> None:
    try:
        teach()
    except Exception as error:
        log_once(logger, "knocks", error)


# Where the knocks are heard ----------------------------------------------------------------------

def after_step(state: dict, step: dict, context, at: float) -> None:
    """steps.OBSERVERS: eating and smelting."""
    db, events = context.db, context.events
    item = step.get("item")
    if step["kind"] == "eat":
        if item in RED_BERRIES and not step.get("sick"):
            guarded(lambda: sure(state, db, events, at, "berries"))
        elif item == "nightberries":
            guarded(lambda: knock(state, db, events, at, "nightberries"))
        elif item == RED_MUSHROOM and step.get("sick"):
            guarded(lambda: sure(state, db, events, at, "red_mushroom"))
        elif item == SPOILED and step.get("sick"):
            guarded(lambda: knock(state, db, events, at, "keeping"))
        elif step.get("raw") and step.get("sick") and db is not None and known(db, "fire"):
            guarded(lambda: knock(state, db, events, at, "cooking"))
    elif step["kind"] == "smelt":
        guarded(lambda: sure(state, db, events, at, "fire"))


def blown(scene, lost: float, source: str) -> None:
    """harm.BLOWS: a hostile's blow at night."""
    if scene.night:
        guarded(lambda: knock(scene.state, scene.herd.db, scene.events, scene.at, "light"))


def at_dawn(state: dict, context, summary: dict, at: float) -> None:
    """ailments.DAWN: a chilled night, a bad night, a night on the floor."""
    db, events = context.db, context.events
    if summary["chill"]:
        guarded(lambda: knock(state, db, events, at, "fire"))
    if summary["chill"] or summary["blows"]:
        guarded(lambda: knock(state, db, events, at, "shelter"))
    if summary["floor"]:
        guarded(lambda: knock(state, db, events, at, "bed"))


def spoils(state: dict, context, item: str, count: int, where: str, at: float) -> None:
    """spoilage.SPOILS: food went bad in Mimo's arms or chest."""
    guarded(lambda: knock(state, context.db, context.events, at, "keeping"))


OBSERVERS.append(after_step)
BLOWS.append(blown)
DAWN.append(at_dawn)
SPOILS.append(spoils)
