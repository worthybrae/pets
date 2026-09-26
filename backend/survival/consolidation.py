"""Sleep consolidates the day (Mind M1).

When Mimo falls asleep in the evening (a "sleep" event from dusk on), Mind's memory hands it to
`night_sleep` (backend.survival.episodes.followed), which consolidates the game day just ended
(`consolidate`), in rules only, inside the Talker chore's one short transaction:
1. the day's repeats of a routine moment (a MOMENTS entry with `many` words: meals, fish, blows)
   are merged into one ("I caught 9 fish."), when there are MERGE_AT or more; a moment of
   importance KEEP_WHOLE or more is always kept whole;
2. a gist of the day is written ("Day 12: reached my goal of iron tools, met my first skitter and
   learned three things."): its biggest moments in Mimo's own words (`clause`, GIST_PHRASES: never
   the event log's "goal: title"), what it learned, what it ate and made, from the day's memories
   and the tally of every event the memory read that day (its meals from the tally, so a meal the
   cap forgot before sleep is still counted);
3. what faded is forgotten: an episode or lesson under KEEP_WHOLE whose keep_score (importance x
   strength against age, mind.keep_score) fell under 1; it lives on only in its day's gist;
4. the stream is brought back within the cap (mind.enforce_cap).
A day that ended without an evening sleep (a night on the trail, a worker catching up) is
consolidated when the memory first reads an event of a later day (`day_tally`, which sees every
event the memory follows: the moments and TALLIED). Consolidation runs inside the mirror
(events.mirror_events), as Mind's writer for the "sleep" event, never on its own: every event logged
before the sleep has been read by then, so nothing the mirrors lag behind on is left out of the day.
A gist never holds a told memory or any memory about the owner (the owner's words stay out of
whatever reads gists, Luna's story among them). Each day is consolidated once
(state["mind"]["day"]); then the NIGHTLY hooks run (Mind M2's reflection), each crash-guarded.

A life that ends closes its mind once (`last_day`, one of the Talker's LAST_CHORES, the final fix
wave's I6): the events logged since the last chore are read, and the day it died on, which no
evening sleep consolidated, gets its gist. Only a life Mind followed (its state has "mind") and has
not closed yet (`unclosed`): a dead pet's archive from before Mind is never opened for writing.
"""

from __future__ import annotations

import copy
import logging
import re
import sqlite3

from backend.survival.clock import clock_at
from backend.survival.episodes import EVERY, MOMENTS, followed, game_day
from backend.survival.events import mirror_events
from backend.survival.mind import (
    FADE, KEEP_SCORE, MEMORY_COLUMNS, TAGS_KEPT, TEXT_LIMIT, Memory, add_memory, enforce_cap, forget, memory_of,
    mind_state,
)
from backend.survival.once import log_once
from backend.survival.replies import SENTENCE_END, starts_with_verb
from backend.survival.situation import DUSK
from backend.survival.talker import LAST_CHORES

logger = logging.getLogger(__name__)

MERGE_AT = 3  # repeats of a routine moment in a day that are merged into one
KEEP_WHOLE = 6  # importance from which a moment is never merged and never fades
GIST_MOMENTS = 3  # moments a gist names
NUMBERS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")
# What a gist says of the day's tally of routine events, the busiest one: "crafted six things".
TALLY_WORDS = {"craft": ("crafted {n} thing", "s"), "cook": ("cooked {n} time", "s"), "smelt": ("smelted {n} ore", "s")}
TALLIED = (*TALLY_WORDS, "sleep", "wake")  # routine kinds the memory follows only to count them and to see a new day
# {name: hook(db, state, day, at, scale)}: run after a day is consolidated (Mind M2's reflection).
NIGHTLY: dict = {}
LAST_BATCHES = 10  # event batches (events.MIRROR_BATCH each) an ended life still reads, at most


def number(n: int) -> str:
    return NUMBERS[n] if 0 <= n < len(NUMBERS) else str(n)


def goal_words(said: str, title: str) -> str:
    """A goal's event words said plainly, for a title that is something to do ("look into a cave")
    or a thing ("iron tools")."""
    doing = starts_with_verb(title)
    if said == "reached":
        return f"managed to {title}" if doing else f"reached my goal of {title}"
    if said == "new":
        return f"decided to {title}" if doing else f"set my heart on {title}"
    return f"put off trying to {title}" if doing else f"put {title} aside for now"


