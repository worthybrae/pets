"""Thoughts (Mind M2): once a game day, Mimo reflects on what it remembers.

The rules read patterns in the memory stream over the last LOOKBACK game days (`insights`, a few
bounded queries) and write candidate thoughts in Mimo's voice, best first, at most INSIGHTS:
- "careful": it nearly died ("I nearly died. I'll be more careful from now on.");
- "hungry_trips": hunger on the days of its trips ("I keep coming home hungry from long trips. I
  should pack more food."), nudge "pack";
- "wary:<kind>": blows or threats from a hostile kind at dusk or night ("Skitters come out near the
  caves at night."), nudge "wary:<kind>";
- "likes:<purpose>": something it did a lot and enjoyed ("I love fishing by the lake."), nudge
  "likes:<purpose>";
- "taught": the owner taught it things ("You teach me so much. I love learning from you.");
- "evenings" or "daily": when the owner comes by ("You visit me in the evenings.");
- "learned:<n>": every ten lessons ("I have learned 20 things; there is so much more out there.");
- "goals:<n>": goals reached ("I have reached 3 goals. I can do anything I set my mind to.");
- "home": a home it built ("Home feels safe. I love my own little house.").
An insight Mimo had in the last THOUGHT_REST game days is not offered again.

Mimo reflects at dusk: the first purpose call to Jev from dusk on, once a game day, asks two
questions more (choosing.ASIDES), "thought" and "another_thought", each "none" or a candidate, so
Jev keeps none, one or two (the same one twice counts once). Without Jev that day, the night's
consolidation keeps the top candidate every other day (consolidation.NIGHTLY). A kept insight is
a thought memory (importance 7) or, when Mimo had it before, strengthens that one; its nudge (if
any) holds for NUDGE_DAYS game days (state["mind"]["nudges"]: {nudge: last game day}), and
backend.survival.nudges turns it into a small, bounded change of behaviour.

The goal choice is shown the THOUGHTS_SHOWN thoughts most relevant to the goals on offer
(choosing.GOAL_NOTES), rehearsed when the goal is stored.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass

from backend.survival.choosing import ASIDES, GOAL_NOTES, Aside
from backend.survival.clock import clock_at
from backend.survival.consolidation import NIGHTLY
from backend.survival.goals import REACHED
from backend.survival.journal import FACT as LESSON
from backend.survival.mind import add_memory, mind_state, rehearse, recall
from backend.survival.pickers import Option
from backend.survival.situation import Situation

LOOKBACK = 7  # game days of memories reflection reads
INSIGHTS = 5  # candidate thoughts at most
THOUGHT_REST = 5  # game days before an insight is offered again
NUDGE_DAYS = 10  # game days a thought's nudge holds
THOUGHTS_SHOWN = 3  # thoughts in the goal choice's payload
ROWS = 2000  # memories reflection reads at most
EVENING = ("dusk", "night", "pre_dawn")
NONE = "none"
HOSTILE = {"skitter": "Skitters come out near the caves at night.",
           "gloomling": "Gloomlings roam in the dark. I'd better stay in at night."}
LIKES = (("fish", "fish", 6, "I love fishing by the lake."), ("hunt", "hunt", 5, "I love a good hunt."),
         ("found", "explore", 8, "I love finding new places."), ("learned", "investigate", 5,
                                                                   "I love learning how the world works."))
REFLECT_INSTRUCTIONS = ("At the end of its day this small pet thinks about what it remembers. Choose the thought "
                        "that rings most true for it, given its memories, traits and mood, or \"none\". Choose only "
                        "from the offered thoughts.")


@dataclass(frozen=True)
class Insight:
    key: str
    text: str
    score: float
    feeling: int = 1
    about: tuple[str, ...] = ()
    nudge: str = ""


def insights(db: sqlite3.Connection, state: dict, day: int, scale: float) -> list[Insight]:
    """What Mimo could think about its last LOOKBACK game days, best first, at most INSIGHTS."""
    rows = db.execute("SELECT game_day, at, kind, source, about, count, feeling FROM mind_memories WHERE game_day > ? "
                      "AND kind IN ('episode', 'told', 'lesson') ORDER BY id DESC LIMIT ?",
                      (day - LOOKBACK, ROWS)).fetchall()
    rested = {row[0] for row in db.execute("SELECT source FROM mind_memories WHERE kind='thought' AND game_day > ?",
                                           (day - THOUGHT_REST,))}
    found: list[Insight] = []
    days: dict[str, set] = {}
    counts: Counter = Counter()
    evening: Counter = Counter()
    for row in rows:
        source = row["source"]
        days.setdefault(source, set()).add(row["game_day"])
        counts[source] += row["count"]
        if clock_at(state["born_at"], row["at"], scale)["phase"] in EVENING:
            evening[source] += row["count"]
            if source in ("hurt", "threat", "fight"):
                for kind in HOSTILE:
                    if kind in row["about"].split():
                        counts[f"night:{kind}"] += row["count"]
    if counts["near_death"]:
        found.append(Insight("careful", "I nearly died. I'll be more careful from now on.", 9, -1))
    hungry = days.get("expedition", set()) & (days.get("hungry", set()) | days.get("starving", set()))
    if len(hungry) >= 2:
        found.append(Insight("hungry_trips", "I keep coming home hungry from long trips. I should pack more food.", 8,
                             -1, ("expedition", "food"), "pack"))
    for kind, text in HOSTILE.items():
        if counts[f"night:{kind}"] >= 2:
            found.append(Insight(f"wary:{kind}", text, 7, -1, (kind, "night"), f"wary:{kind}"))
    for source, purpose, least, text in LIKES:
        if counts[source] >= least and len(days.get(source, ())) >= 2:
            found.append(Insight(f"likes:{purpose}", text, 6, 2, (), f"likes:{purpose}"))
    if counts["taught"] + counts["seen_true"] >= 2:
        found.append(Insight("taught", "You teach me so much. I love learning from you.", 6, 2, ("owner",)))
    owner = sum(counts[source] for source in ("hello", "care", "owner", "taught"))
    if owner >= 3 and sum(evening[source] for source in ("hello", "care", "owner", "taught")) * 2 > owner:
        found.append(Insight("evenings", "You visit me in the evenings.", 5, 1, ("owner",)))
    elif len(set().union(*(days.get(source, set()) for source in ("hello", "care", "owner", "taught")))) >= 3:
        found.append(Insight("daily", "You come to see me every day.", 5, 2, ("owner",)))
    lessons = db.execute("SELECT COUNT(*) FROM memory_knowledge WHERE fact=?", (LESSON,)).fetchone()[0] // 10 * 10
    if lessons:
        found.append(Insight(f"learned:{lessons}", f"I have learned {lessons} things; there is so much more out there.",
                             5, 1))
    goals = db.execute("SELECT COUNT(*) FROM memory_knowledge WHERE fact=?", (REACHED,)).fetchone()[0]
    if goals >= 3:
        found.append(Insight(f"goals:{goals}", f"I have reached {goals} goals. I can do anything I set my mind to.", 4,
                             2))
    if counts["built"]:
        found.append(Insight("home", "Home feels safe. I love my own little house.", 4, 2, ("home",)))
    fresh = [insight for insight in found if insight.key not in rested]
    return sorted(fresh, key=lambda insight: (-insight.score, insight.key))[:INSIGHTS]


def think(db: sqlite3.Connection, state: dict, insight: Insight, day: int, at: float) -> int:
    """Keep an insight as a thought (importance 7), or strengthen the thought Mimo had before; its
    nudge holds for NUDGE_DAYS game days."""
    row = db.execute("SELECT id FROM mind_memories WHERE kind='thought' AND source=?", (insight.key,)).fetchone()
    if row is not None:
        rehearse(db, [row[0]], at)
        db.execute("UPDATE mind_memories SET at=?, game_day=? WHERE id=?", (at, day, row[0]))
        memory = row[0]
    else:
        memory = add_memory(db, at, day, "thought", insight.text, insight.about, 7, insight.feeling, insight.key)
    if insight.nudge:
        nudges = mind_state(state)["nudges"]
        nudges[insight.nudge] = max(nudges.get(insight.nudge, 0), day + NUDGE_DAYS)
    return memory


# At dusk, in the purpose call to Jev ----------------------------------------------------------------

def reflect_due(s: Situation) -> bool:
    return s.phase in EVENING and mind_state(s.state)["reflected"] < s.clock["day_number"]


def reflection(s: Situation) -> list[Aside]:
    """The two questions reflection adds to a purpose call to Jev at dusk, once a game day."""
    if s.db is None or not reflect_due(s):
        return []
    found = insights(s.db, s.state, s.clock["day_number"], s.scale)
    if not found:
        return []
    options = (Option(NONE, "nothing", "Think nothing more of today.", "not every day needs a thought", 0.0),
               *(Option(insight.key, insight.text, f'Think: "{insight.text}"', "from what it remembers of the last "
                        f"{LOOKBACK} days", insight.score) for insight in found))
    by_key, kept, day = {insight.key: insight for insight in found}, set(), s.clock["day_number"]

    def keep(db: sqlite3.Connection, state: dict, pick: str | None, now: float, scale: float) -> None:
        if pick is None:
            return  # Jev did not answer: the night's rules reflect instead
        mind = mind_state(state)
        mind["reflected"] = max(mind["reflected"], day)
        if pick in by_key and pick not in kept:
            kept.add(pick)
            think(db, state, by_key[pick], day, now)
    return [Aside("thought", options, REFLECT_INSTRUCTIONS, keep), Aside("another_thought", options,
                                                                         REFLECT_INSTRUCTIONS, keep)]


def rules_reflection(db: sqlite3.Connection, state: dict, day: int, at: float, scale: float) -> None:
    """A NIGHTLY hook: a day Jev did not reflect on, the rules keep the top insight every other day."""
    mind = mind_state(state)
    if mind["reflected"] >= day:
        return
    mind["reflected"] = day
    if day - mind["rules_thought"] < 2:
        return
    found = insights(db, state, day, scale)
    if found:
        think(db, state, found[0], day, at)
        mind["rules_thought"] = day


def goal_thoughts(db: sqlite3.Connection, s: Situation, choices) -> tuple[list[str], list[int]]:
    """A GOAL_NOTES note: the thoughts most relevant to the goals on offer, and their ids."""
    cue = " ".join(f"{option.phrase} {option.description}" for option in choices)
    found = recall(db, cue, s.at, s.scale, THOUGHTS_SHOWN, kinds=("thought",))
    return [item.memory.text for item in found], [item.memory.id for item in found]


ASIDES.append(reflection)
NIGHTLY["reflection"] = rules_reflection
GOAL_NOTES["thoughts"] = goal_thoughts
