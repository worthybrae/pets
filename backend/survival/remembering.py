"""Chat replies that remember (Mind M2).

Mimo's reply lines (backend.survival.replies) gain two written from its memory, each worked out once
a chat job by a talk.HEARING hook (into Heard.context), with the owner's words as the cue:
- "trip": asked about a trip just made ("Welcome home! How was your trip?"), Mimo answers from its
  homecoming memory, its direction from the setting out: "It was wonderful! I went 249 blocks east,
  camped two nights and learned two new things." ("a wild one" when it got hurt or nearly died on
  the way). It weighs TRIP_WEIGHT, so it answers before how Mimo feels or a greeting. Just after a
  homecoming, a question that only asks about being away ("did you have fun out there?", "where
  did you go?", "how was it?": TRIP_QUESTIONS, only with a "?") asks about the trip too.
- "memory": what the owner's words bring back (mind.recall, rules only), said in Mimo's voice: "I
  remember when I met my first skitter.", "I remember day 12: ...", "I keep thinking: I love fishing
  by the lake.". A memory comes back when the words name a thing Mimo remembers (the memory covers
  at least THING_MATCH of the cue; a time of day, TIMES, is no such thing: "is it night yet?"
  recalls nothing) or ask it to remember (MEMORY_WORDS) and something relates; "yesterday" brings
  back yesterday's gist. A goal or a trip is said plainly, as its day's gist says it ("I remember
  when I managed to look into a cave."). What the owner told of themselves is never said back
  here: that is Bond's to say (its "remember" and "fond" lines), and everyday words must not bring
  it up. It weighs
  WEIGHT plus how much of the cue it covers (and one more when asked), so a real memory answers "do
  you remember the skitter?" before what Mimo knows of its owner. The weights share one scale with
  the topics' keyword counts and replies.TOLD (10): a memory the words do not cue is never offered,
  so recall never crowds out a direct answer, and "I love you", which names no thing, keeps its
  usual answer.
Each line's note names its memory ({"memory": id}); when the line is chosen and stored, the "reply"
keeper hands the note to REPLY_KEEPERS, which rehearses the memory (mind.rehearse): the one write,
in the reply's own transaction. Writing the lines only reads.
"""

from __future__ import annotations

import re
import sqlite3

from backend.survival.consolidation import clause, joined, number, plainly
from backend.survival.mind import MEMORY_COLUMNS, Memory, cue_of, memory_of, recall, rehearse
from backend.survival.replies import ABOUT, REPLIES, Heard, Reply, clip
from backend.survival.situation import Situation
from backend.survival.talk import HEARING, REPLY_KEEPERS

MEMORY, TRIP = "memory", "trip"
OWNER_FACT = "owner_fact"  # the source of a told memory of what the owner said of themselves (episodes.remember_told)
RECALLED = 3  # memories a recall brings up for the line
THING_MATCH = 0.5  # how much of the cue a memory must cover when the words do not ask to remember
WEIGHT = 1.0  # the memory line's weight, with how much of the cue it covers on top (only when the words cue it)
TRIP_WEIGHT = 4.0
TRIP_FRESH = 1  # game days after coming home that the trip is still the one asked about
TIMES = frozenset({"night", "day", "dark", "light", "sun", "morning", "evening"})  # everyday words, not things
MEMORY_WORDS = frozenset({"remember", "remembered", "recall", "when", "yesterday", "ago", "story", "happened"})
TRIP_WORDS = frozenset({"trip", "journey", "expedition", "adventure", "travels", "travel"})
TRIP_PAIRS = ("welcome home", "welcome back")
# Asked just after a homecoming (trip_told finds one only then) and ending with "?", these ask about
# the trip too; "it's cold out there" does not (the final fix wave's M3).
TRIP_QUESTIONS = ("out there", "where did you go", "where have you been", "how was it", "you're back", "youre back")
ROUGH = ("hurt", "near_death", "fight", "threat", "starving", "freezing", "trapped", "fall")
_GIST = re.compile(r"^Day (\d+): (.*)$")
_HOME = re.compile(r"came home from my expedition: (\d+) blocks out, (\d+) nights? camped, (\d+) new things? learned")
_OUT = re.compile(r"set out on an expedition to the (\w+)")


def recalled_line(memory: Memory) -> str:
    """A memory as Mimo says it back."""
    text = memory.text.strip()
    gist = _GIST.match(text)
    if memory.kind == "gist" and gist:
        return f"I remember day {gist.group(1)}: {gist.group(2)}"
    if memory.kind == "thought":
        return f"I keep thinking: {text}"
    words = text[2:].rstrip(".!?") if text.startswith("I ") else ""
    if words and plainly(words) != words:  # the event log's shape, said as the gist says it
        return f"I remember when I {clause(text)}."
    return f"I remember when {text if text.startswith('I ') else text[:1].lower() + text[1:]}"


def yesterday(db: sqlite3.Connection, today: int) -> Memory | None:
    row = db.execute(f"SELECT {','.join(MEMORY_COLUMNS)} FROM mind_memories WHERE kind='gist' AND game_day=? "
                     "ORDER BY id DESC LIMIT 1", (today - 1,)).fetchone()
    return memory_of(row) if row is not None else None


