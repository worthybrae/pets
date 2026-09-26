"""What Mimo remembers of what happens (Mind M1): the moments, in its own words.

Mind's memory follows the event log as the consumer "memory" of the survival core's mirrors
(backend.survival.events, which the worker's Talker runs every few seconds, outside the tick). The
mirrors keep one writer a consumer and kind, so every Mind writer goes through `follow_event`:
FOLLOWERS holds Mind's own writers by event kind (and EVERY's, for every followed event), and
`followed` has the mirrors hand Mind the events of a kind. Each writer runs in a savepoint of its
own, so one that crashes is rolled back alone (its database writes and state["mind"]), logged once
and passed over. A consumer the mirrors meet for the first time starts at the newest event; Mind's
memory goes back (`from_the_start`, a chore after the mirrors, once a life, which reads the first
batch at once) to the first event, or BACKFILL events before the newest in a very long life, so a
pet from before Mind (Pebble on day 55) starts with its past, not a blank mind: bounded, caught up
events.MIRROR_BATCH events a chore, and never more than the stream's cap.

A new event whose kind is in MOMENTS becomes a memory: an episode, or a lesson for a "learned"
event, with the table's importance and feeling (a first sighting 6, a goal reached 7, a meal 1),
dated by the game day it happened on and written in Mimo's voice: "Pip met its first skitter."
becomes "I met my first skitter.", "You gave Pip a snack." becomes "You gave me a snack.". A "plan"
event is a moment only for a goal set, a step finished or a goal set aside or given up
(PLAN_MOMENTS), remembered without the goal's quoted thought or the reason in brackets ("I set a
new goal: map the far hills."), and a sapling growing is not one. A goal reached again, or a camp
made again, whose words Mimo already remembers, is a smaller moment (AGAIN): it fades like a routine
one and lives on in its day's gist, so the moments that mattered stay the first ones. Routine
events (a purpose chosen, a craft, falling asleep, waking...) never become memories one by one: the
day's gist sums them up (backend.survival.consolidation). A moment with `many` words is one that
repeats in a day, and consolidation merges its repeats ("I ate 5 meals.").

What the owner tells about themselves (Bond's owner facts) is a told memory, kept as the fact is
kept (owner_facts.FACT_MIRRORS), never through the event log: "You told me your name is Sam."
(importance 6, about the owner); a fact heard again strengthens it. A told memory holds the owner's
words, so it never reaches Luna (mind.story_memories). No event says that Mimo nearly died, so the
`near_death` chore notices it: health under NEAR_DEATH is a moment of importance 9, at most once a
game day.
"""

from __future__ import annotations

import copy
import logging
import re
import sqlite3
from dataclasses import dataclass

from backend.survival.clock import clock_at, time_scale
from backend.survival.events import CURSORS, mirror, mirror_events
from backend.survival.mind import add_memory, mind_state, rehearse
from backend.survival.once import log_once
from backend.survival.owner_facts import FACT_MIRRORS
from backend.survival.replies import echoed, first_person, told
from backend.survival.steps import label
from backend.survival.talker import CHORES
from backend.survival.triggers import HOUR
from backend.survival.world import read_state

logger = logging.getLogger(__name__)

NEAR_DEATH = 15.0  # health under which Mimo nearly died
BACKFILL = 20_000  # events back from the newest that a pet from before Mind remembers (some 300 game days)
CONSUMER = "memory"  # Mind's cursor on the event log: state["mirrored"]["memory"]
EVERY = "*"
# {event kind (or EVERY): [write(db, state, event, now, scale)]}: Mind's writers for the events its memory
# follows, run in this order, EVERY's last.
FOLLOWERS: dict[str, list] = {}


@dataclass(frozen=True)
class Moment:
    importance: int
    feeling: int
    kind: str = "episode"  # or "lesson", for what Mimo learned
    many: str = ""  # several in one game day, merged by consolidation: "{n}" is how many
    about: tuple[str, ...] = ()  # tags every such moment has