# The event log's shapes, as Mimo says them (the final fix wave's I3): "reached a goal: iron tools"
# -> "reached my goal of iron tools", "finished a step toward an expedition: camp out for the night"
# -> "took a step toward an expedition", "came home from my expedition: 162 blocks out, 1 night
# camped, ..." -> "came home from my expedition 162 blocks out"; and the near death's own colon, "nearly
# died: a gloomling almost got me" -> "was nearly killed by a gloomling".
GIST_PHRASES = (
    (re.compile(r"^reached a goal: (.+)$"), lambda found: goal_words("reached", found[1])),
    (re.compile(r"^set a new goal: (.+)$"), lambda found: goal_words("new", found[1])),
    (re.compile(r"^set a goal aside for now: (.+)$"), lambda found: goal_words("aside", found[1])),
    (re.compile(r"^finished a step toward (.+?): .+$"), lambda found: f"took a step toward {found[1]}"),
    (re.compile(r"^came home from my expedition: (\d+) blocks out\b.*$"),
     lambda found: f"came home from my expedition {found[1]} blocks out"),
    (re.compile(r"^nearly died: (an? .+?) almost got me$"), lambda found: f"was nearly killed by {found[1]}"),
)


def plainly(words: str) -> str:
    """Words of Mimo's (without its leading "I ") with the event log's shapes said plainly (GIST_PHRASES)."""
    for pattern, say in GIST_PHRASES:
        found = pattern.match(words)
        if found:
            return say(found)
    return words


def clause(text: str) -> str:
    """A memory as part of a gist: "I met my first skitter." -> "met my first skitter"; the first
    sentence only, without what it says in brackets, and the event log's shapes said plainly: "I
    reached a goal: look into a cave." -> "managed to look into a cave"."""
    first = re.sub(r"\s*\([^)]*\)", "", SENTENCE_END.split(text.strip())[0]).rstrip(".!?")
    first = first[2:] if first.startswith("I ") else first[:1].lower() + first[1:]
    return plainly(first)