def asks_about_a_trip(heard: Heard) -> bool:
    text = heard.text.lower().replace("\u2019", "'").strip()
    return (bool(heard.words & TRIP_WORDS) or any(pair in text for pair in TRIP_PAIRS)
            or (text.endswith("?") and any(words in text for words in TRIP_QUESTIONS)))


def trip_told(db: sqlite3.Connection, today: int) -> tuple[int, str] | None:
    """The newest homecoming of the last TRIP_FRESH game days as Mimo tells it, and its memory's id."""
    home = db.execute("SELECT id, text, game_day FROM mind_memories WHERE source='expedition' AND game_day >= ? "
                      "AND text LIKE 'I came home from my expedition:%' ORDER BY id DESC LIMIT 1",
                      (today - TRIP_FRESH,)).fetchone()
    found = _HOME.search(home["text"]) if home is not None else None
    if found is None:
        return None
    far, nights, learned = (int(value) for value in found.groups())
    out = db.execute("SELECT id, text FROM mind_memories WHERE source='expedition' AND id < ? "
                     "AND text LIKE 'I set out on an expedition%' ORDER BY id DESC LIMIT 1", (home["id"],)).fetchone()
    heading = _OUT.search(out["text"]) if out is not None else None
    marks = ",".join("?" * len(ROUGH))
    # A trip lasts its nights and the days on the trail at most (M4): without its setting out (faded,
    # or forgotten by the cap), look no further back than that, not the whole life's rough moments.
    rough = db.execute(f"SELECT COUNT(*) FROM mind_memories WHERE id > ? AND id < ? AND game_day >= ? "
                       f"AND source IN ({marks})",
                       (out["id"] if out is not None else 0, home["id"], home["game_day"] - nights - 2,
                        *ROUGH)).fetchone()[0]
    parts = [f"went {far} blocks" + (f" {heading.group(1)}" if heading else "")]
    if nights:
        parts.append(f"camped {number(nights)} night{'' if nights == 1 else 's'}")
    if learned:
        parts.append(f"learned {number(learned)} new thing{'' if learned == 1 else 's'}")
    return home["id"], f"It was {'a wild one' if rough else 'wonderful'}! I {joined(parts)}."


def hear_trip(db: sqlite3.Connection, s: Situation, heard: Heard) -> dict | None:
    """talk.HEARING["trip"]: the trip the owner asks about, if Mimo just came home from one."""
    if not asks_about_a_trip(heard):
        return None
    found = trip_told(db, s.clock["day_number"])
    return {"id": found[0], "line": clip(found[1])} if found else None


def hear_memories(db: sqlite3.Connection, s: Situation, heard: Heard) -> dict | None:
    """talk.HEARING["memory"]: the memory the owner's words bring back, if any ({"id", "line", "weight"})."""
    if heard.context.get(TRIP):
        return None  # the trip line tells it
    asked = bool(heard.words & MEMORY_WORDS)
    if "yesterday" in heard.words:
        found = yesterday(db, s.clock["day_number"])
        if found is not None:
            return {"id": found.id, "line": clip(recalled_line(found)), "weight": WEIGHT + 1.0}
    cue = cue_of(heard.text)
    things = any(thing and word not in TIMES for word, _, thing in cue.terms)
    for item in recall(db, cue, s.at, s.scale, RECALLED):
        if item.memory.source == OWNER_FACT:
            continue  # Bond's to say back
        if item.relevance >= THING_MATCH and things or item.relevance > 0 and asked:
            return {"id": item.memory.id, "line": clip(recalled_line(item.memory)),
                    "weight": WEIGHT + item.relevance + (1.0 if asked else 0.0)}
    return None


def trip_reply(s: Situation, heard: Heard) -> Reply | None:
    """A reply writer: how the trip went, from the homecoming memory."""
    found = heard.context.get(TRIP)
    return Reply(TRIP, found["line"], weight=TRIP_WEIGHT, note={"memory": found["id"]}) if found else None


def memory_reply(s: Situation, heard: Heard) -> Reply | None:
    """A reply writer: the memory the owner's words brought back, with its weight and its note."""
    found = heard.context.get(MEMORY)
    return Reply(MEMORY, found["line"], weight=found["weight"], note={"memory": found["id"]}) if found else None


def rehearse_quoted(db: sqlite3.Connection, state: dict, heard: Heard, note: dict, now: float) -> None:
    """REPLY_KEEPERS["trip"] and ["memory"]: the memory a chosen reply said back grows stronger."""
    if note.get("memory"):
        rehearse(db, [note["memory"]], now)


HEARING[TRIP] = hear_trip
HEARING[MEMORY] = hear_memories
REPLIES[TRIP] = trip_reply
REPLIES[MEMORY] = memory_reply
ABOUT.update({TRIP: "how its trip went", MEMORY: "what it remembers"})
REPLY_KEEPERS.update({TRIP: rehearse_quoted, MEMORY: rehearse_quoted})