MOMENTS: dict[str, Moment] = {
    "birth": Moment(8, 2),
    "found": Moment(6, 1),
    "discovered": Moment(5, 1),
    "explore": Moment(2, 1, many="I found {n} new things out exploring."),
    "learned": Moment(5, 1, kind="lesson"),
    "goal": Moment(7, 2),
    "built": Moment(7, 2),
    "computer": Moment(8, 2),  # Making final fix wave (M2): the machine that remembers how long Mimo has lived
    "sick": Moment(5, -2),
    "hunt": Moment(2, 1, many="I hunted {n} times."),
    "fish": Moment(1, 1, many="I caught {n} fish."),
    "ate": Moment(1, 1, many="I ate {n} meals."),
    "hungry": Moment(2, -1, many="I got hungry {n} times."),
    "starving": Moment(7, -2),
    "freezing": Moment(6, -2),
    "fall": Moment(5, -2, many="I fell and got hurt {n} times."),
    "trapped": Moment(6, -2),
    "hurt": Moment(4, -2, many="I got hit {n} times."),
    "threat": Moment(3, -1, many="I saw {n} creatures coming after me."),
    "fight": Moment(6, 1),
    "expedition": Moment(7, 1),
    "camp": Moment(6, 1),
    "grow": Moment(4, 1),
    "hello": Moment(3, 1, many="You said hello to me {n} times.", about=("owner",)),
    "care": Moment(5, 2, about=("owner",)),
    "owner": Moment(3, 1, many="You helped me {n} times.", about=("owner",)),
}
# A "plan" event is a moment when its words say one of these.
PLAN_MOMENTS = ((" set a new goal: ", Moment(4, 1)), (" finished a step toward ", Moment(4, 1)),
                (" set a goal aside", Moment(4, -1)), (" gave up trying to ", Moment(3, -1)))
# Final fix wave (I4): a goal reached again or another camp like one Mimo remembers is this important,
# not a moment that matters forever (goals can repeat: "look into a cave" was reached 15 times in a
# 60-day life, and at the cap it would have outlived first sightings and fights).
AGAIN = {"goal": 4, "camp": 4}
# What a plan memory leaves out (I3): the reason in brackets and the goal's quoted thought.
_ASIDE = re.compile(r'\s*\([^)]*\)|\s*"[^"]*"')
# What the owner told about themselves, as Mimo remembers it (owner_facts' kinds).
TOLD_FACTS = {"name": "You told me your name is {words}.", "likes": "You told me you like {words}.",
              "dislikes": "You told me you don't like {words}.", "about": "You told me {words}."}


def followed(kind: str, write=None) -> None:
    """Follow the events of `kind` in Mind's memory, `write` among its writers (EVERY: for every event
    followed)."""
    if write is not None:
        FOLLOWERS.setdefault(kind, []).append(write)
    if kind != EVERY:
        mirror(CONSUMER, kind, follow_event)