def joined(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def day_memories(db: sqlite3.Connection, day: int, kinds: tuple[str, ...]) -> list[Memory]:
    marks = ",".join("?" * len(kinds))
    rows = db.execute(f"SELECT {','.join(MEMORY_COLUMNS)} FROM mind_memories WHERE game_day=? AND kind IN ({marks}) "
                      "ORDER BY id", (day, *kinds)).fetchall()
    return [memory_of(row) for row in rows]


def merge_repeats(db: sqlite3.Connection, day: int) -> int:
    """Merge each routine moment's repeats of the day into one memory. Returns how many merged."""
    groups: dict[str, list[Memory]] = {}
    for memory in day_memories(db, day, ("episode",)):
        moment = MOMENTS.get(memory.source)
        if moment is not None and moment.many and memory.importance < KEEP_WHOLE:
            groups.setdefault(memory.source, []).append(memory)
    merged = 0
    for source, found in groups.items():
        if len(found) < MERGE_AT:
            continue
        total = sum(memory.count for memory in found)
        tags = list(dict.fromkeys(tag for memory in found for tag in memory.about))[:TAGS_KEPT]
        forget(db, [memory.id for memory in found])
        add_memory(db, found[-1].at, day, "episode", MOMENTS[source].many.format(n=total), tags,
                   min(KEEP_WHOLE - 1, max(memory.importance for memory in found) + 1),
                   round(sum(memory.feeling for memory in found) / len(found)), source, total,
                   max(memory.strength for memory in found))
        merged += len(found)
    return merged


def times(kind: str, n: int) -> str:
    """ "crafted six things", "cooked once", "cooked twice", "cooked three times"."""
    if kind == "cook" and n in (1, 2):
        return "cooked once" if n == 1 else "cooked twice"
    words, plural = TALLY_WORDS[kind]
    return words.format(n=number(n)) + ("" if n == 1 else plural)


def gist_text(day: int, memories: list[Memory], tally: dict) -> str:
    """ "Day 12: reached my goal of iron tools, met my first skitter, learned three things and ate
    five meals."; "Day 3: a quiet day." when nothing stood out."""
    parts, sources = [], set()
    for memory in sorted(memories, key=lambda memory: (-memory.importance, memory.id)):
        if len(parts) >= GIST_MOMENTS or memory.importance < 4:
            break
        if memory.kind == "lesson" or memory.source in sources:
            continue
        sources.add(memory.source)
        parts.append(clause(memory.text))
    lessons = sum(1 for memory in memories if memory.kind == "lesson")
    if lessons:
        parts.append("learned something new" if lessons == 1 else f"learned {number(lessons)} things")
    # Every meal the memory read is in the day's tally, even one the cap forgot before sleep (I7).
    meals = max(tally.get("ate", 0), sum(memory.count for memory in memories if memory.source == "ate"))
    if meals:
        parts.append(f"ate {number(meals)} meal{'' if meals == 1 else 's'}")
    busiest = max(TALLY_WORDS, key=lambda kind: (tally.get(kind, 0), kind))
    if tally.get(busiest, 0):
        parts.append(times(busiest, tally[busiest]))
    while parts:
        text = f"Day {day}: {joined(parts)}."
        if len(text) <= TEXT_LIMIT:
            return text
        parts.pop(-2 if len(parts) > 1 else -1)
    return f"Day {day}: a quiet day."


def write_gist(db: sqlite3.Connection, day: int, at: float, tally: dict) -> int:
    """The day's gist: as important as its biggest moment (3 to 9), its mood the day's on the
    whole, about what its words name; never from a told memory or one about the owner."""
    memories = [memory for memory in day_memories(db, day, ("episode", "lesson")) if "owner" not in memory.about]
    importance = max([3, *(memory.importance for memory in memories)])
    feeling = round(sum(memory.feeling for memory in memories) / len(memories)) if memories else 0
    return add_memory(db, at, day, "gist", gist_text(day, memories, tally), (), min(9, importance), feeling, "gist",
                      max(1, sum(tally.values())))


def fade(db: sqlite3.Connection, today: int) -> int:
    """Forget the small episodes and lessons whose keep_score fell under 1. Returns how many."""
    ids = [row[0] for row in db.execute(
        f"SELECT id FROM mind_memories WHERE kind IN ('episode', 'lesson') AND importance < ? AND game_day < ? "
        f"AND {KEEP_SCORE} < 1", (KEEP_WHOLE, today, FADE, FADE, today)).fetchall()]
    forget(db, ids)
    return len(ids)


def consolidate(db: sqlite3.Connection, state: dict, day: int, at: float, scale: float) -> bool:
    """Consolidate a game day once: merge its repeats, write its gist, forget what faded, keep the
    cap, then run the NIGHTLY hooks. False when the day was consolidated already."""
    mind = mind_state(state)
    if day <= mind["day"]:
        return False
    tally = mind["tally"]["kinds"] if mind["tally"]["day"] == day else {}
    merge_repeats(db, day)
    write_gist(db, day, at, tally)
    fade(db, day)
    enforce_cap(db, day)
    mind["day"] = day
    for name, hook in list(NIGHTLY.items()):
        mind = copy.deepcopy(state.get("mind"))
        db.execute("SAVEPOINT nightly")
        try:
            hook(db, state, day, at, scale)
        except Exception as error:
            db.execute("ROLLBACK TO nightly")
            state.pop("mind", None)
            if mind is not None:
                state["mind"] = mind
            log_once(logger, f"nightly {name}", error)
        db.execute("RELEASE nightly")
    return True


def night_sleep(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """A mirror writer: falling asleep from dusk on consolidates the day just ended."""
    clock = clock_at(state["born_at"], event["at"], scale)
    if clock["seconds_into_day"] >= DUSK:
        consolidate(db, state, clock["day_number"], event["at"], scale)


def day_tally(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """A mirror writer for every event: count it for its day's gist; the first event of a later day
    consolidates a day that ended without an evening sleep."""
    mind = mind_state(state)
    day, tally = game_day(state, event["at"], scale), mind["tally"]
    if day > tally["day"]:
        if mind["day"] < tally["day"]:
            consolidate(db, state, tally["day"], event["at"], scale)
        mind["tally"] = tally = {"day": day, "kinds": {}}
    if day == tally["day"]:
        tally["kinds"][event["kind"]] = tally["kinds"].get(event["kind"], 0) + 1


def unclosed(state: dict) -> bool:
    """Whether an ended life is one Mind followed (its state has "mind") and has not closed yet."""
    mind = state.get("mind")
    return isinstance(mind, dict) and not mind.get("closed")


def last_day(db: sqlite3.Connection, state: dict, now: float, scale: float) -> bool:
    """A Talker LAST_CHORES chore, once a life (state["mind"]["closed"]): the events logged since the
    last chore are read (at most LAST_BATCHES batches), then the day the tally was counting, the day
    Mimo died on, which no evening sleep consolidated, is consolidated at the moment it died. A day
    already consolidated is not again."""
    if not unclosed(state):
        return False
    for _ in range(LAST_BATCHES):
        if not mirror_events(db, state, now, scale):
            break
    mind = mind_state(state)  # a writer that crashed may have restored state["mind"]
    consolidate(db, state, mind["tally"]["day"], state["died_at"], scale)
    mind_state(state)["closed"] = True
    return True


followed("sleep", night_sleep)
followed(EVERY, day_tally)
for _kind in TALLIED:
    followed(_kind)
LAST_CHORES.append((unclosed, last_day))