def follow_event(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """The mirrors' writer for Mind's memory: every Mind writer of the event's kind, then EVERY's."""
    for write in (*FOLLOWERS.get(event["kind"], ()), *FOLLOWERS.get(EVERY, ())):
        mind = copy.deepcopy(state.get("mind"))
        db.execute("SAVEPOINT memory_write")
        try:
            write(db, state, event, now, scale)
        except Exception as error:
            db.execute("ROLLBACK TO memory_write")
            state.pop("mind", None)
            if mind is not None:
                state["mind"] = mind
            log_once(logger, f"memory {event['kind']} {getattr(write, '__name__', write)}", error)
        db.execute("RELEASE memory_write")


def from_the_start(db: sqlite3.Connection, state: dict, now: float, scale: float) -> bool:
    """A chore, once a life: Mind's memory goes back to the first event (at most BACKFILL events before
    the newest), where the mirrors started it at the newest, and reads the first batch at once."""
    mind = mind_state(state)
    if mind["started"]:
        return False
    mind["started"] = True
    newest = db.execute("SELECT COALESCE(MAX(id), 0) FROM mimo_events").fetchone()[0]
    state.setdefault(CURSORS, {})[CONSUMER] = max(0, newest - BACKFILL)
    mirror_events(db, state, now, scale)
    return True


def voice(text: str, name: str) -> str:
    """An event in Mimo's own voice: about it ("Pip met its first skitter." -> "I met my first
    skitter.") or about the owner and it ("You gave Pip a snack." -> "You gave me a snack.")."""
    text = first_person(text, name).replace(" in my walls", " in its walls")  # a cave mouth's walls
    return text.replace(f"{name}'s ", "my ").replace(f" {name}", " me")


def moment_of(event: dict, name: str) -> Moment | None:
    kind, text = event["kind"], event["text"]
    if kind == "plan":
        return next((moment for words, moment in PLAN_MOMENTS if words in text), None)
    if kind == "grow" and "creature seed" not in text:
        return None  # a sapling growing into a tree is not a moment
    return MOMENTS.get(kind)


def game_day(state: dict, at: float, scale: float) -> int:
    return clock_at(state["born_at"], at, scale)["day_number"]


def moment_text(event: dict, name: str) -> str:
    """The event in Mimo's voice; a plan without its quoted thought or bracketed reason."""
    text = voice(event["text"], name)
    return _ASIDE.sub("", text) if event["kind"] == "plan" else text


def remember_moment(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """A Mind writer: the event as a memory, when it is a moment (a smaller one when it is AGAIN)."""
    moment = moment_of(event, state["name"])
    if moment is not None:
        day = game_day(state, event["at"], scale)
        text = moment_text(event, state["name"])
        importance = moment.importance
        if event["kind"] in AGAIN and db.execute("SELECT 1 FROM mind_memories WHERE source=? AND text=? LIMIT 1",
                                                 (event["kind"], text)).fetchone():
            importance = min(importance, AGAIN[event["kind"]])
        add_memory(db, event["at"], day, moment.kind, text, moment.about, importance, moment.feeling,
                   source=event["kind"])


for _kind in (*MOMENTS, "plan"):
    followed(_kind, remember_moment)
CHORES.append(from_the_start)


def remember_told(db: sqlite3.Connection, kind: str, words: str, at: float, new: bool) -> None:
    """An owner_facts.FACT_MIRRORS writer: a fact the owner told is a told memory; heard again, that
    memory grows stronger."""
    if kind not in TOLD_FACTS:
        return
    said = told(words) if kind == "about" else echoed(words) if kind in ("likes", "dislikes") else words
    text = TOLD_FACTS[kind].format(words=said)
    if not new:
        row = db.execute("SELECT id FROM mind_memories WHERE kind='told' AND source='owner_fact' AND text=? "
                         "ORDER BY id DESC LIMIT 1", (text,)).fetchone()
        if row is not None:
            rehearse(db, [row[0]], at)
            return
    add_memory(db, at, game_day(read_state(db), at, time_scale()), "told", text, ("owner",), 6, 1, "owner_fact")


FACT_MIRRORS.append(remember_told)


def near_death_words(state: dict, now: float, scale: float) -> tuple[str, tuple[str, ...]]:
    vitals, hurt_at = state["vitals"], state.get("hurt_at")
    if state.get("hurt_by") and hurt_at is not None and (now - hurt_at) * scale <= HOUR:
        return f"I nearly died: a {label(state['hurt_by'])} almost got me.", (state["hurt_by"],)
    if vitals.get("hunger", 100.0) <= 5:
        return "I nearly starved to death.", ("food",)
    if vitals.get("warmth", 100.0) <= 10:
        return "I nearly froze to death.", ()
    if vitals.get("air", 100.0) <= 10:
        return "I nearly drowned.", ("water",)
    return "I nearly died.", ()


def near_death(db: sqlite3.Connection, state: dict, now: float, scale: float) -> bool:
    """A chore: health under NEAR_DEATH is remembered (importance 9), at most once a game day."""
    mind = mind_state(state)
    day = game_day(state, now, scale)
    if state["vitals"]["health"] >= NEAR_DEATH or mind["near_death"] >= day:
        return False
    text, about = near_death_words(state, now, scale)
    add_memory(db, now, day, "episode", text, about, 9, -2, source="near_death")
    mind["near_death"] = day
    return True


CHORES.append(near_death)
